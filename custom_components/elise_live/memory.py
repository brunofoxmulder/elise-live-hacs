"""Fail-safe local bridge from Élise Live to Élise Memory."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import logging
from typing import Any

from .live import LiveTool

_LOGGER = logging.getLogger(__name__)

# Internal Home Assistant app hostname for the Élise Memory repository.
# This stays on the Supervisor network; no LAN address or Google identifier is used.
DEFAULT_MEMORY_BASE_URL = "http://d37d49e7-elise-memory:8099"
MEMORY_SEARCH_TOOL_NAME = "elise_memory_search"
_MAX_OPENINGS = 128
_MAX_VALUE_CHARS = 1600

_MEMORY_TOOL_INSTRUCTION = (
    "A local deterministic house-memory tool named elise_memory_search is available. "
    "Use it when the user asks about durable Maison Cognitive knowledge: configuration, "
    "automations, scripts, functional relationships, documented house behavior, or remembered "
    "facts. Do not use it for direct device control or for a current device state; use the "
    "Home Assistant tools for those. For a question asking why an entity is currently in its "
    "state, prefer the dedicated Investigator tool when it is available. Never invent a memory "
    "fact when elise_memory_search can check it."
)


@dataclass(slots=True)
class MemoryOpening:
    """Deterministic conversation-opening state returned by Élise Memory."""

    awake: bool
    wake_at: str
    should_greet: bool
    greeting_reason: str
    source_entity_id: str
    committed: bool = False


def memory_search_tool() -> LiveTool:
    """Return the provider-neutral memory search tool declaration."""
    return LiveTool(
        name=MEMORY_SEARCH_TOOL_NAME,
        description=(
            "Search Élise Memory, the local persistent Maison Cognitive knowledge base. "
            "Use this for durable facts about the home, automations, scripts, relationships "
            "and documented behavior; not for live state or device control."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Short natural-language search focused on the house knowledge needed, "
                        "for example 'volet salon' or 'phase lave linge'."
                    ),
                }
            },
            "required": ["query"],
        },
    )


def add_memory_tool(tools: list[LiveTool]) -> list[LiveTool]:
    """Append the internal memory tool without shadowing an existing tool."""
    if any(tool.name == MEMORY_SEARCH_TOOL_NAME for tool in tools):
        _LOGGER.warning(
            "Tool name %s already exists; Élise Memory search will not be added",
            MEMORY_SEARCH_TOOL_NAME,
        )
        return tools
    return [*tools, memory_search_tool()]


def add_memory_instruction(
    system_instruction: str,
    opening: MemoryOpening | None,
) -> str:
    """Append stable memory/tool guidance and optional wake-cycle greeting context."""
    parts = [system_instruction, _MEMORY_TOOL_INSTRUCTION]
    if opening is not None and opening.should_greet:
        parts.append(
            "Deterministic opening context from Élise Memory: this is the first conversation "
            f"since the current wake cycle began at {opening.wake_at}. On the FIRST assistant "
            "reply of this conversation only, begin naturally with 'Bonjour mon cœur'. "
            "Do not repeat that wake greeting on later turns in the same conversation."
        )
    return "\n\n".join(part for part in parts if part)


def assistant_confirms_wake_greeting(text: str) -> bool:
    """Return True only when the generated transcript contains the expected greeting."""
    head = (text or "").strip().lower()[:220]
    return "bonjour" in head and ("mon cœur" in head or "mon coeur" in head)


class MemoryBridge:
    """Small fail-safe client for the local Élise Memory HTTP API."""

    def __init__(
        self,
        session: Any,
        *,
        base_url: str = DEFAULT_MEMORY_BASE_URL,
        timeout: float = 2.0,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._openings: OrderedDict[str, MemoryOpening] = OrderedDict()

    async def async_open(self, conversation_id: str) -> MemoryOpening | None:
        """Read and cache one opening context per conversation."""
        if opening := self._openings.get(conversation_id):
            self._openings.move_to_end(conversation_id)
            return opening

        status, payload = await self._request("GET", "/v1/session/open")
        if status != 200 or not isinstance(payload, dict):
            return None
        try:
            opening = MemoryOpening(
                awake=bool(payload["awake"]),
                wake_at=str(payload["cycle_since"]),
                should_greet=bool(payload["should_greet"]),
                greeting_reason=str(payload.get("greeting_reason", "")),
                source_entity_id=str(payload.get("source_entity_id", "")),
            )
        except (KeyError, TypeError, ValueError):
            _LOGGER.warning("Élise Memory returned an invalid session opening payload")
            return None

        self._openings[conversation_id] = opening
        self._openings.move_to_end(conversation_id)
        while len(self._openings) > _MAX_OPENINGS:
            self._openings.popitem(last=False)
        return opening

    async def async_search(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        """Search local house knowledge and return a compact model-facing result."""
        normalized = " ".join((query or "").split()).strip()
        if not normalized:
            return {"available": True, "query": query, "knowledge": [], "relations": []}

        status, payload = await self._request(
            "GET",
            "/v1/knowledge/search",
            params={"q": normalized, "limit": max(1, min(int(limit), 8))},
        )
        if status != 200 or not isinstance(payload, dict):
            return {"available": False, "error": "elise_memory_unavailable"}

        knowledge = []
        for row in payload.get("knowledge", [])[:8]:
            if not isinstance(row, dict):
                continue
            knowledge.append(
                {
                    "key": row.get("key"),
                    "object_type": row.get("object_type"),
                    "domain": row.get("domain"),
                    "value": str(row.get("value", ""))[:_MAX_VALUE_CHARS],
                    "origin": row.get("origin"),
                    "source_id": row.get("source_id"),
                }
            )

        relations = []
        for row in payload.get("relations", [])[:8]:
            if not isinstance(row, dict):
                continue
            relations.append(
                {
                    "subject_key": row.get("subject_key"),
                    "relation": row.get("relation"),
                    "object_key": row.get("object_key"),
                }
            )

        return {
            "available": True,
            "query": normalized,
            "knowledge": knowledge,
            "relations": relations,
        }

    async def async_commit_greeting(self, conversation_id: str) -> bool:
        """Confirm a wake greeting only after the caller observed it in output."""
        opening = self._openings.get(conversation_id)
        if opening is None or not opening.should_greet or opening.committed:
            return False

        status, _payload = await self._request(
            "POST",
            "/v1/session/greeting/commit",
            json={"wake_at": opening.wake_at},
        )
        if status == 204:
            opening.committed = True
            return True
        if status == 409:
            # The wake cycle changed; the old greeting decision is no longer applicable.
            opening.committed = True
        return False

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> tuple[int | None, Any]:
        """Issue one bounded local request; errors never propagate into Élise Live."""
        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.request(method, url, **kwargs) as response:
                    status = int(response.status)
                    if status == 204:
                        return status, None
                    if status < 200 or status >= 300:
                        _LOGGER.debug(
                            "Élise Memory request failed method=%s path=%s status=%s",
                            method,
                            path,
                            status,
                        )
                        return status, None
                    return status, await response.json()
        except (TimeoutError, OSError, ValueError) as exc:
            _LOGGER.debug(
                "Élise Memory unavailable method=%s path=%s error=%s",
                method,
                path,
                type(exc).__name__,
            )
            return None, None
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug(
                "Élise Memory request failed safely method=%s path=%s error=%s",
                method,
                path,
                type(exc).__name__,
            )
            return None, None

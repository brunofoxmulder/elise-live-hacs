"""Unit tests for the provider-neutral Élise Memory bridge."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "elise_live"

package = types.ModuleType("elise_live")
package.__path__ = [str(PACKAGE_DIR)]
sys.modules.setdefault("elise_live", package)

for module_name in ("live", "memory"):
    spec = importlib.util.spec_from_file_location(
        f"elise_live.{module_name}",
        PACKAGE_DIR / f"{module_name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"elise_live.{module_name}"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)

from elise_live.live import LiveTool  # noqa: E402
from elise_live.memory import (  # noqa: E402
    MEMORY_SEARCH_TOOL_NAME,
    MemoryBridge,
    add_memory_instruction,
    add_memory_tool,
    assistant_confirms_wake_greeting,
)


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("Unexpected HTTP request")
        status, payload = self.responses.pop(0)
        return FakeResponse(status, payload)


OPENING = {
    "awake": True,
    "cycle_since": "2026-09-19T06:00:00+02:00",
    "should_greet": True,
    "greeting_reason": "first_conversation_since_wake",
    "source_entity_id": "switch.prise_de_comptage_prise_1",
}


class MemoryBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_opening_is_cached_per_conversation(self):
        session = FakeSession([(200, OPENING)])
        bridge = MemoryBridge(session, base_url="http://memory")

        first = await bridge.async_open("conversation-1")
        second = await bridge.async_open("conversation-1")

        self.assertIs(first, second)
        self.assertTrue(first.should_greet)
        self.assertEqual(len(session.calls), 1)

    async def test_search_returns_compact_bounded_payload(self):
        session = FakeSession(
            [
                (
                    200,
                    {
                        "knowledge": [
                            {
                                "key": "volet salon",
                                "object_type": "automation",
                                "domain": "cover",
                                "value": "x" * 2000,
                                "origin": "canonical",
                                "source_id": "automations:production:volet-salon",
                                "evidence": "must not be forwarded",
                            }
                        ],
                        "relations": [
                            {
                                "subject_key": "volet salon",
                                "relation": "piloté_par",
                                "object_key": "automation.volet_salon",
                                "source_id": "hidden here",
                            }
                        ],
                    },
                )
            ]
        )
        bridge = MemoryBridge(session, base_url="http://memory")

        result = await bridge.async_search("  volet   salon  ")

        self.assertTrue(result["available"])
        self.assertEqual(result["query"], "volet salon")
        self.assertEqual(len(result["knowledge"][0]["value"]), 1600)
        self.assertNotIn("evidence", result["knowledge"][0])
        self.assertNotIn("source_id", result["relations"][0])

    async def test_greeting_commit_occurs_once_after_opening(self):
        session = FakeSession([(200, OPENING), (204, None)])
        bridge = MemoryBridge(session, base_url="http://memory")

        opening = await bridge.async_open("conversation-1")
        self.assertTrue(opening.should_greet)
        self.assertTrue(await bridge.async_commit_greeting("conversation-1"))
        self.assertTrue(opening.committed)
        self.assertFalse(opening.should_greet)
        self.assertNotIn("Bonjour mon cœur", add_memory_instruction("base", opening))
        self.assertFalse(await bridge.async_commit_greeting("conversation-1"))

        cached = await bridge.async_open("conversation-1")
        self.assertIs(cached, opening)
        self.assertFalse(cached.should_greet)
        self.assertEqual(len(session.calls), 2)
        method, url, kwargs = session.calls[1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/v1/session/greeting/commit"))
        self.assertEqual(kwargs["json"]["wake_at"], OPENING["cycle_since"])

    async def test_memory_failure_is_non_blocking(self):
        bridge = MemoryBridge(
            FakeSession(error=OSError("offline")),
            base_url="http://memory",
        )

        self.assertIsNone(await bridge.async_open("conversation-1"))
        result = await bridge.async_search("volet salon")
        self.assertEqual(
            result,
            {"available": False, "error": "elise_memory_unavailable"},
        )

    def test_memory_tool_and_instruction(self):
        tools = add_memory_tool([])
        self.assertEqual([tool.name for tool in tools], [MEMORY_SEARCH_TOOL_NAME])

        duplicate = add_memory_tool(
            [LiveTool(MEMORY_SEARCH_TOOL_NAME, "existing")]
        )
        self.assertEqual(len(duplicate), 1)

        instruction = add_memory_instruction("base", None)
        self.assertIn("elise_memory_search", instruction)
        self.assertNotIn("Bonjour mon cœur", instruction)

    def test_expected_wake_greeting_detection(self):
        self.assertTrue(
            assistant_confirms_wake_greeting("Bonjour mon cœur, que puis-je faire ?")
        )
        self.assertTrue(
            assistant_confirms_wake_greeting("Bonjour mon coeur !")
        )
        self.assertFalse(
            assistant_confirms_wake_greeting("Bonsoir mon cœur.")
        )


if __name__ == "__main__":
    unittest.main()

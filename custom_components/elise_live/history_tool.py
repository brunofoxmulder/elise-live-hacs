"""Read-only Home Assistant Recorder history tool for live models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.homeassistant.llm import async_get_exposed_entities
from homeassistant.components.recorder import get_instance, history
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from .live import LiveTool

HISTORY_TOOL_NAME = "GetHistory"
_VALID_OPERATIONS = {"states", "last_change", "count", "duration", "value_at", "statistics"}

HISTORY_TOOL = LiveTool(
    name=HISTORY_TOOL_NAME,
    description=(
        "Read Home Assistant Recorder history for one Home Assistant entity. Identify the "
        "entity by its natural Home Assistant name or alias, optionally narrowed by domain "
        "or area. Do not invent an entity_id. Use for historical questions such as when an "
        "entity changed, its states, transition count, time spent in a state, a value at a "
        "time, or min/max/average over a period. Read-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": sorted(_VALID_OPERATIONS)},
            "name": {
                "type": "string",
                "description": "Home Assistant entity name or alias, for example volet salon.",
            },
            "domain": {
                "type": "string",
                "description": "Optional Home Assistant domain, for example cover or light.",
            },
            "area": {
                "type": "string",
                "description": "Optional Home Assistant area name.",
            },
            "start_time": {"type": "string", "description": "ISO 8601 start time with timezone."},
            "end_time": {"type": "string", "description": "ISO 8601 end time with timezone."},
            "target_state": {
                "type": "string",
                "description": "State used by last_change, count or duration when relevant.",
            },
            "at_time": {
                "type": "string",
                "description": "ISO 8601 instant for value_at.",
            },
        },
        "required": ["operation", "name"],
        "additionalProperties": False,
    },
)


def add_history_tool(tools: list[LiveTool]) -> list[LiveTool]:
    """Append the integration-owned Recorder tool."""
    if any(tool.name == HISTORY_TOOL_NAME for tool in tools):
        return tools
    return [*tools, HISTORY_TOOL]


def _resolve_entity_id(hass: HomeAssistant, args: dict[str, Any]) -> str:
    """Resolve one natural target against entities exposed to Assist."""
    name = args.get("name")
    domain = args.get("domain")
    area = args.get("area")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a Home Assistant entity name or alias")
    if domain is not None and (not isinstance(domain, str) or not domain.strip()):
        raise ValueError("domain must be a Home Assistant domain")
    if area is not None and (not isinstance(area, str) or not area.strip()):
        raise ValueError("area must be a Home Assistant area name")

    exposed_entities = async_get_exposed_entities(
        hass, "conversation", include_state=False
    )
    exposed_states = [
        state
        for entity_id in exposed_entities
        if (state := hass.states.get(entity_id)) is not None
    ]
    match_result = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            name=name.strip(),
            area_name=area.strip() if isinstance(area, str) else None,
            domains=[domain.strip()] if isinstance(domain, str) else None,
            allow_duplicate_names=True,
        ),
        states=exposed_states,
    )
    if not match_result.is_match or not match_result.states:
        raise ValueError(f"No exposed Home Assistant entity matches {name!r}")
    if len(match_result.states) != 1:
        matches = ", ".join(sorted(state.entity_id for state in match_result.states))
        raise ValueError(
            f"Ambiguous Home Assistant entity name {name!r}; matches: {matches}. "
            "Add domain or area to disambiguate."
        )
    return match_result.states[0].entity_id


def _parse_time(hass: HomeAssistant, value: str | None, field: str) -> datetime:
    if not value or (parsed := dt_util.parse_datetime(value)) is None:
        raise ValueError(f"{field} must be a valid ISO 8601 datetime")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_time_zone(hass.config.time_zone) or UTC)
    return dt_util.as_utc(parsed)


def _window(hass: HomeAssistant, args: dict[str, Any]) -> tuple[datetime, datetime]:
    operation = args["operation"]
    if operation == "value_at":
        at_time = _parse_time(hass, args.get("at_time"), "at_time")
        return at_time, at_time + timedelta(microseconds=1)
    end = _parse_time(hass, args.get("end_time"), "end_time") if args.get("end_time") else dt_util.utcnow()
    start = _parse_time(hass, args.get("start_time"), "start_time") if args.get("start_time") else end - timedelta(days=1)
    if end <= start:
        raise ValueError("end_time must be after start_time")
    return start, end


def _serialize(state: State) -> dict[str, Any]:
    return {"state": state.state, "time": dt_util.as_local(state.last_updated).isoformat()}


def _valid_numeric(states: list[State]) -> list[float]:
    values: list[float] = []
    for state in states:
        if state.state in {"unknown", "unavailable"}:
            continue
        try:
            values.append(float(state.state))
        except (TypeError, ValueError):
            continue
    return values


def _compute(args: dict[str, Any], states: list[State], start: datetime, end: datetime) -> dict[str, Any]:
    operation = args["operation"]
    target = args.get("target_state")
    usable = [state for state in states if state.state not in {"unknown", "unavailable"}]

    if operation == "states":
        return {"states": [_serialize(state) for state in states[:200]], "truncated": len(states) > 200}

    if operation == "value_at":
        state = states[-1] if states else None
        return {
            "value": (
                _serialize(state)
                if state is not None and state.state not in {"unknown", "unavailable"}
                else None
            )
        }

    transitions = states[1:] if len(states) > 1 else []
    if operation == "last_change":
        if target is None:
            matches = transitions
        else:
            matches = [
                state
                for index, state in enumerate(states[1:], start=1)
                if state.state == target and states[index - 1].state != target
            ]
        return {"change": _serialize(matches[-1]) if matches else None}

    if operation == "count":
        if target is None:
            matches = transitions
        else:
            matches = [
                state
                for index, state in enumerate(states[1:], start=1)
                if state.state == target and states[index - 1].state != target
            ]
        return {"count": len(matches), "target_state": target}

    if operation == "duration":
        if target is None:
            raise ValueError("target_state is required for duration")
        seconds = 0.0
        for index, state in enumerate(states):
            segment_start = max(start, state.last_updated)
            segment_end = min(end, states[index + 1].last_updated) if index + 1 < len(states) else end
            if state.state == target and segment_end > segment_start:
                seconds += (segment_end - segment_start).total_seconds()
        return {"seconds": round(seconds, 3), "target_state": target}

    if operation == "statistics":
        values = _valid_numeric(states)
        if not values:
            return {"statistics": None}
        weighted_sum = 0.0
        weighted_seconds = 0.0
        for index, state in enumerate(states):
            if state.state in {"unknown", "unavailable"}:
                continue
            try:
                value = float(state.state)
            except (TypeError, ValueError):
                continue
            segment_start = max(start, state.last_updated)
            segment_end = min(end, states[index + 1].last_updated) if index + 1 < len(states) else end
            seconds = max(0.0, (segment_end - segment_start).total_seconds())
            weighted_sum += value * seconds
            weighted_seconds += seconds
        return {
            "statistics": {
                "min": min(values),
                "max": max(values),
                "average": weighted_sum / weighted_seconds if weighted_seconds else sum(values) / len(values),
                "samples": len(values),
            }
        }

    raise ValueError(f"Unsupported history operation: {operation}")


async def async_handle_history_tool(
    hass: HomeAssistant, args: dict[str, Any]
) -> dict[str, Any]:
    """Execute one read-only Recorder history query."""
    operation = args.get("operation")
    if operation not in _VALID_OPERATIONS:
        raise ValueError("Invalid history operation")
    entity_id = _resolve_entity_id(hass, args)

    start, end = _window(hass, args)
    def _read() -> dict[str, list[State]]:
        return history.state_changes_during_period(
            hass,
            start,
            end,
            entity_id=entity_id,
            no_attributes=True,
            include_start_time_state=True,
        )

    result = await get_instance(hass).async_add_executor_job(_read)
    states = result.get(entity_id.lower(), [])
    if operation == "value_at":
        # Recorder's include_start_time_state supplies the state in force at
        # start, even when its last change predates the requested instant.
        states = states[:1]
    return {
        "entity_id": entity_id,
        "operation": operation,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        **_compute(args, states, start, end),
    }

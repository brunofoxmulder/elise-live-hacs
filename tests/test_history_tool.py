"""Unit tests for the deterministic GetHistory calculations."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

_PACKAGE_PATH = Path(__file__).parents[1] / "custom_components" / "elise_live"
_PACKAGE_NAME = "custom_components.elise_live"

# Build a lightweight package shell so relative imports work without executing
# elise_live/__init__.py (which initializes unrelated STT/TTS dependencies).
_package = ModuleType(_PACKAGE_NAME)
_package.__path__ = [str(_PACKAGE_PATH)]
sys.modules[_PACKAGE_NAME] = _package

_live_spec = importlib.util.spec_from_file_location(
    f"{_PACKAGE_NAME}.live", _PACKAGE_PATH / "live.py"
)
_live_module = importlib.util.module_from_spec(_live_spec)
sys.modules[_live_spec.name] = _live_module
assert _live_spec.loader is not None
_live_spec.loader.exec_module(_live_module)

_SPEC = importlib.util.spec_from_file_location(
    f"{_PACKAGE_NAME}.history_tool", _PACKAGE_PATH / "history_tool.py"
)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)
_compute = _MODULE._compute


BASE = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def _state(value: str, minutes: int):
    return SimpleNamespace(state=value, last_updated=BASE + timedelta(minutes=minutes))


def test_states_keeps_recorder_order():
    result = _compute(
        {"operation": "states"},
        [_state("off", 0), _state("on", 10)],
        BASE,
        BASE + timedelta(hours=1),
    )
    assert [item["state"] for item in result["states"]] == ["off", "on"]


def test_last_change_to_target():
    result = _compute(
        {"operation": "last_change", "target_state": "off"},
        [_state("on", 0), _state("off", 10), _state("on", 20), _state("off", 30)],
        BASE,
        BASE + timedelta(hours=1),
    )
    assert result["change"]["time"] == (BASE + timedelta(minutes=30)).isoformat()


def test_count_target_transitions():
    result = _compute(
        {"operation": "count", "target_state": "on"},
        [_state("off", 0), _state("on", 10), _state("off", 20), _state("on", 30)],
        BASE,
        BASE + timedelta(hours=1),
    )
    assert result["count"] == 2


def test_duration_does_not_bridge_unavailable():
    result = _compute(
        {"operation": "duration", "target_state": "on"},
        [_state("on", 0), _state("unavailable", 10), _state("on", 20), _state("off", 30)],
        BASE,
        BASE + timedelta(hours=1),
    )
    assert result["seconds"] == 20 * 60


def test_value_at_does_not_hide_unavailable():
    result = _compute(
        {"operation": "value_at"},
        [_state("21.0", 0), _state("unavailable", 10)],
        BASE,
        BASE + timedelta(hours=1),
    )
    assert result["value"] is None


def test_statistics_time_weighted_average():
    result = _compute(
        {"operation": "statistics"},
        [_state("10", 0), _state("20", 15)],
        BASE,
        BASE + timedelta(hours=1),
    )
    stats = result["statistics"]
    assert stats["min"] == 10
    assert stats["max"] == 20
    assert stats["average"] == 17.5


def test_count_ignores_duplicate_target_samples():
    result = _compute(
        {"operation": "count", "target_state": "on"},
        [_state("off", 0), _state("on", 10), _state("on", 15), _state("off", 20), _state("on", 30)],
        BASE,
        BASE + timedelta(hours=1),
    )
    assert result["count"] == 2


def test_last_change_ignores_duplicate_target_samples():
    result = _compute(
        {"operation": "last_change", "target_state": "on"},
        [_state("off", 0), _state("on", 10), _state("on", 15), _state("off", 20), _state("on", 30)],
        BASE,
        BASE + timedelta(hours=1),
    )
    assert result["change"]["time"] == (BASE + timedelta(minutes=30)).isoformat()


def test_value_at_uses_recorder_start_state():
    """The value at an instant is the start-state supplied by Recorder."""
    result = _compute(
        {"operation": "value_at"},
        [_state("21.5", 0)],
        BASE,
        BASE + timedelta(microseconds=1),
    )
    assert result["value"]["state"] == "21.5"

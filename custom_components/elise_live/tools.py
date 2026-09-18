"""Use Home Assistant's native API merger for both live and typed requests.

No service router or second permission model is implemented here. Home Assistant
owns tool namespacing, schema handling, prompts and dispatch with LLMContext.
"""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

_RESERVED_TOOLS = frozenset({"end_conversation", "show_text"})


def selected_api_ids(config: Mapping[str, Any]) -> list[str]:
    """Preserve the Assist default only when selection has never been saved."""
    value = config.get(CONF_LLM_HASS_API, [llm.LLM_API_ASSIST])
    if value is None:
        return []
    if isinstance(value, str):
        value = [value] if value else []
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise HomeAssistantError("Invalid Home Assistant tool API selection")
    return list(dict.fromkeys(value))


async def async_load_tools(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    llm_context: llm.LLMContext,
) -> llm.APIInstance | None:
    """Load exactly the selected APIs or fail without enabling other tools.

    An empty selection is intentional. Missing APIs must never silently fall back to
    Assist, which could enable home-control tools that the user had deselected.
    """
    api_ids = selected_api_ids(config)
    if not api_ids:
        return None
    instance = await llm.async_get_api(hass, api_ids, llm_context)
    seen: set[str] = set()
    for tool in instance.tools:
        if tool.name in seen or tool.name in _RESERVED_TOOLS:
            raise HomeAssistantError(f"Conflicting tool name: {tool.name}")
        seen.add(tool.name)
    return instance

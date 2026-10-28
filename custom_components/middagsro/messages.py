"""Errors in Danish for the panel (Home Assistant words them in English)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import translation

from .const import DOMAIN


async def async_danish(hass: HomeAssistant, err: Exception) -> str:
    """The error in Danish, as the panel is."""
    key = getattr(err, "translation_key", None)
    if not isinstance(err, HomeAssistantError) or err.translation_domain != DOMAIN or not key:
        return str(err)
    messages = await translation.async_get_translations(hass, "da", "exceptions", [DOMAIN])
    message = messages.get(f"component.{DOMAIN}.exceptions.{key}.message")
    if not message:
        return str(err)
    try:
        return message.format(**(err.translation_placeholders or {})).rstrip(".")
    except (KeyError, IndexError, ValueError):
        return str(err)

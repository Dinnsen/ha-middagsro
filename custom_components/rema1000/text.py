"""Type something to put on the REMA 1000 shopping list."""

from __future__ import annotations

from typing import Any

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import RemaError
from .const import DOMAIN
from .coordinator import RemaConfigEntry, RemaShoppingListCoordinator
from .entity import RemaEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the quick-add field."""
    async_add_entities([RemaQuickAddText(entry.runtime_data.shopping_list, entry)])


class RemaQuickAddText(RemaEntity[RemaShoppingListCoordinator], TextEntity):
    """Write 'letmælk' or '3 x æg': the best REMA product is added, else the text."""

    _attr_mode = TextMode.TEXT
    _attr_native_max = 100
    _attr_native_value = ""

    def __init__(self, coordinator: RemaShoppingListCoordinator, entry: RemaConfigEntry) -> None:
        """Initialize the field."""
        super().__init__(coordinator, entry, "quick_add")
        self._entry = entry
        self._last: dict[str, Any] | None = None

    @property
    def available(self) -> bool:
        """Always usable while the integration is loaded."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """What was added last time."""
        if not self._last:
            return None
        return {
            "last_text": self._last["text"],
            "last_added": self._last["added"],
            "free_text": self._last["free_text"],
            "product_id": self._last["product_id"],
        }

    async def async_set_value(self, value: str) -> None:
        """Add what was typed, then clear the field."""
        if not value.strip():
            return
        try:
            self._last = await self._entry.runtime_data.planner.async_quick_add(value)
        except RemaError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self._attr_native_value = ""
        self.async_write_ha_state()

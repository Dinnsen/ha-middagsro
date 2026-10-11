"""Sensors for REMA 1000."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Catalog
from .coordinator import RemaConfigEntry, RemaOffersCoordinator, RemaShoppingListCoordinator
from .entity import RemaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    data = entry.runtime_data
    async_add_entities(
        [
            RemaListTotalSensor(data.shopping_list, entry),
            RemaCatalogSensor(data.offers, entry, "current_catalog"),
            RemaCatalogSensor(data.offers, entry, "upcoming_catalog"),
        ]
    )


class RemaListTotalSensor(RemaEntity[RemaShoppingListCoordinator], SensorEntity):
    """Estimated price of what is left on the list."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "DKK"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: RemaShoppingListCoordinator, entry: RemaConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "list_total")

    @property
    def native_value(self) -> float | None:
        """Return the estimated total."""
        return self.coordinator.data.unbought_total if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Show how many lines the estimate covers."""
        data = self.coordinator.data
        if not data:
            return None
        open_items = [item for item in data.items if not item.bought]
        return {
            "items": len(open_items),
            "items_without_price": sum(1 for item in open_items if item.price is None),
        }


class RemaCatalogSensor(RemaEntity[RemaOffersCoordinator], SensorEntity):
    """The current or next tilbudsavis. The state is when it starts."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: RemaOffersCoordinator, entry: RemaConfigEntry, key: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, key)
        self._key = key

    @property
    def _catalog(self) -> Catalog | None:
        data = self.coordinator.data
        if not data:
            return None
        return data.current if self._key == "current_catalog" else data.upcoming

    @property
    def native_value(self) -> datetime | None:
        """Return when the avis starts."""
        catalog = self._catalog
        return catalog.valid_from if catalog else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Describe the avis."""
        catalog = self._catalog
        if not catalog:
            return None
        return {
            "catalog_id": catalog.id,
            "label": catalog.label,
            "valid_to": catalog.valid_to.isoformat() if catalog.valid_to else None,
            "offer_count": catalog.offer_count,
            "first_seen": self.coordinator.data.first_seen.get(catalog.id),
        }

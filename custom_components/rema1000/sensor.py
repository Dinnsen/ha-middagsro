"""Sensors for REMA 1000."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Catalog
from .coordinator import RemaConfigEntry, RemaOffersCoordinator, RemaShoppingListCoordinator
from .entity import RemaEntity
from .mealplan import signal_plans_updated

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
            RemaMealPlanSensor(data.shopping_list, entry),
        ]
    )


class RemaMealPlanSensor(RemaEntity[RemaShoppingListCoordinator], SensorEntity):
    """Status of the newest meal plan."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["none", "generating", "error", "draft", "sent"]

    def __init__(self, coordinator: RemaShoppingListCoordinator, entry: RemaConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "meal_plan")
        self._entry = entry

    @property
    def available(self) -> bool:
        """The plan is stored locally, so it is always available."""
        return True

    @property
    def native_value(self) -> str:
        """Generating/error while working, else the newest plan's status."""
        data = self._entry.runtime_data
        if data.planner.status["state"] in ("generating", "error"):
            return data.planner.status["state"]
        plan = data.store.latest_plan
        return plan["status"] if plan else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Describe the newest plan."""
        data = self._entry.runtime_data
        plan = data.store.latest_plan
        attrs: dict[str, Any] = {"message": data.planner.status.get("message")}
        if plan:
            attrs |= {
                "title": plan["title"],
                "start_date": plan["start_date"],
                "end_date": plan["end_date"],
                "total": plan["total"],
                "budget": plan["budget"],
                "over_budget": plan.get("over_budget", False),
                "dinners": {day["date"]: day["dish"] for day in plan["days"]},
            }
        return attrs

    async def async_added_to_hass(self) -> None:
        """Update when plans change."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_plans_updated(self._entry.entry_id), self._plans_updated
            )
        )

    @callback
    def _plans_updated(self) -> None:
        self.async_write_ha_state()


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

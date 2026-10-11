"""Base entity for REMA 1000."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import RemaConfigEntry


class RemaEntity[CoordinatorT: DataUpdateCoordinator](CoordinatorEntity[CoordinatorT]):
    """Common base for REMA 1000 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CoordinatorT, entry: RemaConfigEntry, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            name="REMA 1000",
            manufacturer="REMA 1000",
            model=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://shop.rema1000.dk",
        )

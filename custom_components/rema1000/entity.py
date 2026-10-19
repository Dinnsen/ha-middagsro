"""Base entity for REMA 1000."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import RemaConfigEntry


def device_info(entry: RemaConfigEntry) -> DeviceInfo:
    """The one service device per REMA 1000 account."""
    return DeviceInfo(
        identifiers={(DOMAIN, str(entry.unique_id))},
        name="Middagsro",
        manufacturer="Middagsro",
        model=f"REMA 1000-konto: {entry.title}",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://shop.rema1000.dk",
    )


class RemaEntity[CoordinatorT: DataUpdateCoordinator[Any]](CoordinatorEntity[CoordinatorT]):
    """Common base for REMA 1000 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CoordinatorT, entry: RemaConfigEntry, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(entry)

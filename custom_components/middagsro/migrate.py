"""Move an installation of the old ``rema1000`` integration over to Middagsro.

Before 1.1.0 the integration's id (and folder) was ``rema1000``. The new
config flow finds such an account and creates the Middagsro entry for it;
setting that entry up moves the meal plans, settings and recipe collection,
the device and the entities (with their entity IDs) over, and removes the old
entry. Nothing has to be entered again.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .storage import STORE_VERSION

_LOGGER = logging.getLogger(__name__)

OLD_DOMAIN = "rema1000"
MIGRATE_FROM = "migrate_from"
_STORES = (("mealplans", STORE_VERSION), ("catalogs", STORAGE_VERSION))


def old_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Accounts of the old integration that are not moved over yet."""
    moved = {e.unique_id for e in hass.config_entries.async_entries(DOMAIN)}
    return [e for e in hass.config_entries.async_entries(OLD_DOMAIN) if e.unique_id not in moved]


async def async_migrate(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move an old account's data, device and entities to this entry."""
    old_id = entry.data.get(MIGRATE_FROM)
    if not old_id:
        return
    old = hass.config_entries.async_get_entry(old_id)
    if old is not None and old.state is ConfigEntryState.LOADED:
        await hass.config_entries.async_unload(old_id)

    for name, version in _STORES:
        source: Store[Any] = Store(hass, version, f"{OLD_DOMAIN}.{old_id}.{name}")
        data = await source.async_load()
        if data is not None:
            await Store(hass, version, f"{DOMAIN}.{entry.entry_id}.{name}").async_save(data)
            await source.async_remove()

    # Entities first: a device that leaves the old entry takes its entities with it.
    entities = er.async_get(hass)
    for item in er.async_entries_for_config_entry(entities, old_id):
        # Only entities without a state can change integration; they come back at setup.
        hass.states.async_remove(item.entity_id)
        entities.async_update_entity_platform(
            item.entity_id, DOMAIN, new_config_entry_id=entry.entry_id
        )

    devices = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(devices, old_id):
        devices.async_update_device(
            device.id,
            add_config_entry_id=entry.entry_id,
            remove_config_entry_id=old_id,
            new_identifiers={
                (DOMAIN if domain == OLD_DOMAIN else domain, value)
                for domain, value in device.identifiers
            },
        )

    if old is not None:
        await hass.config_entries.async_remove(old_id)
    hass.config_entries.async_update_entry(
        entry, data={k: v for k, v in entry.data.items() if k != MIGRATE_FROM}
    )
    _LOGGER.info("Moved %s from the rema1000 integration to Middagsro", entry.title)

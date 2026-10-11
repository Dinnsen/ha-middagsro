"""The REMA 1000 integration."""

from __future__ import annotations

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import RemaAuthError, RemaClient, RemaError
from .const import DOMAIN
from .coordinator import (
    RemaConfigEntry,
    RemaOffersCoordinator,
    RemaRuntimeData,
    RemaShoppingListCoordinator,
)
from .mealplan import MealPlanner
from .panel import async_register_panel, async_unregister_panel
from .services import async_setup_services
from .storage import RemaPlanStore
from .websocket import async_register_websocket

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.TEXT,
    Platform.TODO,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the actions and the panel's websocket commands."""
    async_setup_services(hass)
    async_register_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RemaConfigEntry) -> bool:
    """Set up REMA 1000 from a config entry."""
    # Own session so the login cookies of this account are kept apart.
    session = async_create_clientsession(hass)
    client = RemaClient(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    try:
        await client.async_login()
    except RemaAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except RemaError as err:
        raise ConfigEntryNotReady(str(err)) from err

    store = RemaPlanStore(hass, entry.entry_id)
    await store.async_load()

    shopping_list = RemaShoppingListCoordinator(hass, entry, client)
    offers = RemaOffersCoordinator(hass, entry, client)
    await shopping_list.async_config_entry_first_refresh()
    # Offers come from a third party (Tjek); don't block setup if it fails.
    await offers.async_refresh()

    def catalogs():
        data = offers.data
        return (data.current, data.upcoming) if data else (None, None)

    planner = MealPlanner(
        hass, entry.entry_id, client, store, catalogs, shopping_list.async_add_items
    )
    entry.runtime_data = RemaRuntimeData(
        client=client, shopping_list=shopping_list, offers=offers, store=store, planner=planner
    )

    @callback
    def _offers_updated() -> None:
        if offers.data:
            planner.async_check_auto_generate(offers.data.upcoming)

    entry.async_on_unload(offers.async_add_listener(_offers_updated))
    entry.async_on_unload(planner.async_cancel)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_panel(hass)
    _offers_updated()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemaConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not [
        e for e in hass.config_entries.async_loaded_entries(DOMAIN) if e.entry_id != entry.entry_id
    ]:
        async_unregister_panel(hass)
    return unloaded

"""The REMA 1000 integration."""

from __future__ import annotations

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
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
from .services import async_setup_services

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.TODO]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the services."""
    async_setup_services(hass)
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

    shopping_list = RemaShoppingListCoordinator(hass, entry, client)
    offers = RemaOffersCoordinator(hass, entry, client)
    await shopping_list.async_config_entry_first_refresh()
    # Offers come from a third party (Tjek); don't block setup if it fails.
    await offers.async_refresh()

    entry.runtime_data = RemaRuntimeData(client=client, shopping_list=shopping_list, offers=offers)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

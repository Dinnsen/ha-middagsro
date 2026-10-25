"""Middagsro: meal plans, recipes and REMA 1000 shopping in Home Assistant."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .api import Catalog, RemaAuthError, RemaClient, RemaError
from .bilka import BILKA_ID
from .const import DOMAIN, STORAGE_VERSION
from .coordinator import (
    RemaConfigEntry,
    RemaOffersCoordinator,
    RemaRuntimeData,
    RemaShoppingListCoordinator,
)
from .favorites import FavoriteOffers
from .mealplan import MealPlanner
from .migrate import async_migrate
from .panel import async_register_panel, async_unregister_panel
from .services import async_setup_services
from .storage import STORE_VERSION, RemaPlanStore
from .store_client import REMA, BilkaStoreClient, StoreClient, store_of
from .watch import CHECK_EVERY as WATCH_CHECK_EVERY, async_check as async_watch_check
from .websocket import async_register_websocket

_LOGGER = logging.getLogger(__name__)

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
    """Set up Middagsro for a REMA 1000 account, or for another shop (no login)."""
    await async_migrate(hass, entry)
    # Own session so the login cookies of this account are kept apart.
    session = async_create_clientsession(hass)
    store_id = store_of(entry.data)
    client: RemaClient
    if store_id == REMA:
        client = RemaClient(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    elif store_id == BILKA_ID:
        client = BilkaStoreClient(hass, session, entry.entry_id)
    else:
        client = StoreClient(hass, session, entry.entry_id, store_id)
    try:
        await client.async_login()
    except RemaAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
            translation_placeholders={"email": entry.data[CONF_EMAIL]},
        ) from err
    except RemaError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    store = RemaPlanStore(hass, entry.entry_id)
    await store.async_load()
    store.prices = client.has_prices

    shopping_list = RemaShoppingListCoordinator(hass, entry, client)
    offers = RemaOffersCoordinator(hass, entry, client)
    await shopping_list.async_config_entry_first_refresh()
    # Offers come from a third party (Tjek); don't block setup if it fails.
    await offers.async_refresh()

    def catalogs() -> tuple[Catalog | None, Catalog | None]:
        data = offers.data
        return (data.current, data.upcoming) if data else (None, None)

    async def _mirror(items: list[dict[str, Any]]) -> None:
        """Copy what was put on the list to the family's own to-do list, if chosen."""
        target = str(store.settings.get("ha_todo_entity") or "")
        if not target or hass.states.get(target) is None:
            return
        for item in items:
            name = str(item.get("name") or "").strip()
            amount = int(item.get("amount") or 1)
            if not name:
                continue
            try:
                await hass.services.async_call(
                    "todo",
                    "add_item",
                    {"item": f"{amount} x {name}" if amount > 1 else name},
                    target={"entity_id": target},
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Could not put %s on %s: %s", name, target, err)
                return

    if store_id != REMA:
        shopping_list.mirror = _mirror

    planner = MealPlanner(
        hass, entry.entry_id, client, store, catalogs, shopping_list.async_add_items
    )
    entry.runtime_data = RemaRuntimeData(
        client=client,
        shopping_list=shopping_list,
        offers=offers,
        store=store,
        planner=planner,
        favorite_offers=FavoriteOffers(client),
    )

    @callback
    def _offers_updated() -> None:
        if offers.data:
            planner.async_check_auto_generate(offers.data.upcoming)

    entry.async_on_unload(offers.async_add_listener(_offers_updated))
    entry.async_on_unload(planner.async_cancel)

    # The watch list: every few hours, tell about watched items that came on offer.
    async def _check_watch(_now: datetime) -> None:
        try:
            await async_watch_check(planner)
        except (HomeAssistantError, RemaError, ValueError, TypeError, KeyError) as err:
            _LOGGER.debug("The watch list was not checked: %s", err)

    entry.async_on_unload(async_track_time_interval(hass, _check_watch, WATCH_CHECK_EVERY))
    entry.async_on_unload(async_call_later(hass, 120, _check_watch))
    planner.async_restore_sends()

    # The panel first: forwarding the platforms is the last thing that may fail.
    await async_register_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _offers_updated()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: RemaConfigEntry) -> None:
    """Remove the account's stored plans and offers when the account is removed."""
    for name, version in (("mealplans", STORE_VERSION), ("catalogs", STORAGE_VERSION), ("list", 1)):
        await Store(hass, version, f"{DOMAIN}.{entry.entry_id}.{name}").async_remove()


async def async_unload_entry(hass: HomeAssistant, entry: RemaConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not [
        e for e in hass.config_entries.async_loaded_entries(DOMAIN) if e.entry_id != entry.entry_id
    ]:
        async_unregister_panel(hass)
    return unloaded

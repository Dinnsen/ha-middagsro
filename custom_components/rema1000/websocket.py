"""Websocket commands used by the REMA 1000 panel."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .api import RemaError
from .const import DOMAIN
from .coordinator import RemaConfigEntry
from .mealplan import parse_date, plan_summary
from .schema import vol
from .storage import ALLERGY_OPTIONS, AVOID_OPTIONS, FAVORITE_FREQUENCIES

ENTRY = vol.Optional("entry_id")


def _entry(hass: HomeAssistant, msg: dict[str, Any]) -> RemaConfigEntry:
    entries: list[RemaConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if entry_id := msg.get("entry_id"):
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise HomeAssistantError("REMA 1000 er ikke sat op eller ikke indlæst")
    return entries[0]


def _state(hass: HomeAssistant, entry: RemaConfigEntry) -> dict[str, Any]:
    data = entry.runtime_data
    store = data.store
    offers = data.offers.data
    shopping = data.shopping_list.data

    def catalog(cat: Any) -> dict[str, Any] | None:
        if not cat:
            return None
        return {
            "id": cat.id,
            "label": cat.label,
            "valid_from": cat.valid_from.isoformat() if cat.valid_from else None,
            "valid_to": cat.valid_to.isoformat() if cat.valid_to else None,
        }

    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "settings": store.settings,
        "favorites": store.favorites,
        "plans": [plan_summary(plan) for plan in store.plans],
        "latest_plan": store.latest_plan,
        "status": data.planner.status,
        "default_start": data.planner.default_start().isoformat(),
        "ai_entities": [
            {"entity_id": entity_id, "name": (hass.states.get(entity_id).name)}
            for entity_id in hass.states.async_entity_ids("ai_task")
            if hass.states.get(entity_id)
        ],
        "catalogs": {
            "current": catalog(offers.current) if offers else None,
            "upcoming": catalog(offers.upcoming) if offers else None,
        },
        "rema_list": {
            "name": shopping.name,
            "items": [
                {"id": i.id, "name": i.name, "amount": i.amount, "bought": i.bought}
                for i in shopping.items
            ],
            "total": shopping.unbought_total,
        }
        if shopping
        else None,
        "options": {
            "avoid": list(AVOID_OPTIONS),
            "allergies": list(ALLERGY_OPTIONS),
            "frequencies": list(FAVORITE_FREQUENCIES),
        },
    }


def _wrap(handler):
    """Turn errors into websocket error messages."""

    async def wrapper(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
        try:
            await handler(hass, connection, msg)
        except (HomeAssistantError, RemaError, ValueError) as err:
            connection.send_error(msg["id"], "rema1000_error", str(err))

    wrapper.__name__ = handler.__name__
    return wrapper


@websocket_api.websocket_command({vol.Required("type"): "rema1000/state", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_state(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Everything the panel shows."""
    connection.send_result(msg["id"], _state(hass, _entry(hass, msg)))


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/plan", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_plan(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """One full plan."""
    plan = _entry(hass, msg).runtime_data.store.get_plan(msg["plan_id"])
    if plan is None:
        raise HomeAssistantError("Madplanen findes ikke")
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/settings", ENTRY: str, vol.Required("settings"): dict}
)
@websocket_api.async_response
@_wrap
async def ws_settings(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Save settings."""
    entry = _entry(hass, msg)
    settings = await entry.runtime_data.store.async_set_settings(msg["settings"])
    connection.send_result(msg["id"], settings)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/favorite/save", ENTRY: str, vol.Required("favorite"): dict}
)
@websocket_api.async_response
@_wrap
async def ws_favorite_save(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Add or change a favourite dish."""
    store = _entry(hass, msg).runtime_data.store
    connection.send_result(msg["id"], await store.async_save_favorite(msg["favorite"]))


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/favorite/delete", ENTRY: str, vol.Required("favorite_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_favorite_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Delete a favourite dish."""
    await _entry(hass, msg).runtime_data.store.async_delete_favorite(msg["favorite_id"])
    connection.send_result(msg["id"], True)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/generate",
        ENTRY: str,
        vol.Optional("start_date"): vol.Any(str, None),
    }
)
@websocket_api.async_response
@_wrap
async def ws_generate(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Start making a meal plan."""
    planner = _entry(hass, msg).runtime_data.planner
    planner.async_start_generation(parse_date(msg.get("start_date")))
    connection.send_result(msg["id"], planner.status)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/send", ENTRY: str, vol.Optional("plan_id"): vol.Any(str, None)}
)
@websocket_api.async_response
@_wrap
async def ws_send(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Send a plan's shopping list to the REMA list."""
    plan = await _entry(hass, msg).runtime_data.planner.async_send(msg.get("plan_id"))
    connection.send_result(msg["id"], {"plan_id": plan["id"], "status": plan["status"]})


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/plan/delete", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_plan_delete(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Delete a plan from the history."""
    await _entry(hass, msg).runtime_data.store.async_delete_plan(msg["plan_id"])
    connection.send_result(msg["id"], True)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/search", ENTRY: str, vol.Required("query"): str}
)
@websocket_api.async_response
@_wrap
async def ws_search(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Search products (used for weekly must-haves)."""
    client = _entry(hass, msg).runtime_data.client
    products = await client.async_search_products(msg["query"], 10)
    connection.send_result(msg["id"], [p.as_dict() for p in products])


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the panel's commands."""
    for command in (
        ws_state,
        ws_plan,
        ws_settings,
        ws_favorite_save,
        ws_favorite_delete,
        ws_generate,
        ws_send,
        ws_plan_delete,
        ws_search,
    ):
        websocket_api.async_register_command(hass, command)

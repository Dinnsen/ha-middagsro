"""Websocket commands used by the REMA 1000 panel."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import functools
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .api import Catalog, RemaError
from .const import DOMAIN
from .coordinator import RemaConfigEntry
from .mealplan import parse_date, plan_summary
from .planedit import (
    async_add_pantry_item,
    async_add_product,
    async_remove_line,
    async_swap_dish,
    async_swap_options,
    pantry_needs,
)
from .schema import vol
from .storage import ALLERGY_OPTIONS, AVOID_OPTIONS, FAVORITE_FREQUENCIES

ENTRY = vol.Optional("entry_id")

type _Handler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]], Awaitable[None]
]


def _entry(hass: HomeAssistant, msg: dict[str, Any]) -> RemaConfigEntry:
    entries: list[RemaConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if entry_id := msg.get("entry_id"):
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_found")
    return entries[0]


def _catalog(cat: Catalog | None) -> dict[str, Any] | None:
    if not cat:
        return None
    return {
        "id": cat.id,
        "label": cat.label,
        "valid_from": cat.valid_from.isoformat() if cat.valid_from else None,
        "valid_to": cat.valid_to.isoformat() if cat.valid_to else None,
    }


def _state(hass: HomeAssistant, entry: RemaConfigEntry) -> dict[str, Any]:
    data = entry.runtime_data
    store = data.store
    offers = data.offers.data
    shopping = data.shopping_list.data

    latest = store.latest_plan
    current = store.plan_covering(dt_util.now().date())
    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "settings": store.settings,
        "favorites": store.favorites,
        "plans": [plan_summary(plan) for plan in store.plans],
        "latest_plan": latest,
        # The plan with tonight's dinner, when it is not the newest one.
        "current_plan": current if current is not latest else None,
        "note": store.note,
        "status": data.planner.status,
        "default_start": data.planner.default_start().isoformat(),
        "ai_entities": [
            {"entity_id": state.entity_id, "name": state.name}
            for state in hass.states.async_all("ai_task")
        ],
        "catalogs": {
            "current": _catalog(offers.current) if offers else None,
            "upcoming": _catalog(offers.upcoming) if offers else None,
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


def _wrap(handler: _Handler) -> _Handler:
    """Turn errors into websocket error messages."""

    @functools.wraps(handler)
    async def wrapper(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
    ) -> None:
        try:
            await handler(hass, connection, msg)
        except (HomeAssistantError, RemaError, ValueError) as err:
            connection.send_error(msg["id"], "rema1000_error", str(err))

    return wrapper


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/state", ENTRY: str, vol.Optional("refresh"): bool}
)
@websocket_api.async_response
@_wrap
async def ws_state(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Everything the panel shows; refresh=True fetches the REMA list first."""
    entry = _entry(hass, msg)
    if msg.get("refresh"):
        await entry.runtime_data.shopping_list.async_refresh()
    connection.send_result(msg["id"], _state(hass, entry))


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/plan", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_plan(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """One full plan."""
    plan = _entry(hass, msg).runtime_data.store.get_plan(msg["plan_id"])
    if plan is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="plan_not_found")
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/settings", ENTRY: str, vol.Required("settings"): dict}
)
@websocket_api.async_response
@_wrap
async def ws_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save settings."""
    entry = _entry(hass, msg)
    settings = await entry.runtime_data.store.async_set_settings(msg["settings"])
    connection.send_result(msg["id"], settings)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/note", ENTRY: str, vol.Required("text"): str}
)
@websocket_api.async_response
@_wrap
async def ws_note(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save the family's wishes for the next plan (empty removes them)."""
    store = _entry(hass, msg).runtime_data.store
    connection.send_result(msg["id"], {"note": await store.async_set_note(msg["text"])})


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/favorite/save", ENTRY: str, vol.Required("favorite"): dict}
)
@websocket_api.async_response
@_wrap
async def ws_favorite_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add or change a favourite dish."""
    store = _entry(hass, msg).runtime_data.store
    connection.send_result(msg["id"], await store.async_save_favorite(msg["favorite"]))


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/favorite/delete", ENTRY: str, vol.Required("favorite_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_favorite_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a favourite dish."""
    await _entry(hass, msg).runtime_data.store.async_delete_favorite(msg["favorite_id"])
    connection.send_result(msg["id"], True)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/generate",
        ENTRY: str,
        vol.Optional("start_date"): vol.Any(str, None),
        vol.Optional("skip_dates"): [str],
    }
)
@websocket_api.async_response
@_wrap
async def ws_generate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Start making a meal plan; skip_dates get no dinner."""
    planner = _entry(hass, msg).runtime_data.planner
    skip = {d for d in (parse_date(v) for v in msg.get("skip_dates") or []) if d}
    planner.async_start_generation(parse_date(msg.get("start_date")), skip=skip)
    connection.send_result(msg["id"], planner.status)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/send",
        ENTRY: str,
        vol.Optional("plan_id"): vol.Any(str, None),
        vol.Optional("part", default="main"): vol.In(["main", "late", "all"]),
    }
)
@websocket_api.async_response
@_wrap
async def ws_send(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send a plan's shopping list to the REMA list."""
    plan = await _entry(hass, msg).runtime_data.planner.async_send(msg.get("plan_id"), msg["part"])
    connection.send_result(msg["id"], {"plan_id": plan["id"], "status": plan["status"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/recipe",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
    }
)
@websocket_api.async_response
@_wrap
async def ws_recipe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Write one day's recipe again."""
    planner = _entry(hass, msg).runtime_data.planner
    day = await planner.async_regenerate_recipe(msg["plan_id"], msg["date"])
    connection.send_result(msg["id"], day)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/plan/delete", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_plan_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a plan from the history."""
    await _entry(hass, msg).runtime_data.store.async_delete_plan(msg["plan_id"])
    connection.send_result(msg["id"], True)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/search", ENTRY: str, vol.Required("query"): str}
)
@websocket_api.async_response
@_wrap
async def ws_search(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Search products (used for weekly must-haves)."""
    client = _entry(hass, msg).runtime_data.client
    products = await client.async_search_products(msg["query"], 10)
    connection.send_result(msg["id"], [p.as_dict() for p in products])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/favorites",
        ENTRY: str,
        vol.Optional("force"): bool,
        vol.Optional("week", default="current"): vol.In(["current", "next"]),
    }
)
@websocket_api.async_response
@_wrap
async def ws_favorites(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The account's favourite products, and those on offer this or next week.

    Until next week's avis is out, next week shows this week's offers
    (fallback=True).
    """
    data = _entry(hass, msg).runtime_data
    force = bool(msg.get("force"))
    products = await data.client.async_get_favorites(force=force)
    catalogs = data.offers.data
    current = catalogs.current if catalogs else None
    upcoming = catalogs.upcoming if catalogs else None
    catalog = upcoming if msg["week"] == "next" else current
    fallback = msg["week"] == "next" and upcoming is None
    if fallback:
        catalog = current
    offers = await data.favorite_offers.async_on_offer(products, catalog, force=force)
    connection.send_result(
        msg["id"],
        {
            "week": msg["week"],
            "fallback": fallback,
            "catalog": _catalog(catalog),
            "products": [p.as_dict() for p in products],
            "on_offer": offers,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/list/add",
        ENTRY: str,
        vol.Required("product_id"): int,
        vol.Optional("amount", default=1): int,
    }
)
@websocket_api.async_response
@_wrap
async def ws_list_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add one product to the primary REMA list."""
    coordinator = _entry(hass, msg).runtime_data.shopping_list
    await coordinator.async_add_items(
        [{"product_id": msg["product_id"], "amount": max(1, min(99, msg["amount"]))}]
    )
    connection.send_result(msg["id"], True)


@websocket_api.websocket_command({vol.Required("type"): "rema1000/list/clear", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_list_clear(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove everything from the primary REMA list."""
    removed = await _entry(hass, msg).runtime_data.shopping_list.async_clear()
    connection.send_result(msg["id"], {"removed": removed})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/swap/options",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
    }
)
@websocket_api.async_response
@_wrap
async def ws_swap_options(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Three other dishes the AI suggests for a day."""
    planner = _entry(hass, msg).runtime_data.planner
    result = await async_swap_options(planner, msg["plan_id"], msg["date"])
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/swap",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
        vol.Required("option"): dict,
    }
)
@websocket_api.async_response
@_wrap
async def ws_swap(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put the chosen dish on the day, with its shopping and recipe."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await async_swap_dish(planner, msg["plan_id"], msg["date"], msg["option"])
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/pantry", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_pantry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The basic items the plan's recipes use, which are not on the shopping list."""
    data = _entry(hass, msg).runtime_data
    plan = data.store.get_plan(msg["plan_id"])
    if plan is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="plan_not_found")
    connection.send_result(msg["id"], pantry_needs(plan, data.store.settings["pantry"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/plan/add",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Exclusive("product_id", "what"): int,
        vol.Exclusive("pantry", "what"): str,
        vol.Optional("amount", default=1): int,
        vol.Optional("part", default="main"): vol.In(["main", "late"]),
    }
)
@websocket_api.async_response
@_wrap
async def ws_plan_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put a searched product, or a basic item the recipes use, on the plan's list."""
    planner = _entry(hass, msg).runtime_data.planner
    if "pantry" in msg:
        line = await async_add_pantry_item(planner, msg["plan_id"], msg["pantry"])
    elif "product_id" in msg:
        line = await async_add_product(
            planner, msg["plan_id"], msg["product_id"], msg["amount"], msg["part"]
        )
    else:
        raise ValueError("product_id or pantry is required")
    connection.send_result(msg["id"], line)


@websocket_api.websocket_command(
    {vol.Required("type"): "rema1000/plan/refresh", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_plan_refresh(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Match the plan's offer items again with REMA's products and prices now."""
    planner = _entry(hass, msg).runtime_data.planner
    connection.send_result(msg["id"], await planner.async_refresh_offers(msg["plan_id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rema1000/plan/remove",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("line_id"): str,
    }
)
@websocket_api.async_response
@_wrap
async def ws_plan_remove(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Take an added item off the plan's list."""
    planner = _entry(hass, msg).runtime_data.planner
    await async_remove_line(planner, msg["plan_id"], msg["line_id"])
    connection.send_result(msg["id"], True)


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the panel's commands."""
    for command in (
        ws_state,
        ws_plan,
        ws_settings,
        ws_note,
        ws_favorite_save,
        ws_favorite_delete,
        ws_generate,
        ws_send,
        ws_recipe,
        ws_plan_delete,
        ws_search,
        ws_favorites,
        ws_list_add,
        ws_list_clear,
        ws_swap_options,
        ws_swap,
        ws_pantry,
        ws_plan_add,
        ws_plan_remove,
        ws_plan_refresh,
    ):
        websocket_api.async_register_command(hass, command)

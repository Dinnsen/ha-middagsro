"""Websocket commands used by the Middagsro panel."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import functools
import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.util import dt as dt_util

from .api import Catalog, RemaError
from .budget import (
    async_book as async_budget_book,
    async_delete as async_purchase_delete,
    async_edit as async_purchase_edit,
    summary as budget_summary,
)
from .chains import (
    CHAINS,
    REMA_ID,
    ChainError,
    async_add_offer,
    async_add_rema_offer,
    async_chain_line,
    async_clear_chain,
    async_compare,
    async_compare_products,
    async_move_line,
    async_search_everywhere,
)
from .const import DOMAIN
from .coordinator import RemaConfigEntry
from .freezer import async_generate as async_generate_freezer, async_portions
from .health import plan_health
from .mealie import MealieError
from .mealplan import ai_choices, parse_date, plan_summary, signal_plans_updated
from .messages import async_danish
from .planedit import (
    async_add_pantry_item,
    async_add_product,
    async_add_text,
    async_clear_day,
    async_edit_line,
    async_move_day,
    async_remove_line,
    async_swap_dish,
    async_swap_options,
    cooked_day,
    pantry_needs,
)
from .recipes import (
    ACTIONS,
    async_delete_recipe,
    async_extract,
    async_import,
    async_rate,
    async_rate_day,
    async_save_recipe,
    async_scan,
    find_recipe,
)
from .rema_recipes import TAGS as REMA_TAGS
from .schema import vol
from .sites import SITES, site_of
from .storage import ALLERGY_OPTIONS, AVOID_OPTIONS, FAVORITE_FREQUENCIES
from .store_client import REMA, REMA_ONLY, rema_only, store_name, store_of
from .watch import (
    async_check as async_watch_check,
    async_deals as async_watch_deals,
    async_own_favorite,
    async_toggle as async_watch_toggle,
    notify_targets,
)

_LOGGER = logging.getLogger(__name__)

ENTRY = vol.Optional("entry_id")
# One-time notes in the panel: the shop can be chosen (2.7.0).
NOTICES = ("store_choice",)

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


def _recipe_summary(recipe: dict[str, Any]) -> dict[str, Any]:
    """A recipe in the collection without its ingredients and steps (those come on request)."""
    return {
        key: recipe.get(key)
        for key in (
            "id",
            "name",
            "type",
            "servings",
            "total_minutes",
            "active_minutes",
            "rating",
            "favorite",
            "source",
            "site",
            "created",
            "times_planned",
            "last_planned",
        )
    } | {"ingredient_names": [i["name"] for i in recipe.get("ingredients") or []][:30]}


def _state(hass: HomeAssistant, entry: RemaConfigEntry) -> dict[str, Any]:
    data = entry.runtime_data
    store = data.store
    offers = data.offers.data
    shop = store_of(entry.data)
    shopping = data.shopping_list.data

    latest = store.latest_plan
    today = dt_util.now().date()
    current = store.plan_covering(today)
    timeline = store.timeline(today, store.settings["start_weekday"])
    shown = {entry["plan_id"] for entry in timeline}
    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "settings": store.settings,
        "favorites": store.favorites,
        "plans": [plan_summary(plan) for plan in store.plans],
        "freezer_plans": [plan_summary(plan) for plan in store.freezer_plans],
        "latest_plan": latest,
        # The plan with tonight's dinner, when it is not the newest one.
        "current_plan": current if current is not latest else None,
        # This week and the coming days as one plan: which plan each date comes from.
        "timeline": timeline,
        "timeline_plans": [
            p for p in store.plans if p["id"] in shown and p is not latest and p is not current
        ],
        "note": store.note,
        "freezer_note": store.freezer_note,
        # When a setting the plans are made from last changed: "Opdater madplan".
        "settings_changed": store.settings_changed or None,
        "recipes": [_recipe_summary(r) for r in store.recipes],
        "watch": store.watch,
        "own_favorites": store.own_favorites,
        # The food budget (budget.py): None when the family keeps none.
        "budget": budget_summary(store),
        "notify_targets": notify_targets(hass),
        "recipe_sites": [{"id": site.id, "name": site.name} for site in SITES.values()],
        # The shop: REMA 1000 (with its login), or another without prices and app.
        "shop": {
            "id": shop,
            "name": store_name(shop),
            "rema": shop == REMA,
            # Bilka has every item's price (its webshop); the others only their offers'.
            "prices": bool(data.client.has_prices),
            **(
                {
                    "bilka_cart": True,
                    "pickup_name": getattr(getattr(data.client, "cart", None), "pickup_name", ""),
                }
                if getattr(data.client, "cart", None) is not None
                else {}
            ),
            "rema_only": rema_only(shop) or list(REMA_ONLY),
        },
        # One-time notes to show (the family closes them once).
        "notices": [n for n in NOTICES if n not in store.seen and (shop == REMA)],
        "status": data.planner.status,
        "default_start": data.planner.default_start().isoformat(),
        "ai_entities": ai_choices(hass),
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
        "mealie": {
            "available": data.planner.mealie.available,
            "url": data.planner.mealie.url,
            "recipes": data.planner.mealie.recipe_url(""),
        },
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
            connection.send_error(msg["id"], "middagsro_error", await _async_danish(hass, err))

    return wrapper


_async_danish = async_danish


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/state", ENTRY: str, vol.Optional("refresh"): bool}
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
    {
        vol.Required("type"): "middagsro/notice_seen",
        ENTRY: str,
        vol.Required("notice"): vol.In(NOTICES),
    }
)
@websocket_api.async_response
@_wrap
async def ws_notice_seen(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """A one-time note in the panel was closed: not shown again."""
    await _entry(hass, msg).runtime_data.store.async_seen(msg["notice"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "middagsro/subscribe", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The same as middagsro/state, now and each time it changes (for the dashboard cards).

    Changes come from the plans and the budget (the planner's signal), the REMA list and
    midnight (a new "tonight"); a burst of them is sent once.
    """
    entry = _entry(hass, msg)
    msg_id = msg["id"]
    pending: list[Any] = []

    @callback
    def send(*_: Any) -> None:
        pending.clear()
        if entry.state is not ConfigEntryState.LOADED:
            # Reloaded (new settings, a new login): the cards subscribe again.
            connection.send_message(websocket_api.event_message(msg_id, {"reload": True}))
            return
        connection.send_message(websocket_api.event_message(msg_id, _state(hass, entry)))

    @callback
    def changed(*_: Any) -> None:
        if not pending:
            pending.append(async_call_later(hass, 0.5, send))

    unsubs = [
        async_dispatcher_connect(hass, signal_plans_updated(entry.entry_id), changed),
        entry.runtime_data.shopping_list.async_add_listener(changed),
        async_track_time_change(hass, changed, hour=0, minute=0, second=10),
    ]

    live = [True]

    @callback
    def unsubscribe() -> None:
        live.clear()
        for unsub in unsubs:
            unsub()
        for cancel in pending:
            cancel()

    @callback
    def unloaded() -> None:
        # The entry is reloaded with a new list and planner: the cards subscribe again.
        if live:
            unsubscribe()
            connection.send_message(websocket_api.event_message(msg_id, {"reload": True}))

    entry.async_on_unload(unloaded)

    connection.subscriptions[msg_id] = unsubscribe
    connection.send_result(msg_id)
    send()


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/plan", ENTRY: str, vol.Required("plan_id"): str}
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
    {vol.Required("type"): "middagsro/settings", ENTRY: str, vol.Required("settings"): dict}
)
@websocket_api.async_response
@_wrap
async def ws_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save settings."""
    entry = _entry(hass, msg)
    settings = await entry.runtime_data.store.async_set_settings(msg["settings"])
    entry.runtime_data.planner._notify()  # the budget's sensors follow
    connection.send_result(msg["id"], settings)


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/note", ENTRY: str, vol.Required("text"): str}
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
    {vol.Required("type"): "middagsro/favorite/save", ENTRY: str, vol.Required("favorite"): dict}
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
    {
        vol.Required("type"): "middagsro/favorite/delete",
        ENTRY: str,
        vol.Required("favorite_id"): str,
    }
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
        vol.Required("type"): "middagsro/generate",
        ENTRY: str,
        vol.Optional("start_date"): vol.Any(str, None),
        vol.Optional("skip_dates"): [str],
        vol.Optional("surprise", default=False): bool,
        # {date: {dish, source: collection|rema|mealie, recipe_id | slug, type}}
        vol.Optional("picks"): {
            str: {
                vol.Required("dish"): str,
                vol.Optional("source"): vol.In(["collection", "rema", "mealie", "web"]),
                vol.Optional("url"): vol.Any(str, None),
                vol.Optional("recipe_id"): vol.Any(str, None),
                vol.Optional("slug"): vol.Any(str, None),
                vol.Optional("type"): vol.Any(str, None),
            }
        },
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
    planner.async_start_generation(
        parse_date(msg.get("start_date")),
        skip=skip,
        surprise=msg["surprise"],
        picks=msg.get("picks"),
    )
    connection.send_result(msg["id"], planner.status)


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/plan/update", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_plan_update(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update a plan to the changed settings (in the background, like a new plan)."""
    planner = _entry(hass, msg).runtime_data.planner
    planner.async_start_update(msg["plan_id"])
    connection.send_result(msg["id"], planner.status)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/send",
        ENTRY: str,
        vol.Optional("plan_id"): vol.Any(str, None),
        vol.Optional("part", default="main"): vol.In(["main", "late", "all"]),
        vol.Optional("line_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
@_wrap
async def ws_send(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send a plan's shopping list (or one line of it) to the REMA list."""
    plan = await _entry(hass, msg).runtime_data.planner.async_send(
        msg.get("plan_id"), msg["part"], msg.get("line_id")
    )
    connection.send_result(msg["id"], {"plan_id": plan["id"], "status": plan["status"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/freezer/generate",
        ENTRY: str,
        vol.Required("count"): vol.In([4, 5]),
        vol.Optional("note"): vol.All(str, vol.Length(max=2000)),
    }
)
@websocket_api.async_response
@_wrap
async def ws_freezer_generate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Generate in the background, just as weekly plans do."""
    planner = _entry(hass, msg).runtime_data.planner
    if planner.generating:
        raise ValueError("En plan er allerede ved at blive lavet.")
    if not planner.ai_available():
        raise ValueError("Vælg en AI-opgave under Indstillinger først.")
    planner._set_status("generating", "Laver fryserplan …")

    async def generate() -> None:
        try:
            await async_generate_freezer(planner, msg["count"], msg.get("note"))
        except Exception as err:  # match the weekly background task's error reporting
            if isinstance(err, ValueError) or getattr(err, "translation_key", "") in (
                "ai_no_credit",
                "ai_busy",
                "ai_key_failed",
            ):
                # The AI service said no, or its answer was not a usable plan.
                _LOGGER.warning("Could not make a freezer plan: %s", err.__cause__ or err)
            else:
                _LOGGER.exception("Could not make a freezer plan")
            planner._set_status("error", await async_danish(hass, err) or err.__class__.__name__)
        else:
            planner._set_status("idle")

    planner._task = hass.async_create_background_task(generate(), name="middagsro freezer plan")
    connection.send_result(msg["id"], planner.status)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/freezer/portions",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
        vol.Required("portions"): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    }
)
@websocket_api.async_response
@_wrap
async def ws_freezer_portions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Scale a single dish and update the shared list."""
    plan = await async_portions(
        _entry(hass, msg).runtime_data.planner, msg["plan_id"], msg["date"], msg["portions"]
    )
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/send/restore",
        ENTRY: str,
        vol.Optional("plan_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
@_wrap
async def ws_send_restore(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put the items sent last back on the family's list."""
    plan = await _entry(hass, msg).runtime_data.planner.async_restore_sent(msg.get("plan_id"))
    connection.send_result(msg["id"], {"plan_id": plan["id"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/recipe",
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
    {vol.Required("type"): "middagsro/plan/delete", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_plan_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a plan from the history."""
    data = _entry(hass, msg).runtime_data
    await data.store.async_delete_plan(msg["plan_id"])
    data.planner._notify()  # the sensors and calendar show the plan before it
    connection.send_result(msg["id"], True)


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/search", ENTRY: str, vol.Required("query"): str}
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
        vol.Required("type"): "middagsro/favorites",
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
    # The family's own favourites (added in Middagsro), after the app's hearts.
    hearts = {p.id for p in products}
    own_ids = [p["id"] for p in data.store.own_favorites if p["id"] not in hearts]
    own: set[int] = set()
    if own_ids:
        try:
            extra = await data.client.async_get_products(own_ids)
        except RemaError:
            extra = []
        products = [*products, *extra]
        own = {p.id for p in extra}
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
            "products": [{**p.as_dict(), "own": p.id in own} for p in products],
            "on_offer": offers,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/list/add",
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


@websocket_api.websocket_command({vol.Required("type"): "middagsro/list/clear", ENTRY: str})
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
        vol.Required("type"): "middagsro/swap/options",
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
        vol.Required("type"): "middagsro/swap",
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
    {vol.Required("type"): "middagsro/pantry", ENTRY: str, vol.Required("plan_id"): str}
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
        vol.Required("type"): "middagsro/plan/add",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Exclusive("product_id", "what"): int,
        vol.Exclusive("pantry", "what"): str,
        vol.Exclusive("name", "what"): str,
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
    elif "name" in msg:
        line = await async_add_text(
            planner, msg["plan_id"], msg["name"], msg["amount"], msg["part"]
        )
    else:
        raise ValueError("product_id, pantry or name is required")
    connection.send_result(msg["id"], line)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/plan/refresh",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Optional("unmatched", default=False): bool,
    }
)
@websocket_api.async_response
@_wrap
async def ws_plan_refresh(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Match the plan's offer items again with REMA's products and prices now."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await (
        planner.async_rematch_missing(msg["plan_id"])
        if msg["unmatched"]
        else planner.async_refresh_offers(msg["plan_id"])
    )
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/plan/remove",
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/day/clear",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
        vol.Optional("skip", default=False): bool,
    }
)
@websocket_api.async_response
@_wrap
async def ws_day_clear(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a day's dish, or skip the day (no dinner at home)."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await async_clear_day(planner, msg["plan_id"], msg["date"], skip=msg["skip"])
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/day/move",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
        vol.Required("direction"): vol.In(["up", "down"]),
    }
)
@websocket_api.async_response
@_wrap
async def ws_day_move(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Swap a day's dinner with the day before or after."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await async_move_day(planner, msg["plan_id"], msg["date"], msg["direction"])
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/plan/line",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("line_id"): str,
        vol.Optional("delete", default=False): bool,
        vol.Optional("packages"): vol.Any(int, None),
        vol.Optional("product_id"): vol.Any(int, None),
    }
)
@websocket_api.async_response
@_wrap
async def ws_plan_line(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a shopping item, change how many, or put another product on it."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await async_edit_line(
        planner,
        msg["plan_id"],
        msg["line_id"],
        delete=msg["delete"],
        packages=msg.get("packages"),
        product_id=msg.get("product_id"),
    )
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/health",
        ENTRY: str,
        vol.Optional("plan_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
@_wrap
async def ws_health(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Nutrition, dietary advice and labels for a plan (the newest by default)."""
    data = _entry(hass, msg).runtime_data
    store = data.store
    plan = store.get_plan(msg["plan_id"]) if msg.get("plan_id") else store.latest_plan
    if plan is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_plan")
    ids = [
        int(line["product"]["id"])
        for line in plan.get("shopping") or []
        if isinstance(line.get("product"), dict) and line["product"].get("id")
    ]
    try:
        table = await data.client.async_get_nutrition(ids)
    except RemaError:
        table = {}
    connection.send_result(msg["id"], plan_health(plan, store.settings, table))


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/nutrition", ENTRY: str, vol.Required("product_id"): int}
)
@websocket_api.async_response
@_wrap
async def ws_nutrition(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """REMA's nutrition per 100 g for one product (empty if REMA has none)."""
    client = _entry(hass, msg).runtime_data.client
    table = await client.async_get_nutrition([msg["product_id"]])
    connection.send_result(msg["id"], table.get(msg["product_id"]) or {})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/mealie/save",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
    }
)
@websocket_api.async_response
@_wrap
async def ws_mealie_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save a day's recipe in Mealie (and put it in Mealie's calendar, if switched on)."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = planner.store.get_plan(msg["plan_id"])
    day = next((d for d in plan["days"] if d["date"] == msg["date"]), None) if plan else None
    if plan is None or day is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="day_not_found")
    day = cooked_day(plan, day)
    saved = await planner.mealie.async_save_recipe(day)
    day["mealie"] = saved["slug"]
    await planner.store.async_save()
    await planner.async_mealie_sync(plan)
    connection.send_result(msg["id"], saved)


@websocket_api.websocket_command({vol.Required("type"): "middagsro/mealie/recipes", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_mealie_recipes(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The family's recipes in Mealie (name and slug), to choose a dish for a day."""
    mealie = _entry(hass, msg).runtime_data.planner.mealie
    try:
        summaries = await mealie.async_summaries()
    except MealieError as err:
        raise HomeAssistantError(f"Mealie: {err}") from err
    connection.send_result(
        msg["id"],
        {"recipes": [{"slug": r["slug"], "name": r.get("name") or r["slug"]} for r in summaries]},
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/mealie/sync", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_mealie_sync(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put a plan's dinners in Mealie's calendar now."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = planner.store.get_plan(msg["plan_id"])
    if plan is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="plan_not_found")
    count = await planner.async_mealie_sync(plan, force=True)
    connection.send_result(msg["id"], {"count": count})


# ------------------------------------------------------------------ recipe collection


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/recipes/get", ENTRY: str, vol.Required("recipe_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_recipe_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """One recipe in the collection, with ingredients and steps."""
    store = _entry(hass, msg).runtime_data.store
    recipe = find_recipe(store, msg["recipe_id"])
    if recipe is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="recipe_not_found")
    connection.send_result(msg["id"], recipe)


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/recipes/save", ENTRY: str, vol.Required("recipe"): dict}
)
@websocket_api.async_response
@_wrap
async def ws_recipe_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a recipe to the collection, or save changes to one."""
    data = _entry(hass, msg).runtime_data
    recipe = await async_save_recipe(data.store, msg["recipe"])
    data.planner._notify()
    connection.send_result(msg["id"], recipe)


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/recipes/delete", ENTRY: str, vol.Required("recipe_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_recipe_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a recipe from the collection."""
    data = _entry(hass, msg).runtime_data
    await async_delete_recipe(data.store, msg["recipe_id"])
    data.planner._notify()
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/recipes/rate",
        ENTRY: str,
        vol.Required("recipe_id"): str,
        vol.Required("action"): vol.In(ACTIONS),
    }
)
@websocket_api.async_response
@_wrap
async def ws_recipe_rate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """👍, 👎 or ❤️ a recipe (pressing again takes it back)."""
    data = _entry(hass, msg).runtime_data
    recipe = await async_rate(data.store, msg["recipe_id"], msg["action"])
    data.planner._notify()
    connection.send_result(msg["id"], recipe)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/recipes/rate_day",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
        vol.Required("action"): vol.In(ACTIONS),
    }
)
@websocket_api.async_response
@_wrap
async def ws_recipe_rate_day(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """👍, 👎 or ❤️ a dinner in a plan: it goes in the recipe collection."""
    planner = _entry(hass, msg).runtime_data.planner
    recipe = await async_rate_day(planner, msg["plan_id"], msg["date"], msg["action"])
    connection.send_result(msg["id"], recipe)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/sites/search",
        ENTRY: str,
        vol.Required("query"): str,
        # Other sites than the chosen ones (to try a site before choosing it).
        vol.Optional("sites"): [vol.In(SITES)],
    }
)
@websocket_api.async_response
@_wrap
async def ws_sites_search(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Search the family's recipe sites."""
    planner = _entry(hass, msg).runtime_data.planner
    sites = msg.get("sites") or planner.store.settings["recipe_sites"]
    results = await planner.sites.async_search(sites, msg["query"]) if sites else []
    connection.send_result(msg["id"], {"results": results})


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/sites/recipe", ENTRY: str, vol.Required("url"): str}
)
@websocket_api.async_response
@_wrap
async def ws_sites_recipe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """A recipe from one of the sites, to look over and save (not saved yet)."""
    planner = _entry(hass, msg).runtime_data.planner
    if site_of(msg["url"]) is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="recipe_bad_link")
    recipe = await planner.sites.async_recipe(msg["url"], lambda page: async_extract(planner, page))
    if recipe is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="recipe_not_on_page"
        )
    connection.send_result(msg["id"], recipe)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/recipes/scan",
        ENTRY: str,
        vol.Required("photos"): vol.All([str], vol.Length(min=1, max=4)),
    }
)
@websocket_api.async_response
@_wrap
async def ws_recipe_scan(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Read the recipe in photos of cookbook pages; saved when the family has looked it over."""
    planner = _entry(hass, msg).runtime_data.planner
    connection.send_result(msg["id"], await async_scan(planner, msg["photos"]))


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/recipes/import", ENTRY: str, vol.Required("url"): str}
)
@websocket_api.async_response
@_wrap
async def ws_recipe_import(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Read the recipe behind a link; it is saved when the family has looked it over."""
    planner = _entry(hass, msg).runtime_data.planner
    connection.send_result(msg["id"], await async_import(planner, msg["url"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/recipes/plan",
        ENTRY: str,
        vol.Required("recipe_id"): str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
    }
)
@websocket_api.async_response
@_wrap
async def ws_recipe_plan(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put a recipe from the collection on a day of a plan (its items go on the list)."""
    planner = _entry(hass, msg).runtime_data.planner
    recipe = find_recipe(planner.store, msg["recipe_id"])
    if recipe is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="recipe_not_found")
    option = {
        "dish": recipe["name"],
        "type": recipe["type"],
        "active_minutes": recipe["active_minutes"],
        "total_minutes": recipe["total_minutes"],
        "recipe_id": recipe["id"],
    }
    plan = await async_swap_dish(planner, msg["plan_id"], msg["date"], option)
    connection.send_result(msg["id"], plan)


# ------------------------------------------------------------------ other chains


@websocket_api.websocket_command({vol.Required("type"): "middagsro/chains", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_chains(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The chains that can be chosen, with their logos."""
    planner = _entry(hass, msg).runtime_data.planner
    dealers = await planner.chains.async_dealers()
    connection.send_result(msg["id"], {"chains": list(dealers.values())})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/chains/offers",
        ENTRY: str,
        vol.Required("dealer_id"): vol.In([REMA_ID, *CHAINS]),
        vol.Optional("force", default=False): bool,
    }
)
@websocket_api.async_response
@_wrap
async def ws_chain_offers(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """A chain's food offers."""
    planner = _entry(hass, msg).runtime_data.planner
    try:
        offers = await planner.chains.async_offers(msg["dealer_id"], msg["force"])
    except ChainError as err:
        raise HomeAssistantError(str(err)) from err
    connection.send_result(msg["id"], {"dealer_id": msg["dealer_id"], "offers": offers})


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/chains/compare", ENTRY: str, vol.Required("plan_id"): str}
)
@websocket_api.async_response
@_wrap
async def ws_chain_compare(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Where the plan's items are cheaper than at REMA this week."""
    planner = _entry(hass, msg).runtime_data.planner
    connection.send_result(msg["id"], await async_compare(planner, msg["plan_id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/chains/products",
        ENTRY: str,
        vol.Required("products"): [dict],
        vol.Optional("date"): vol.Any(None, str),
    }
)
@websocket_api.async_response
@_wrap
async def ws_chain_products(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Which of some REMA products are cheaper in another chain on a day (default today)."""
    planner = _entry(hass, msg).runtime_data.planner
    day = parse_date(msg.get("date")) or dt_util.now().date()
    found = await async_compare_products(planner, msg["products"], day)
    connection.send_result(msg["id"], {"products": found})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/chains/move",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("line_id"): str,
        vol.Required("dealer_id"): vol.Any(None, vol.In(list(CHAINS))),
        vol.Optional("price"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("heading"): vol.Any(None, str),
    }
)
@websocket_api.async_response
@_wrap
async def ws_chain_move(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Buy an item in another shop instead (or back at REMA)."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await async_move_line(
        planner,
        msg["plan_id"],
        msg["line_id"],
        msg["dealer_id"],
        msg.get("price"),
        msg.get("heading"),
    )
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/chains/add",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("offer"): dict,
    }
)
@websocket_api.async_response
@_wrap
async def ws_chain_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put another chain's offer on that shop's list."""
    planner = _entry(hass, msg).runtime_data.planner
    connection.send_result(msg["id"], await async_add_offer(planner, msg["plan_id"], msg["offer"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/chains/line",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("line_id"): str,
        vol.Optional("bought"): bool,
        vol.Optional("packages"): vol.All(int, vol.Range(min=1, max=99)),
        vol.Optional("delete", default=False): bool,
    }
)
@websocket_api.async_response
@_wrap
async def ws_chain_line(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Tick off, change how many or delete an item on a shop's list."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await async_chain_line(
        planner,
        msg["plan_id"],
        msg["line_id"],
        bought=msg.get("bought"),
        packages=msg.get("packages"),
        delete=msg["delete"],
    )
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/chains/clear",
        ENTRY: str,
        vol.Required("plan_id"): str,
        vol.Required("dealer_id"): vol.In(list(CHAINS)),
    }
)
@websocket_api.async_response
@_wrap
async def ws_chain_clear(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Empty a shop's basket: the ticked-off items are bought."""
    planner = _entry(hass, msg).runtime_data.planner
    plan = await async_clear_chain(planner, msg["plan_id"], msg["dealer_id"])
    connection.send_result(msg["id"], plan)


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/search/everywhere", ENTRY: str, vol.Required("query"): str}
)
@websocket_api.async_response
@_wrap
async def ws_search_everywhere(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """A product at REMA and in the chosen chains' offers, cheapest marked."""
    planner = _entry(hass, msg).runtime_data.planner
    connection.send_result(msg["id"], await async_search_everywhere(planner, msg["query"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/chains/rema_add",
        ENTRY: str,
        vol.Required("offer"): dict,
        vol.Optional("plan_id"): vol.Any(None, str),
    }
)
@websocket_api.async_response
@_wrap
async def ws_rema_offer_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put an offer from REMA's avis on the plan's list (or the REMA list)."""
    planner = _entry(hass, msg).runtime_data.planner
    result = await async_add_rema_offer(planner, msg["offer"], msg.get("plan_id"))
    connection.send_result(msg["id"], result)


# ------------------------------------------------------------------ watch list


@websocket_api.websocket_command({vol.Required("type"): "middagsro/watch", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_watch(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The watch list with the offers in REMA and the chosen chains."""
    data = _entry(hass, msg).runtime_data
    connection.send_result(
        msg["id"],
        {
            "items": await async_watch_deals(data.planner),
            "notify": data.store.settings["watch_notify"],
            "targets": notify_targets(hass),
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/watch/toggle", ENTRY: str, vol.Required("item"): dict}
)
@websocket_api.async_response
@_wrap
async def ws_watch_toggle(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Watch a product or a text, or stop watching it."""
    store = _entry(hass, msg).runtime_data.store
    watched = await async_watch_toggle(store, msg["item"])
    connection.send_result(msg["id"], {"watched": watched, "watch": store.watch})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/favorites/own",
        ENTRY: str,
        vol.Required("product"): dict,
        vol.Optional("add", default=True): bool,
    }
)
@websocket_api.async_response
@_wrap
async def ws_own_favorite(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a REMA product to the family's own favourites, or remove it."""
    store = _entry(hass, msg).runtime_data.store
    connection.send_result(msg["id"], await async_own_favorite(store, msg["product"], msg["add"]))


@websocket_api.websocket_command({vol.Required("type"): "middagsro/watch/check", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_watch_check(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Look for watched items on offer now, and tell about the new ones."""
    told = await async_watch_check(_entry(hass, msg).runtime_data.planner)
    connection.send_result(msg["id"], {"told": told})


# ------------------------------------------------------------------ REMA's recipes


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/rema_recipes/list",
        ENTRY: str,
        vol.Optional("tag"): vol.Any(str, None),
        vol.Optional("sort", default="popular"): vol.In(["popular", "newest"]),
        vol.Optional("page", default=1): vol.All(int, vol.Range(min=1, max=100)),
        vol.Optional("query"): vol.Any(str, None),
    }
)
@websocket_api.async_response
@_wrap
async def ws_rema_recipes(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """A page of REMA 1000's recipes: in a category, all of them, or a search."""
    planner = _entry(hass, msg).runtime_data.planner
    result = await planner.rema_recipes.async_list(
        msg.get("tag"), msg["sort"], msg["page"], msg.get("query")
    )
    connection.send_result(msg["id"], {**result, "tags": REMA_TAGS})


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/rema_recipes/get", ENTRY: str, vol.Required("slug"): str}
)
@websocket_api.async_response
@_wrap
async def ws_rema_recipe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """One of REMA's recipes, ready to look over and save (not saved yet)."""
    planner = _entry(hass, msg).runtime_data.planner
    connection.send_result(msg["id"], await planner.rema_recipes.async_get(msg["slug"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/rema_recipes/plan",
        ENTRY: str,
        vol.Required("slug"): str,
        vol.Required("plan_id"): str,
        vol.Required("date"): str,
    }
)
@websocket_api.async_response
@_wrap
async def ws_rema_recipe_plan(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put a REMA recipe on a day: it is saved in the collection, and its items go on the list."""
    planner = _entry(hass, msg).runtime_data.planner
    recipe = await async_save_recipe(
        planner.store, await planner.rema_recipes.async_get(msg["slug"])
    )
    option = {
        "dish": recipe["name"],
        "type": recipe["type"],
        "active_minutes": recipe["active_minutes"],
        "total_minutes": recipe["total_minutes"],
        "recipe_id": recipe["id"],
    }
    plan = await async_swap_dish(planner, msg["plan_id"], msg["date"], option)
    connection.send_result(msg["id"], plan)


@callback
# ------------------------------------------------------------------ the food budget


@websocket_api.websocket_command({vol.Required("type"): "middagsro/budget", ENTRY: str})
@websocket_api.async_response
@_wrap
async def ws_budget(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The food budget: the week, the month, the weeks and the year, and the purchases."""
    connection.send_result(msg["id"], budget_summary(_entry(hass, msg).runtime_data.store))


_PURCHASE: dict[Any, Any] = {
    vol.Optional("amount"): vol.Any(int, float, str),
    vol.Optional("date"): vol.Any(str, None),
    vol.Optional("store"): vol.Any(str, None),
    vol.Optional("note"): vol.Any(str, None),
}


@websocket_api.websocket_command(
    {vol.Required("type"): "middagsro/purchases/add", ENTRY: str, **_PURCHASE}
)
@websocket_api.async_response
@_wrap
async def ws_purchase_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Book a purchase against the food budget."""
    planner = _entry(hass, msg).runtime_data.planner
    raw = {key: msg[key] for key in ("amount", "date", "store", "note") if msg.get(key) is not None}
    connection.send_result(msg["id"], await async_budget_book(planner, raw))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/purchases/edit",
        ENTRY: str,
        vol.Required("purchase_id"): str,
        **_PURCHASE,
    }
)
@websocket_api.async_response
@_wrap
async def ws_purchase_edit(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Change a purchase."""
    data = _entry(hass, msg).runtime_data
    raw = {key: msg[key] for key in ("amount", "date", "store", "note") if msg.get(key) is not None}
    await async_purchase_edit(data.store, msg["purchase_id"], raw)
    data.planner._notify()
    connection.send_result(msg["id"], budget_summary(data.store))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "middagsro/purchases/delete",
        ENTRY: str,
        vol.Required("purchase_id"): str,
    }
)
@websocket_api.async_response
@_wrap
async def ws_purchase_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove a purchase."""
    data = _entry(hass, msg).runtime_data
    await async_purchase_delete(data.store, msg["purchase_id"])
    data.planner._notify()
    connection.send_result(msg["id"], budget_summary(data.store))


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the panel's commands."""
    for command in (
        ws_state,
        ws_notice_seen,
        ws_plan,
        ws_settings,
        ws_note,
        ws_favorite_save,
        ws_favorite_delete,
        ws_generate,
        ws_plan_update,
        ws_freezer_generate,
        ws_freezer_portions,
        ws_send,
        ws_send_restore,
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
        ws_day_clear,
        ws_day_move,
        ws_recipe_scan,
        ws_sites_search,
        ws_sites_recipe,
        ws_mealie_recipes,
        ws_plan_line,
        ws_health,
        ws_nutrition,
        ws_mealie_save,
        ws_mealie_sync,
        ws_recipe_get,
        ws_recipe_save,
        ws_recipe_delete,
        ws_recipe_rate,
        ws_recipe_rate_day,
        ws_recipe_import,
        ws_recipe_plan,
        ws_chains,
        ws_chain_offers,
        ws_chain_compare,
        ws_chain_products,
        ws_chain_move,
        ws_chain_add,
        ws_chain_line,
        ws_chain_clear,
        ws_search_everywhere,
        ws_rema_offer_add,
        ws_rema_recipes,
        ws_rema_recipe,
        ws_watch,
        ws_watch_toggle,
        ws_own_favorite,
        ws_watch_check,
        ws_rema_recipe_plan,
        ws_budget,
        ws_purchase_add,
        ws_purchase_edit,
        ws_purchase_delete,
        ws_subscribe,
    ):
        websocket_api.async_register_command(hass, command)

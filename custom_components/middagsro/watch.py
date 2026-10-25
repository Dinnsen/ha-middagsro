"""The family's watch list: products and words, and their offers in REMA and the chosen chains.

A watched REMA product is on offer when REMA prices it as an offer (now, or from next
week's avis), and in another chain when an offer there is the same kind of product.
A watched text ("Merrild kaffe", or something REMA doesn't sell) is on offer wherever an
avis offer has all its words. When something new comes on offer, the family can be told
with a notification.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .api import Product, RemaError, parse_time
from .chains import CHAINS, REMA_ID, ChainError, _same_kind, as_offer, query_words, text_has
from .const import DOMAIN

if TYPE_CHECKING:
    from .mealplan import MealPlanner
    from .storage import RemaPlanStore

_LOGGER = logging.getLogger(__name__)

MAX_WATCH = 100
MAX_OWN_FAVORITES = 200
CHECK_EVERY = timedelta(hours=3)
PANEL_PATH = "/middagsro"


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def chain_name(dealer_id: str) -> str:
    """REMA 1000, Netto, Lidl …"""
    return "REMA 1000" if dealer_id == REMA_ID else CHAINS.get(dealer_id, dealer_id)


def _image(value: Any) -> str | None:
    return value if isinstance(value, str) and value.startswith("https://") else None


def clean_item(raw: Any) -> dict[str, Any] | None:
    """A watched REMA product ({product_id, name …}) or a text ({text})."""
    if not isinstance(raw, dict):
        return None
    product_id = raw.get("product_id", raw.get("id"))
    product_id = product_id if isinstance(product_id, int) and product_id > 0 else None
    text = " ".join(str(raw.get("text") or raw.get("name") or "").split())[:120]
    if not text:
        return None
    key = f"p{product_id}" if product_id else "t" + text.lower()
    return {
        "key": key,
        "product_id": product_id,
        "text": text,
        "underline": str(raw.get("underline") or "")[:120],
        "image": _image(raw.get("image")),
        "is_organic": bool(raw.get("is_organic")),
    }


async def async_toggle(store: RemaPlanStore, raw: Any) -> bool:
    """Watch a product or a text, or stop watching it. Returns whether it is watched now."""
    item = clean_item(raw)
    if item is None:
        raise _invalid("watch_item_required")
    before = len(store.watch)
    store.watch = [w for w in store.watch if w.get("key") != item["key"]]
    watched = len(store.watch) == before
    if watched:
        if len(store.watch) >= MAX_WATCH:
            raise _invalid("too_many_watched", limit=str(MAX_WATCH))
        store.watch.insert(0, item)
    await store.async_save()
    return watched


async def async_own_favorite(store: RemaPlanStore, raw: Any, add: bool) -> list[dict[str, Any]]:
    """Add a REMA product to the family's own favourites (next to the app's hearts), or remove it."""
    item = clean_item(raw)
    if item is None or item["product_id"] is None:
        raise _invalid("watch_item_required")
    store.own_favorites = [p for p in store.own_favorites if p.get("id") != item["product_id"]]
    if add:
        if len(store.own_favorites) >= MAX_OWN_FAVORITES:
            raise _invalid("too_many_watched", limit=str(MAX_OWN_FAVORITES))
        store.own_favorites.insert(
            0,
            {
                "id": item["product_id"],
                "name": item["text"],
                "underline": item["underline"],
                "image": item["image"],
            },
        )
    await store.async_save()
    return store.own_favorites


def _rema_deal(product: Product, now: datetime) -> dict[str, Any] | None:
    """REMA's own offer on a product: now, or the coming one from the next avis."""
    base = {
        "source": "rema",
        "dealer_id": REMA_ID,
        "heading": product.name,
        "underline": product.underline,
        "product_id": product.id,
        "image": product.image,
    }
    cheaper = (
        product.price is not None
        and product.normal_price is not None
        and (product.price < product.normal_price - 0.01)
    )
    if product.is_advertised or product.is_campaign or cheaper:
        return {
            **base,
            "price": product.price,
            "normal_price": product.normal_price,
            "valid_from": None,
            "valid_to": product.price_valid_to,
        }
    start = parse_time(product.upcoming_from)
    if (
        product.upcoming_is_advertised
        and product.upcoming_price is not None
        and start
        and start > now
    ):
        return {
            **base,
            "price": product.upcoming_price,
            "normal_price": product.price,
            "valid_from": product.upcoming_from,
            "valid_to": None,
        }
    return None


def _offer_deal(offer: dict[str, Any], dealer_id: str) -> dict[str, Any]:
    return {
        "source": "rema_avis" if dealer_id == REMA_ID else "chain",
        "dealer_id": dealer_id,
        "heading": offer.get("heading"),
        "underline": offer.get("description") or offer.get("quantity"),
        "price": offer.get("price"),
        "normal_price": offer.get("pre_price"),
        "valid_from": offer.get("valid_from"),
        "valid_to": offer.get("valid_to"),
        "image": offer.get("image"),
        "offer": offer,
    }


def _fits_kind(kind: dict[str, Any], offer: dict[str, Any]) -> bool:
    return _same_kind(kind, as_offer(offer))


def _fits_words(words: list[str], offer: dict[str, Any]) -> bool:
    return text_has(words, f"{offer.get('heading')} {offer.get('description') or ''}")


def _offer_price(offer: dict[str, Any]) -> float:
    price = offer.get("price")
    return float(price) if isinstance(price, int | float) else 1e9


def _current(offer: dict[str, Any], now: datetime) -> bool:
    end = parse_time(offer.get("valid_to"))
    return end is None or end >= now


async def async_deals(planner: MealPlanner) -> list[dict[str, Any]]:
    """Every watched item with its offers: REMA first, then the chains, cheapest first."""
    store = planner.store
    items = list(store.watch)
    if not items:
        return []
    now = dt_util.utcnow()
    ids = [w["product_id"] for w in items if w.get("product_id")]
    products: dict[int, Product] = {}
    if ids:
        try:
            products = {p.id: p for p in await planner.client.async_get_products(ids)}
        except RemaError as err:
            _LOGGER.debug("Watched products not read: %s", err)
    # The family's own shop first (REMA 1000, or the shop chosen instead), then the chains.
    own = planner.dealer_id
    dealers = [own] + [d for d in store.settings["chains"] if d in CHAINS and d != own]
    offers: dict[str, list[dict[str, Any]]] = {}
    for dealer_id in dealers:
        try:
            offers[dealer_id] = [
                o for o in await planner.chains.async_offers(dealer_id) if _current(o, now)
            ]
        except ChainError as err:
            _LOGGER.debug("Offers of %s not read: %s", dealer_id, err)
            offers[dealer_id] = []

    # Matching every item against every offer is plain CPU work: not on the event loop.
    return await planner.hass.async_add_executor_job(_match, items, products, offers, dealers, now)


def _match(
    items: list[dict[str, Any]],
    products: dict[int, Product],
    offers: dict[str, list[dict[str, Any]]],
    dealers: list[str],
    now: datetime,
) -> list[dict[str, Any]]:
    out = []
    for item in items:
        deals: list[dict[str, Any]] = []
        fits: Callable[[dict[str, Any]], bool]
        product = products.get(item["product_id"]) if item.get("product_id") else None
        if item.get("product_id"):
            kind = {"name": item["text"], "is_organic": item.get("is_organic")}
            if product is not None:
                kind["department"] = product.department
            fits = partial(_fits_kind, kind)
            if product is not None and (deal := _rema_deal(product, now)):
                deals.append(deal)
                searched = [d for d in dealers if d != REMA_ID]  # REMA: its own price
            else:
                # REMA shows an offer's price only once it runs: until then, its avis.
                searched = dealers
        else:
            fits = partial(_fits_words, query_words(item["text"]))
            searched = dealers
        for dealer_id in searched:
            found = [o for o in offers.get(dealer_id, []) if fits(o)]
            if found:
                best = min(found, key=_offer_price)
                deals.append(_offer_deal(best, dealer_id))
        out.append(
            {
                **item,
                "price": product.price if product else None,
                "image": item.get("image") or (product.image if product else None),
                "deals": deals,
            }
        )
    return out


# ------------------------------------------------------------------ notifications


def _deal_key(item: dict[str, Any], deal: dict[str, Any]) -> str:
    return "|".join(
        str(part or "")
        for part in (item["key"], deal["dealer_id"], deal.get("valid_from"), deal.get("valid_to"))
    )


def _day(value: Any) -> str:
    moment = parse_time(value)
    if moment is None:
        return ""
    day = dt_util.as_local(moment).date()
    return f"{day.day}/{day.month}"


def _price(value: Any) -> str:
    return f"{float(value):.2f}".replace(".", ",") + " kr." if value is not None else ""


def deal_line(deal: dict[str, Any]) -> str:
    """The offer as one line, e.g. 'REMA 1000: LETMÆLK 1,5% - 9,95 kr. til 24/10' with an icon."""
    icon = "🛒" if deal["dealer_id"] == REMA_ID else "🏷️"
    text = f"{icon} {chain_name(deal['dealer_id'])}: {deal['heading']}"
    if deal.get("price") is not None:
        text += f" – {_price(deal['price'])}"
    if (
        deal.get("normal_price")
        and deal.get("price") is not None
        and deal["normal_price"] > deal["price"]
    ):
        text += f" (før {_price(deal['normal_price'])})"
    if (
        deal.get("valid_from")
        and (start := parse_time(deal["valid_from"]))
        and start > dt_util.utcnow()
    ):
        text += f" fra {_day(deal['valid_from'])}"
    elif deal.get("valid_to"):
        text += f" til {_day(deal['valid_to'])}"
    return text


async def _async_notify(
    hass: HomeAssistant, target: str, item: dict[str, Any], deals: list[dict[str, Any]]
) -> None:
    title = f"🔔 {item['text']} er på tilbud"
    message = "\n".join(deal_line(d) for d in deals)
    if target == "persistent_notification":
        slug = re.sub(r"\W+", "_", item["key"])
        persistent_notification.async_create(
            hass, message, title, notification_id=f"{DOMAIN}_watch_{slug}"
        )
        return
    data: dict[str, Any] = {
        # Tapping it opens Middagsro (iOS: url, Android: clickAction), with an icon and photo.
        "url": PANEL_PATH,
        "clickAction": PANEL_PATH,
        "notification_icon": "mdi:tag-heart",
        "group": f"{DOMAIN}-watch",
        "tag": f"{DOMAIN}-{item['key']}",
    }
    image = item.get("image") or next((d.get("image") for d in deals if d.get("image")), None)
    if image:
        data["image"] = image
    await hass.services.async_call(
        "notify",
        target.removeprefix("notify."),
        {"title": title, "message": message, "data": data},
        blocking=True,
    )


_checking: set[str] = set()


async def async_check(planner: MealPlanner) -> int:
    """Tell about watched items that came on offer since last time. Returns how many.

    One check at a time per account (the timer and "check now" can overlap), so
    nothing is told twice.
    """
    store = planner.store
    target = store.settings.get("watch_notify")
    if not target or not store.watch or planner.entry_id in _checking:
        return 0
    _checking.add(planner.entry_id)
    try:
        return await _async_check(planner, target)
    finally:
        _checking.discard(planner.entry_id)


async def _async_check(planner: MealPlanner, target: str) -> int:
    store = planner.store
    now = dt_util.utcnow()
    # Offers that have ended can be told about again when they come back.
    before = len(store.watch_sent)
    store.watch_sent = {
        key: until
        for key, until in store.watch_sent.items()
        if (end := parse_time(until)) is None or end >= now
    }
    changed = len(store.watch_sent) != before
    told = 0
    for item in await async_deals(planner):
        new = [d for d in item["deals"] if _deal_key(item, d) not in store.watch_sent]
        if not new:
            continue
        try:
            await _async_notify(planner.hass, target, item, new)
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("Could not send the notification for %s: %s", item["text"], err)
            continue
        for deal in new:
            until = deal.get("valid_to") or (now + timedelta(days=8)).isoformat()
            store.watch_sent[_deal_key(item, deal)] = str(until)
        told += 1
        changed = True
    if changed:
        await store.async_save()
    return told


def notify_targets(hass: HomeAssistant) -> list[dict[str, str]]:
    """Where a notification can go: Home Assistant itself and each notify service."""
    services = sorted(
        name
        for name in hass.services.async_services_for_domain("notify")
        if name not in ("send_message", "persistent_notification")
    )
    return [{"id": "persistent_notification", "name": "Home Assistant (notifikation i HA)"}] + [
        {"id": f"notify.{name}", "name": name.replace("mobile_app_", "📱 ").replace("_", " ")}
        for name in services
    ]

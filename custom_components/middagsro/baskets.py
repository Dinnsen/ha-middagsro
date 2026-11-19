"""The week's list in the other installed webshops: what it costs there, and over.

REMA 1000 stays the plan's shop. When Nemlig.com or Bilka ToGo is set up too (as
its own Middagsro entry), the plan's lines are searched there with the account's
own prices, and the found products can be put in that shop's basket. Middagsro
never chooses a delivery time and never orders: the family finishes in the shop.

The fees (delivery, packing) depend on the family's choices in the shop, so the
panel adds them; this only sums the goods.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from .bilka import BILKA_ID
from .const import DOMAIN
from .nemlig import NEMLIG_ID
from .store_client import store_name, store_of

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import RemaConfigEntry

WEBSHOPS = (NEMLIG_ID, BILKA_ID)
_CONCURRENCY = 4
_MAX_LINES = 60


def webshop_entries(hass: HomeAssistant, entry: RemaConfigEntry) -> list[RemaConfigEntry]:
    """The other installed entries for a webshop with prices and a basket."""
    found: list[RemaConfigEntry] = []
    for other in hass.config_entries.async_loaded_entries(DOMAIN):
        if other.entry_id == entry.entry_id or store_of(other.data) not in WEBSHOPS:
            continue
        client = getattr(other, "runtime_data", None)
        client = getattr(client, "client", None)
        if client is not None and getattr(client, "has_prices", False):
            found.append(other)
    return found


def _lines(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The lines the family buys at the plan's shop (not left out, not elsewhere)."""
    return [
        line
        for line in plan.get("shopping") or []
        if not line.get("skipped") and not line.get("buy_at")
    ][:_MAX_LINES]


def _query(line: dict[str, Any]) -> str:
    return str(line.get("search") or line.get("name") or "").strip()


async def _search_shop(other: RemaConfigEntry, lines: list[dict[str, Any]]) -> dict[str, Any]:
    client = other.runtime_data.client
    cart = getattr(client, "cart", None)
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(line: dict[str, Any]) -> dict[str, Any] | None:
        query = _query(line)
        if not query:
            return None
        async with gate:
            try:
                products = await client.async_search_products(query, 3)
            except Exception:
                return None
        product = next((p for p in products if p.price), None)
        if product is None or product.price is None:
            return None
        packages = max(1, int(line.get("packages") or 1))
        return {
            "line_id": line.get("id"),
            "name": line.get("name"),
            "product": {
                "id": product.id,
                "name": product.name,
                "underline": product.underline,
                "price": product.price,
                "image": product.image,
            },
            "packages": packages,
            "cost": round(product.price * packages, 2),
        }

    results = await asyncio.gather(*(one(line) for line in lines))
    items = [item for item in results if item]
    found = {item["line_id"] for item in items}
    return {
        "entry_id": other.entry_id,
        "store": store_of(other.data),
        "name": store_name(store_of(other.data)),
        "basket": cart is not None,
        "pickup": getattr(cart, "pickup_name", "") or "",
        "items": items,
        "missing": [line.get("name") for line in lines if line.get("id") not in found],
        "total": round(sum(item["cost"] for item in items), 2),
    }


async def async_compare(
    hass: HomeAssistant, entry: RemaConfigEntry, plan: dict[str, Any]
) -> dict[str, Any]:
    """The plan's list here and in each other webshop (goods only, no fees)."""
    lines = _lines(plan)
    own = {
        "entry_id": entry.entry_id,
        "store": store_of(entry.data),
        "name": store_name(store_of(entry.data)),
        "count": len(lines),
        "total": round(sum(line.get("cost") or 0 for line in lines), 2),
        "priced": sum(1 for line in lines if line.get("cost")),
    }
    shops = await asyncio.gather(*(_search_shop(o, lines) for o in webshop_entries(hass, entry)))
    return {"plan_id": plan.get("id"), "own": own, "shops": list(shops)}


async def async_transfer(
    hass: HomeAssistant, entry: RemaConfigEntry, target_id: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Put products in another webshop's basket: at least as many as asked.

    Setting "at least" (not adding) makes a second press harmless.
    """
    target = next((o for o in webshop_entries(hass, entry) if o.entry_id == target_id), None)
    cart = getattr(getattr(target, "runtime_data", None), "client", None)
    cart = getattr(cart, "cart", None)
    if target is None or cart is None:
        raise ValueError("Butikken har ingen kurv at lægge varerne i. Log ind på den først.")
    wanted: dict[int, int] = {}
    for item in items:
        product_id = int(item.get("product_id") or 0)
        if product_id:
            wanted[product_id] = wanted.get(product_id, 0) + max(1, int(item.get("packages") or 1))
    basket = await cart.async_list()
    targets: dict[int, int] = {}
    for product_id, packages in wanted.items():
        have = cart.amount(product_id, basket)
        if have >= packages:
            continue
        targets[product_id] = packages
        await cart.async_set_amount(product_id, packages, verify=False)
    confirmed = await cart.async_confirm(targets) if targets else set()
    already = len(wanted) - len(targets)
    return {
        "store": store_name(store_of(target.data)),
        "added": len(confirmed),
        "already": already,
        "failed": [pid for pid in targets if pid not in confirmed],
    }

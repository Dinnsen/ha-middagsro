"""The shops a plan's items are found in, as the matcher sees them.

The family's own shop is the planner's client (api.RemaClient, or a
store_client.StoreClient for a shop without an online catalogue): it searches
(async_search_products), looks products up by number (async_get_products) and
says whether it has prices (has_prices). When it has no sure product for an
item, the next shops are asked in turn (:func:`next_shops`), and the first sure
product goes on that shop's own list. Only Bilka ToGo can be
searched today; another shop is one more :class:`OtherShop` here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .api import Product, RemaError
from .bilka import BILKA_ID
from .chains import wants_bilka

if TYPE_CHECKING:
    from .matcher import ProductMatcher


@dataclass(frozen=True)
class OtherShop:
    """A shop to look in for what the family's shop has no sure product for."""

    dealer_id: str  # its list in the plan (a line's buy_at)
    name: str
    search: Callable[[str, int], Awaitable[list[Product]]]


def next_shops(planner: ProductMatcher) -> list[OtherShop]:
    """The shops to ask, in turn, for the items the family's shop isn't sure of."""
    shops: list[OtherShop] = []
    if planner.prices and wants_bilka(planner):
        shops.append(OtherShop(BILKA_ID, "Bilka", planner.bilka.async_search))
    return shops


async def async_search(shop: OtherShop, query: str, limit: int = 15) -> list[Product] | None:
    """A search in another shop; None when the shop can't be reached."""
    try:
        return await shop.search(query, limit)
    except RemaError:
        return None

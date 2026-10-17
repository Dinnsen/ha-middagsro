"""Tests for the favourites on offer this week and next week."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from custom_components.rema1000.api import Product, RemaClient, RemaError
from custom_components.rema1000.favorites import (
    FavoriteOffers,
    check_time,
    in_avis,
    late_time,
    on_offer,
)

from .conftest import CURRENT, OFFERS, UPCOMING, make_product

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)  # the last day of the avis
MILK = make_product(20494, "LETMÆLK 1,5% FEDT", 10.95)
BEEF = make_product(30001, "HK. OKSEKØD 8-12%", 50.0)
BEEF_SALE = make_product(30001, "HK. OKSEKØD 8-12%", 40.0, normal_price=50.0, is_advertised=True)
BROCCOLI = make_product(50001, "BROCCOLI", 12.0)
BROCCOLI_SALE = make_product(50001, "BROCCOLI", 8.0, normal_price=12.0, is_advertised=True)
CHIPS_SALE = make_product(80001, "CHIPS", 10.0, normal_price=15.0)  # cheaper today by its own price
WEDNESDAY = datetime(2026, 10, 21, 9, 59, 30, tzinfo=UTC)  # middle of next week's avis
FRIDAY = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)  # friday noon, danish time


def test_helpers() -> None:
    """What counts as an offer, what is worth checking, and when."""
    assert on_offer(BEEF_SALE)
    assert on_offer(CHIPS_SALE)
    assert not on_offer(MILK)
    # The beef matches two words of the avis, broccoli one, milk none.
    assert in_avis([MILK, BROCCOLI, BEEF], OFFERS) == [BEEF, BROCCOLI]
    assert check_time(CURRENT, NOW) == NOW
    # Next week's avis is checked in the middle of its week, not at its start
    # (REMA's prices start a few hours after the avis does).
    assert check_time(UPCOMING, NOW) == WEDNESDAY
    assert check_time(replace(UPCOMING, valid_to=None), NOW) == datetime(
        2026, 10, 18, 22, tzinfo=UTC
    )
    # ...and on its friday, for the offers that only start thursday.
    assert late_time(UPCOMING) == FRIDAY
    assert late_time(replace(UPCOMING, valid_to=None)) is None


async def test_favorite_offers(freezer: Any) -> None:
    """Favourites in the avis are checked with REMA at times the avis runs."""
    freezer.move_to(NOW)
    client = MagicMock(spec=RemaClient)
    client.async_get_offers = AsyncMock(return_value=OFFERS)
    seen: list[list[datetime]] = []

    async def search(query: str, limit: int, times: list[datetime]) -> list[list[Product]]:
        seen.append(times)
        if "OKSEKØD" in query:
            return [[MILK, BEEF_SALE] for _ in times]
        if query == "BROCCOLI" and len(times) == 2:
            # Only on offer from thursday: not in the middle of the week.
            early = replace(BROCCOLI, upcoming_from="2026-10-21T22:00:00+00:00")
            return [[early], [BROCCOLI_SALE]]
        raise RemaError("down")

    client.async_search_products_at = AsyncMock(side_effect=search)
    favorites = FavoriteOffers(client)
    products = [MILK, CHIPS_SALE, BEEF, BROCCOLI]

    # This week (saturday): checked now only, plus today's own offers, in order.
    result = await favorites.async_on_offer(products, CURRENT)
    assert [(p["id"], p["offer_from"]) for p in result] == [(CHIPS_SALE.id, None), (BEEF.id, None)]
    assert result[1]["price"] == 40.0
    assert {tuple(t) for t in seen} == {(NOW,)}
    await favorites.async_on_offer(products, CURRENT)  # cached
    assert client.async_get_offers.await_count == 1

    # Next week: in the middle of the week and on friday; today's prices don't count.
    seen.clear()
    result = await favorites.async_on_offer(products, UPCOMING, force=True)
    assert [(p["id"], p["price"], p["offer_from"]) for p in result] == [
        (BEEF.id, 40.0, None),
        (BROCCOLI.id, 8.0, "2026-10-21T22:00:00+00:00"),
    ]
    assert {tuple(t) for t in seen} == {(WEDNESDAY, FRIDAY)}

    # A thursday offer whose start REMA doesn't say: from friday.
    async def unknown_start(query: str, limit: int, times: list[datetime]) -> list[list[Product]]:
        return [[], [BROCCOLI_SALE]] if query == "BROCCOLI" else [[] for _ in times]

    client.async_search_products_at.side_effect = unknown_start
    result = await favorites.async_on_offer(products, UPCOMING, force=True)
    assert [(p["id"], p["offer_from"]) for p in result] == [(BROCCOLI.id, FRIDAY.isoformat())]

    # No avis, or the avis can't be read: today's own offers.
    assert [p["id"] for p in await favorites.async_on_offer(products, None)] == [CHIPS_SALE.id]
    client.async_get_offers.side_effect = RemaError("Tjek is down")
    result = await favorites.async_on_offer(products, CURRENT, force=True)
    assert [p["id"] for p in result] == [CHIPS_SALE.id]

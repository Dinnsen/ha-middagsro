"""Tests for the favourites on offer this week and next week."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from custom_components.rema1000.api import Product, RemaClient, RemaError
from custom_components.rema1000.favorites import FavoriteOffers, check_time, in_avis, on_offer

from .conftest import CURRENT, OFFERS, UPCOMING, make_product

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)  # the last day of the avis
MILK = make_product(20494, "LETMÆLK 1,5% FEDT", 10.95)
BEEF = make_product(30001, "HK. OKSEKØD 8-12%", 50.0)
BEEF_SALE = make_product(30001, "HK. OKSEKØD 8-12%", 40.0, normal_price=50.0, is_advertised=True)
BROCCOLI = make_product(50001, "BROCCOLI", 12.0)
CHIPS_SALE = make_product(80001, "CHIPS", 10.0, normal_price=15.0)  # cheaper today by its own price


def test_helpers() -> None:
    """What counts as an offer, what is worth checking, and when."""
    assert on_offer(BEEF_SALE)
    assert on_offer(CHIPS_SALE)
    assert not on_offer(MILK)
    # The beef matches two words of the avis, broccoli one, milk none.
    assert in_avis([MILK, BROCCOLI, BEEF], OFFERS) == [BEEF, BROCCOLI]
    assert check_time(CURRENT, NOW) == NOW
    assert UPCOMING.valid_from is not None
    assert check_time(UPCOMING, NOW) == UPCOMING.valid_from + timedelta(hours=1)


async def test_favorite_offers(freezer: Any) -> None:
    """Favourites in the avis are checked with REMA at a time the avis runs."""
    freezer.move_to(NOW)
    client = MagicMock(spec=RemaClient)
    client.async_get_offers = AsyncMock(return_value=OFFERS)
    seen: list[datetime | None] = []

    async def search(query: str, limit: int = 24, at: datetime | None = None) -> list[Product]:
        seen.append(at)
        if "OKSEKØD" in query:
            return [MILK, BEEF_SALE]
        raise RemaError("down")

    client.async_search_products = AsyncMock(side_effect=search)
    favorites = FavoriteOffers(client)
    products = [MILK, CHIPS_SALE, BEEF, BROCCOLI]

    # This week: checked now, plus today's own offers, in the favourites' order.
    result = await favorites.async_on_offer(products, CURRENT)
    assert [p.id for p in result] == [CHIPS_SALE.id, BEEF.id]
    assert result[1].price == 40.0
    assert set(seen) == {NOW}
    await favorites.async_on_offer(products, CURRENT)  # cached
    assert client.async_get_offers.await_count == 1

    # Next week: priced an hour after the avis starts; today's prices don't count.
    seen.clear()
    result = await favorites.async_on_offer(products, UPCOMING, force=True)
    assert [p.id for p in result] == [BEEF.id]
    assert UPCOMING.valid_from is not None
    assert set(seen) == {UPCOMING.valid_from + timedelta(hours=1)}

    # No avis, or the avis can't be read: today's own offers.
    assert await favorites.async_on_offer(products, None) == [CHIPS_SALE]
    client.async_get_offers.side_effect = RemaError("Tjek is down")
    assert await favorites.async_on_offer(products, CURRENT, force=True) == [CHIPS_SALE]

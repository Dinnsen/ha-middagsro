"""Tests for the favourites on offer this week and next week."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from custom_components.rema1000.api import Offer, RemaClient, RemaError
from custom_components.rema1000.favorites import FavoriteOffers, match_offer, offer_start, on_offer

from .conftest import CURRENT, UPCOMING, make_product

NOW = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)  # wednesday of week 42
MILK = make_product(20494, "LETMÆLK 1,5% FEDT", 10.95, underline="1 LTR. / ARLA", is_organic=True)
CREAM = make_product(41001, "PISKEFLØDE 36%", 12.95, underline="0.25 LTR. / KAROLINES KØKKEN")
PATE = make_product(42001, "LEVERPOSTEJ", 18.0, underline="500 GR. / REMA 1000")
OTHER_PATE = make_product(
    42002, "STOR LEVERPOSTEJ", 22.0, underline="400 GR. / SLAGTER MESTER ANDERSEN"
)
BEEF_SALE = make_product(30001, "HK. OKSEKØD 8-12%", 40.0, normal_price=50.0, is_advertised=True)
CHIPS = make_product(80001, "KIMS CHIPS", 20.0, underline="170 GR. / KIMS")


def offer(heading: str, price: float, start: str, **kwargs: Any) -> Offer:
    """An avis offer from a day (YYYY-MM-DD, danish time) to the avis's saturday."""
    return Offer(
        id=heading,
        heading=heading,
        description=kwargs.get("description"),
        price=price,
        pre_price=kwargs.get("pre_price"),
        quantity=kwargs.get("quantity"),
        valid_from=f"{start}T00:00:00+02:00",
        valid_to=kwargs.get("valid_to", "2026-10-17T23:59:59+02:00"),
    )


THIS_WEEK = [
    offer("Karolines Køkken Piskefløde 36%", 12, "2026-10-11", quantity="250 ml"),
    offer("KiMs chips eller snacks", 14, "2026-10-15"),  # thursday
]
NEXT_WEEK = [
    offer("Karolines Køkken Piskefløde 36%", 10, "2026-10-18", pre_price=14.95,
          valid_to="2026-10-24T23:59:59+02:00"),
    offer("REMA 1000 salami, leverpostej eller Taga serrano", 10, "2026-10-22",
          valid_to="2026-10-24T23:59:59+02:00"),
    offer("Arla letmælk", 9, "2026-10-18", valid_to="2026-10-24T23:59:59+02:00",
          description="1 liter\nØkologisk"),
]  # fmt: skip


def test_matching() -> None:
    """Favourites are found in the avis only when the offer is for that very product."""
    assert on_offer(BEEF_SALE)
    assert not on_offer(MILK)
    assert match_offer(CREAM, NEXT_WEEK) is NEXT_WEEK[0]
    assert match_offer(PATE, NEXT_WEEK) is NEXT_WEEK[1]
    assert match_offer(OTHER_PATE, NEXT_WEEK) is None  # another brand's, and "stor"
    assert match_offer(make_product(2, "PISKEFLØDE 36%", 9.0), NEXT_WEEK) is None  # REMA's own
    assert match_offer(CHIPS, THIS_WEEK) is THIS_WEEK[1]
    assert match_offer(BEEF_SALE, NEXT_WEEK) is None
    assert match_offer(make_product(1, "1,5% FEDT", 9.0), NEXT_WEEK) is None  # no real words
    # The avis says 00:00 danish time; REMA's price changes at 00:00 UTC (02:00 danish).
    assert offer_start(THIS_WEEK[1]) == datetime(2026, 10, 15, tzinfo=UTC)
    assert offer_start(Offer("x", "x", None, 1, None, None, None, None)) is None


async def test_this_and_next_week(freezer: Any) -> None:
    """This week: REMA's prices, plus thursday's offers from the avis. Next week: the avis."""
    freezer.move_to(NOW)
    client = MagicMock(spec=RemaClient)
    client.async_get_offers = AsyncMock(
        side_effect=lambda catalog_id: THIS_WEEK if catalog_id == CURRENT.id else NEXT_WEEK
    )
    favorites = FavoriteOffers(client)
    products = [MILK, CREAM, CHIPS, BEEF_SALE, PATE]

    # Wednesday: the beef is on offer in REMA; the chips only from thursday (avis).
    result = await favorites.async_on_offer(products, CURRENT)
    assert [(p["name"], p["price"], p["offer_from"]) for p in result] == [
        ("KIMS CHIPS", 14, "2026-10-15T00:00:00+00:00"),
        ("HK. OKSEKØD 8-12%", 40.0, None),
    ]
    assert result[0]["avis"] == "KiMs chips eller snacks"
    assert result[0]["normal_price"] == 20.0
    await favorites.async_on_offer(products, CURRENT)  # the avis is cached
    assert client.async_get_offers.await_count == 1

    # Next week, from the avis: thursday's offer marked, before-price from the avis.
    result = await favorites.async_on_offer(products, UPCOMING)
    assert [(p["name"], p["price"], p["normal_price"], p["offer_from"]) for p in result] == [
        ("LETMÆLK 1,5% FEDT", 9, 10.95, None),
        ("PISKEFLØDE 36%", 10, 14.95, None),
        ("LEVERPOSTEJ", 10, 18.0, "2026-10-22T00:00:00+00:00"),
    ]

    # Thursday 02:00: the chips are in REMA's prices now, not from the avis.
    freezer.move_to(datetime(2026, 10, 15, 0, 30, tzinfo=UTC))
    result = await favorites.async_on_offer(products, CURRENT, force=True)
    assert [p["name"] for p in result] == ["HK. OKSEKØD 8-12%"]

    # No avis, or the avis can't be read: REMA's own offers.
    assert [p["name"] for p in await favorites.async_on_offer(products, None)] == [
        "HK. OKSEKØD 8-12%"
    ]
    client.async_get_offers.side_effect = RemaError("Tjek is down")
    result = await favorites.async_on_offer(products, UPCOMING, force=True)
    assert result == []

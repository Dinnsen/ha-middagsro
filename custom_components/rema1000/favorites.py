"""Which of the account's favourite products are on offer this week or next week.

This week the prices come straight from REMA (as in the app). Offers in the
avis that start later in the week (thursday) and everything in next week's
avis come from the avis itself, because REMA only has those prices once they
take effect (at 00:00 UTC, i.e. 02:00 danish time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time as clock_time
import logging
import time
from typing import Any

from homeassistant.util import dt as dt_util

from .api import DANISH_TIME, Catalog, Offer, Product, RemaClient, RemaError, parse_time
from .mealplan import avis_match, unlinked_match

_LOGGER = logging.getLogger(__name__)

CACHE_SECONDS = 900


def on_offer(product: Product) -> bool:
    """True if the product's price is an offer."""
    return bool(
        product.is_advertised
        or product.is_campaign
        or (product.normal_price and product.price and product.price < product.normal_price - 0.01)
    )


def match_offer(product: Product, offers: list[Offer]) -> Offer | None:
    """The avis offer that is this very favourite, if any.

    By REMA's product ids when Tjek has them for an offer; otherwise (also
    for products Tjek lists without a REMA id) strictly by name (see
    ``unlinked_match`` and ``avis_match``): a wrong match shows a wrong price,
    so a favourite is better left out than matched to something else.
    """
    by_id = next((o for o in offers if o.product_ids and product.id in o.product_ids), None)
    return by_id or next(
        (
            o
            for o in offers
            if (o.product_ids is None or o.unlinked)
            and (
                unlinked_match(product.name, product.underline, product.is_organic, o)
                or avis_match(product.name, product.underline, product.is_organic, o)
            )
        ),
        None,
    )


def offer_start(offer: Offer) -> datetime | None:
    """When an avis offer's price is in REMA: 00:00 UTC (02:00 danish) on its first day.

    The avis says 00:00 danish time, but REMA's prices change two hours later.
    """
    start = parse_time(offer.valid_from)
    if start is None:
        return None
    return datetime.combine(start.astimezone(DANISH_TIME).date(), clock_time(), UTC)


def _from_avis(product: Product, offer: Offer, late: bool) -> dict[str, Any]:
    """A favourite with the avis's price."""
    before = [
        price
        for price in (
            offer.pre_price,
            product.normal_price,
            None if product.upcoming_is_advertised else product.upcoming_price,
        )
        if price
    ]
    normal = max(before) if before else None
    start = offer_start(offer)
    return product.as_dict() | {
        "price": offer.price,
        "normal_price": normal if normal and offer.price and normal > offer.price else offer.price,
        "is_advertised": True,
        "price_valid_to": offer.valid_to,
        "offer_from": start.isoformat() if late and start else None,
        "avis": offer.heading,
        "avis_quantity": offer.quantity,
    }


def _from_rema(product: Product) -> dict[str, Any]:
    return product.as_dict() | {"offer_from": None, "avis": None, "avis_quantity": None}


@dataclass
class FavoriteOffers:
    """Find favourites on offer in an avis."""

    client: RemaClient
    _offers: dict[str, tuple[float, list[Offer]]] = field(default_factory=dict)

    async def _async_offers(self, catalog: Catalog, force: bool) -> list[Offer]:
        cached = self._offers.get(catalog.id)
        if cached and not force and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        offers = await self.client.async_get_offers(catalog.id)
        offers = await self.client.async_get_offer_products(offers)
        self._offers[catalog.id] = (time.monotonic(), offers)
        return offers

    async def async_on_offer(
        self,
        favorites: list[Product],
        catalog: Catalog | None,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """The favourites on offer while an avis runs, in the favourites' order.

        For the avis running now: REMA's own prices, plus the avis's offers
        that have not started yet (``offer_from``). For an avis that has not
        started: the avis's prices, ``offer_from`` on those starting after its
        first day.
        """
        now = dt_util.utcnow()
        upcoming = bool(catalog and catalog.valid_from and catalog.valid_from > now)
        mine = {} if upcoming else {p.id: _from_rema(p) for p in favorites if on_offer(p)}
        if catalog is None:
            return list(mine.values())
        try:
            offers = await self._async_offers(catalog, force)
        except RemaError as err:
            _LOGGER.warning("Could not load the avis to check favourites: %s", err)
            return list(mine.values())

        first_day = (catalog.valid_from or now).astimezone(DANISH_TIME).date()

        def late(offer: Offer) -> bool:
            start = offer_start(offer)
            if start is None:
                return False
            if upcoming:
                return start.astimezone(DANISH_TIME).date() > first_day
            return start > now

        # This week only the offers that have not started yet come from the avis.
        usable = offers if upcoming else [o for o in offers if late(o)]
        result: list[dict[str, Any]] = []
        for product in favorites:
            if product.id in mine:
                result.append(mine[product.id])
            elif offer := match_offer(product, usable):
                result.append(_from_avis(product, offer, late(offer)))
        return result

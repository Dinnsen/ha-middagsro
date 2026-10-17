"""Which of the account's favourite products are on offer this week or next week."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, time as clock_time, timedelta
import logging
import time
from typing import Any

from homeassistant.util import dt as dt_util

from .api import DANISH_TIME, Catalog, Offer, Product, RemaClient, RemaError
from .mealplan import _NEUTRAL_WORDS, _tokens

_LOGGER = logging.getLogger(__name__)

CACHE_SECONDS = 900
MAX_CHECKS = 60  # product searches per avis, at most
CHECK_CONCURRENCY = 4


def on_offer(product: Product) -> bool:
    """True if the product's price is an offer."""
    return bool(
        product.is_advertised
        or product.is_campaign
        or (product.normal_price and product.price and product.price < product.normal_price - 0.01)
    )


def _words(text: str) -> set[str]:
    """Words that say what a product is (no sizes, numbers or neutral words)."""
    return {w for w in _tokens(text) if len(w) > 2 and w not in _NEUTRAL_WORDS}


def in_avis(products: list[Product], offers: list[Offer]) -> list[Product]:
    """Favourites whose name looks like something in the avis, best match first.

    The avis names things differently ("Arla letmælk" for "LETMÆLK 1,5% FEDT"),
    so this only picks which favourites are worth checking with REMA.
    """
    avis: set[str] = set()
    for offer in offers:
        avis |= _words(f"{offer.heading} {offer.description or ''}")
    scored: list[tuple[int, int, Product]] = []
    for idx, product in enumerate(products):
        score = sum(
            1
            for word in _words(product.name)
            if word in avis or any(len(a) > 3 and (a in word or word in a) for a in avis)
        )
        if score:
            scored.append((-score, idx, product))
    return [product for _, _, product in sorted(scored)]


def check_time(catalog: Catalog, now: datetime) -> datetime:
    """A moment the avis runs: now if it runs now, else the middle of its week.

    REMA's prices for the week start a few hours after the avis does (the
    avis at 00:00 danish time, the prices at 00:00 UTC), so the start itself
    is not safe.
    """
    if catalog.valid_from and catalog.valid_from > now:
        if catalog.valid_to and catalog.valid_to > catalog.valid_from:
            return catalog.valid_from + (catalog.valid_to - catalog.valid_from) / 2
        return catalog.valid_from + timedelta(days=1)
    return now


def late_time(catalog: Catalog) -> datetime | None:
    """Friday noon (danish time) of the avis's week, when its late offers run.

    Some offers only start on thursday; this is a moment both they and the
    rest of the avis run.
    """
    if not catalog.valid_to:
        return None
    last_day = catalog.valid_to.astimezone(DANISH_TIME).date()  # saturday
    return datetime.combine(last_day - timedelta(days=1), clock_time(12), DANISH_TIME).astimezone(
        UTC
    )


@dataclass
class FavoriteOffers:
    """Find favourites on offer in an avis, cached per avis."""

    client: RemaClient
    _cache: dict[str, tuple[float, list[dict[str, Any]]]] = field(default_factory=dict)

    async def async_on_offer(
        self,
        favorites: list[Product],
        catalog: Catalog | None,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """The favourites on offer while an avis runs, with that price.

        REMA's favourites list only has today's price, so each favourite that
        looks like something in the avis is looked up in REMA's product search,
        which has the prices for the coming days too. It is checked twice: in
        the avis's week and on its friday, for the offers that start thursday.
        Those get ``offer_from``, when the offer starts.
        """
        now = dt_util.utcnow()
        running = catalog is None or check_time(catalog, now) == now
        today = [_offer(p) for p in favorites if on_offer(p)] if running else []
        if catalog is None:
            return today
        cached = self._cache.get(catalog.id)
        if cached and not force and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]

        try:
            offers = await self.client.async_get_offers(catalog.id)
        except RemaError as err:
            _LOGGER.warning("Could not load the avis to check favourites: %s", err)
            return today
        at = check_time(catalog, now)
        late = late_time(catalog)
        times = [at, late] if late and late > at else [at]
        candidates = in_avis(favorites, offers)[:MAX_CHECKS]
        semaphore = asyncio.Semaphore(CHECK_CONCURRENCY)

        async def check(product: Product) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    found = await self.client.async_search_products_at(product.name, 20, times)
                except RemaError as err:
                    _LOGGER.debug("Could not check %s: %s", product.name, err)
                    return None
            same = [next((p for p in at_time if p.id == product.id), None) for at_time in found]
            if same[0] and on_offer(same[0]):
                return _offer(same[0])
            if len(same) > 1 and same[1] and on_offer(same[1]):
                # Only on offer later in the week: say from when.
                start = same[0].upcoming_from if same[0] else None
                return _offer(same[1], start or times[1].isoformat())
            return None

        checked = {p["id"]: p for p in await asyncio.gather(*map(check, candidates)) if p}
        # Keep the order of the favourites list; today's own price also counts.
        mine = {p["id"]: p for p in today}
        result = [
            checked.get(p.id) or mine[p.id] for p in favorites if p.id in checked or p.id in mine
        ]
        self._cache[catalog.id] = (time.monotonic(), result)
        return result


def _offer(product: Product, offer_from: str | None = None) -> dict[str, Any]:
    """A favourite on offer, as the panel shows it."""
    return product.as_dict() | {"offer_from": offer_from}

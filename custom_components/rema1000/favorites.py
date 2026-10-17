"""Which of the account's favourite products are on offer this week or next week."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time

from homeassistant.util import dt as dt_util

from .api import Catalog, Offer, Product, RemaClient, RemaError
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


@dataclass
class FavoriteOffers:
    """Find favourites on offer in an avis, cached per avis."""

    client: RemaClient
    _cache: dict[str, tuple[float, list[Product]]] = field(default_factory=dict)

    async def async_on_offer(
        self,
        favorites: list[Product],
        catalog: Catalog | None,
        force: bool = False,
    ) -> list[Product]:
        """The favourites that are on offer while an avis runs, with that price.

        REMA's favourites list only has today's price, so each favourite that
        looks like something in the avis is looked up in REMA's product search,
        which has the prices for the coming days too.
        """
        now = dt_util.utcnow()
        running = catalog is None or check_time(catalog, now) == now
        today = [p for p in favorites if on_offer(p)] if running else []
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
        candidates = in_avis(favorites, offers)[:MAX_CHECKS]
        semaphore = asyncio.Semaphore(CHECK_CONCURRENCY)

        async def check(product: Product) -> Product | None:
            async with semaphore:
                try:
                    found = await self.client.async_search_products(product.name, 20, at=at)
                except RemaError as err:
                    _LOGGER.debug("Could not check %s: %s", product.name, err)
                    return None
            same = next((p for p in found if p.id == product.id), None)
            return same if same and on_offer(same) else None

        checked = {p.id: p for p in await asyncio.gather(*map(check, candidates)) if p}
        # Keep the order of the favourites list; today's own price also counts.
        today_ids = {p.id for p in today}
        result = [checked.get(p.id, p) for p in favorites if p.id in checked or p.id in today_ids]
        self._cache[catalog.id] = (time.monotonic(), result)
        return result

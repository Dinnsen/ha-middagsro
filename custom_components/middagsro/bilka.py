"""Bilka ToGo's prices on every item (not only its offers).

Bilka ToGo's webshop searches its products with Algolia, with a search key that
is in the webshop's own JavaScript (``NUXT_ENV_ALGOLIA_SEARCH_API_KEY``). The key
is read from there when it is needed (and again if Algolia stops taking it), so
nothing is kept here that the webshop doesn't hand every visitor. Unofficial,
like REMA 1000's API: it may stop working if Bilka changes the webshop.

Prices are the delivery warehouse's (store 1653), the webshop's own: close to,
not always the same as, a Bilka shop's.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from .api import Product, RemaApiError, RemaConnectionError
from .recipes import HEADERS, async_read_body, page_session

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

BILKA_ID = "93f13"  # Bilka on Tjek (chains.CHAINS)
SITE = "https://www.bilkatogo.dk"
INDEX = "prod_BILKATOGO_PRODUCTS"
STORE = "1653"  # the webshop's delivery warehouse
FILTERS = f"isInAssortmentIn:{STORE} AND inStockStore:{STORE} AND nonsearchable:false"
ATTRIBUTES = [
    "id", "name", "brand", "netcontent", "price", "sales_price", "categories",
    "targetOrganic", "isInCurrentLeaflet", "images", "storeData",
]  # fmt: skip
TIMEOUT = aiohttp.ClientTimeout(total=20)
SCRIPT_LIMIT = 6_000_000
KEY_RETRY = 600  # seconds before the key is looked for again after a failure
SEARCH_CACHE = 3600
MAX_PRODUCTS = 3000

_SCRIPT = re.compile(r"""<script[^>]+src=["'](/_nuxt/[^"']+\.js)["']""")
_KEY = re.compile(r'NUXT_ENV_ALGOLIA_SEARCH_API_KEY:"([0-9a-f]{32})"')
_APP = re.compile(r'NUXT_ENV_ALGOLIA_APP_ID:"([A-Z0-9]{6,20})"')


class BilkaError(RemaApiError):
    """Bilka ToGo's search could not be used."""


def _kr(value: Any) -> float | None:
    try:
        return round(float(value) / 100, 2) if value else None
    except (TypeError, ValueError):
        return None


def to_product(hit: dict[str, Any]) -> Product | None:
    """A Bilka ToGo product in the shape the app knows (REMA's products)."""
    try:
        product_id = int(hit.get("id") or hit["objectID"])
    except (KeyError, TypeError, ValueError):
        return None
    name = str(hit.get("name") or "").strip()
    price = _kr(hit.get("sales_price")) or _kr(hit.get("price"))
    if not name or price is None:
        return None
    normal = _kr(hit.get("price")) or price
    store = (hit.get("storeData") or {}).get(STORE) or {}
    unit = str(store.get("unitsOfMeasurePriceUnit") or "").strip(" .").lower() or None
    categories = hit.get("categories") or {}
    top = [str(c) for c in categories.get("lvl0") or []]
    sub = [str(c).split(" > ")[-1] for c in categories.get("lvl1") or []]
    images = hit.get("images") or []
    netcontent = str(hit.get("netcontent") or "").strip()
    brand = str(hit.get("brand") or "").strip()
    on_offer = normal > price
    return Product(
        id=product_id,
        name=name,
        underline=" / ".join(p for p in (netcontent.upper(), brand.upper()) if p) or None,
        department=top[0] if top else None,
        category=sub[0] if sub else None,
        price=price,
        normal_price=normal,
        compare_unit=unit,
        compare_unit_price=_kr(store.get("unitsOfMeasureShowPrice")),
        is_advertised=on_offer and bool(hit.get("isInCurrentLeaflet")),
        is_campaign=on_offer,
        price_valid_to=None,
        upcoming_price=None,
        upcoming_from=None,
        upcoming_is_advertised=False,
        is_organic=bool(hit.get("targetOrganic")) or bool(re.search(r"\bøko", name.lower())),
        labels=[],
        image=str(images[0]) if images and isinstance(images[0], str) else None,
    )


class BilkaSearch:
    """Search Bilka ToGo's products, with their prices now."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self._key: tuple[str, str] | None = None
        self._key_failed = 0.0
        self._lock = asyncio.Lock()
        self._searches: dict[str, tuple[float, list[int]]] = {}
        self._products: dict[int, Product] = {}

    async def _async_text(self, url: str, limit: int) -> str:
        async with page_session(self.hass).get(
            url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True
        ) as resp:
            if resp.status >= 400:
                raise aiohttp.ClientError(f"HTTP {resp.status}")
            return await async_read_body(resp, limit)

    async def _async_find_key(self) -> tuple[str, str]:
        """(app id, search key) from the webshop's JavaScript."""
        page = await self._async_text(f"{SITE}/", 2_000_000)
        scripts = list(dict.fromkeys(_SCRIPT.findall(page)))
        # The big bundles hold the settings: the last ones on the page.
        for src in reversed(scripts):
            text = await self._async_text(f"{SITE}{src}", SCRIPT_LIMIT)
            if (key := _KEY.search(text)) and (app := _APP.search(text)):
                return app.group(1), key.group(1)
        raise BilkaError("Bilka ToGo's search key was not found on bilkatogo.dk")

    async def _async_credentials(self, force: bool = False) -> tuple[str, str]:
        async with self._lock:
            if self._key and not force:
                return self._key
            if time.monotonic() - self._key_failed < KEY_RETRY and not self._key:
                raise BilkaError("Bilka ToGo could not be read a moment ago")
            try:
                self._key = await self._async_find_key()
            except (aiohttp.ClientError, TimeoutError, BilkaError) as err:
                self._key_failed = time.monotonic()
                self._key = None
                raise BilkaError(f"Could not read Bilka ToGo: {err}") from err
            return self._key

    async def _async_query(self, query: str, limit: int) -> list[dict[str, Any]]:
        for attempt in (0, 1):
            app, key = await self._async_credentials(force=attempt == 1)
            try:
                async with page_session(self.hass).post(
                    f"https://{app}-dsn.algolia.net/1/indexes/{INDEX}/query",
                    headers={
                        "x-algolia-application-id": app,
                        "x-algolia-api-key": key,
                        "content-type": "application/json",
                    },
                    json={
                        "query": query,
                        "hitsPerPage": limit,
                        "filters": FILTERS,
                        "attributesToRetrieve": ATTRIBUTES,
                    },
                    timeout=TIMEOUT,
                ) as resp:
                    if resp.status in (401, 403) and attempt == 0:
                        continue  # a new key: read it again
                    if resp.status >= 400:
                        raise BilkaError(f"Bilka ToGo's search answered HTTP {resp.status}")
                    data = await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise RemaConnectionError(f"Could not reach Bilka ToGo: {err}") from err
            hits = data.get("hits") if isinstance(data, dict) else None
            return [h for h in hits or [] if isinstance(h, dict)]
        raise BilkaError("Bilka ToGo's search key was not accepted")

    async def async_search(self, query: str, limit: int = 12) -> list[Product]:
        """Products for a search, best first (kept for an hour)."""
        text = " ".join(str(query or "").split()).lower()[:80]
        if not text:
            return []
        limit = max(1, min(limit, 40))
        key = f"{limit}|{text}"
        cached = self._searches.get(key)
        if cached and time.monotonic() - cached[0] < SEARCH_CACHE:
            return [self._products[i] for i in cached[1] if i in self._products]
        products = [p for p in (to_product(h) for h in await self._async_query(text, limit)) if p]
        for product in products:
            self._products[product.id] = product
        self._searches[key] = (time.monotonic(), [p.id for p in products])
        if len(self._products) > MAX_PRODUCTS:
            for pid in list(self._products)[: MAX_PRODUCTS // 2]:
                del self._products[pid]
            self._searches.clear()
        return products

    def known(self, product_ids: list[int]) -> list[Product]:
        """Products found before (Bilka's search can't look them up by id)."""
        return [self._products[i] for i in product_ids if i in self._products]

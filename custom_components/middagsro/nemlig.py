"""Nemlig.com: the family's account, its prices on every item, its offers and its basket.

Uses the webshop's own calls, as the browser makes them (unofficial, like REMA
1000's API: it may stop working if Nemlig changes the webshop):

- ``/webapi/Token`` hands out a short-lived bearer token (five minutes) for the
  session's cookies; ``/webapi/login`` logs the session in with the account.
- ``searchgateway/api/search`` finds products with the account's prices.
- ``/tilbud?GetAsJson=1`` has the offer page's product groups (Ugens Priskup,
  Skarp pris, Dagstilbud ...), read with ``Products/GetByProductGroupId``.
- ``basket/AddToBasket`` sets a product's quantity in the basket (an absolute
  quantity, 0 removes it) and answers with the whole basket.

The password stays in the config entry; tokens and cookies live only in memory.
Middagsro never chooses a delivery time and never places an order.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
import re
import time
from typing import Any
import uuid

import aiohttp
from yarl import URL

from homeassistant.util import dt as dt_util

from .api import (
    Catalog,
    Offer,
    Product,
    RemaApiError,
    RemaAuthError,
    RemaConnectionError,
    ShoppingList,
    ShoppingListItem,
)

_LOGGER = logging.getLogger(__name__)

NEMLIG_ID = "nemlig"
NEMLIG_NAME = "Nemlig.com"
SITE = "https://www.nemlig.com"
SEARCH = "https://webapi.prod.knl.nemlig.it/searchgateway/api/search"
TIMEOUT = aiohttp.ClientTimeout(total=25)
TOKEN_TTL = 240  # seconds; Nemlig's tokens last 300
SETTINGS_TTL = 1800
OFFERS_TTL = 3600
SEARCH_CACHE = 3600
MAX_PRODUCTS = 3000
MAX_GROUPS = 8
# The webshop sends these with every call; an unknown client may be turned away.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.5",
    "platform": "web",
    "version": "11.236.2",
    "device-size": "desktop",
}
# Product groups on the offer page that are not the week's offers.
_NOT_OFFERS = re.compile(r"favorit|madspild|sponsor|gave|inspiration|nyhed", re.IGNORECASE)
_UNIT = re.compile(r"kr\.?\s*/\s*([a-zæøå]+)", re.IGNORECASE)


class NemligError(RemaApiError):
    """Nemlig.com could not be used."""


def _num(value: Any) -> float | None:
    try:
        return round(float(value), 2) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pid(value: Any) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _organic(item: dict[str, Any]) -> bool:
    labels = " ".join(str(label) for label in item.get("Labels") or []).lower()
    return "øko" in labels or bool(re.search(r"\bøko", str(item.get("Name") or "").lower()))


def to_product(item: dict[str, Any]) -> Product | None:
    """A Nemlig product in the shape the app knows (REMA's products)."""
    pid = _pid(item.get("Id"))
    name = " ".join(str(item.get("Name") or "").split())
    price = _num(item.get("Price"))
    if pid is None or not name or price is None:
        return None
    availability = item.get("Availability") or {}
    if availability and availability.get("IsDeliveryAvailable") is False:
        return None
    campaign = item.get("Campaign") or {}
    unit_label = str(item.get("UnitPriceLabel") or "")
    unit = _UNIT.search(unit_label)
    labels = [str(label) for label in item.get("Labels") or []]
    on_offer = bool(campaign) or "Discount" in labels
    return Product(
        id=pid,
        name=name,
        underline=str(item.get("Description") or "").upper() or None,
        department=str(item.get("ProductMainGroupName") or item.get("Category") or "") or None,
        category=str(item.get("ProductSubGroupName") or item.get("SubCategory") or "") or None,
        price=price,
        normal_price=price,
        compare_unit=unit.group(1).lower() if unit else None,
        compare_unit_price=_num(item.get("UnitPriceCalc")),
        is_advertised=bool(campaign),
        is_campaign=on_offer,
        price_valid_to=str(campaign.get("IntervalEnd") or "") or None,
        upcoming_price=None,
        upcoming_from=None,
        upcoming_is_advertised=False,
        is_organic=_organic(item),
        labels=labels,
        image=str(item.get("PrimaryImage") or "") or None,
    )


def to_offer(item: dict[str, Any], start: datetime, end: datetime) -> Offer | None:
    """A product on Nemlig's offer page as an avis offer (its product linked)."""
    product = to_product(item)
    if product is None:
        return None
    campaign = item.get("Campaign") or {}
    pieces = int(campaign.get("MinQuantity") or 0)
    total = _num(campaign.get("CampaignPrice") or campaign.get("TotalPrice"))
    price: float | None
    quantity: str | None
    description: str | None
    if pieces > 1 and total:
        price, quantity = total, f"{pieces} stk."
        description = f"{pieces} for {total:.2f} kr. · {item.get('Description') or ''}".strip(" ·")
    else:
        price, quantity = (total or product.price), str(item.get("Description") or "") or None
        description = str(item.get("Description") or "") or None
    valid_from = str(campaign.get("IntervalStart") or "") or start.isoformat()
    valid_to = str(campaign.get("IntervalEnd") or "") or end.isoformat()
    return Offer(
        id=f"nemlig-{product.id}",
        heading=product.name,
        description=description,
        price=price,
        pre_price=None,
        quantity=quantity,
        valid_from=valid_from,
        valid_to=valid_to,
        product_ids=(product.id,),
        product_names=(product.name,),
        unlinked=False,
    )


def basket_items(data: dict[str, Any]) -> list[ShoppingListItem]:
    """The basket's products (not bags, deposits or meal boxes)."""
    items: list[ShoppingListItem] = []
    for line in data.get("Lines") or []:
        if not isinstance(line, dict):
            continue
        pid = _pid(line.get("Id"))
        try:
            amount = int(line.get("Quantity") or 0)
        except (TypeError, ValueError):
            raise NemligError("Nemlig.com returned an invalid basket line") from None
        if pid is None or amount <= 0:
            continue
        items.append(
            ShoppingListItem(
                id=pid,
                product_id=pid,
                name=str(line.get("Name") or pid),
                bought=False,
                amount=amount,
                underline=str(line.get("Description") or "") or None,
                price=_num(line.get("ItemPrice")),
            )
        )
    return items


def offer_groups(page: Any) -> list[tuple[str, str]]:
    """(heading, product group id) of the offer page's lists of products."""
    found: list[tuple[str, str]] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            group = node.get("ProductGroupId")
            heading = str(node.get("Heading") or "").strip()
            if (
                isinstance(group, str)
                and re.fullmatch(r"[0-9a-f-]{36}", group)
                and str(node.get("TemplateName") or "").startswith("productlist")
                and not _NOT_OFFERS.search(heading)
                and group not in {g for _h, g in found}
            ):
                found.append((heading, group))
            for child in node.values():
                visit(child)

    visit(page)
    return found[:MAX_GROUPS]


def week_of(now: datetime) -> tuple[datetime, datetime]:
    """Monday 00:00 to Sunday 23:59:59, Danish time, of the week ``now`` is in."""
    local = dt_util.as_local(now)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday, monday + timedelta(days=7, seconds=-1)


class NemligClient:
    """A Nemlig.com account: search, offers and basket (never checkout)."""

    pickup_name = ""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        """Keep credentials in the config entry; tokens and cookies live only in memory."""
        self.session = session
        self.email = email
        self.password = password
        self.user_id: int | None = None
        self._token: str | None = None
        self._token_at = 0.0
        self._logged_in = False
        self._login_lock = asyncio.Lock()
        self._change = asyncio.Lock()
        self._settings: dict[str, Any] = {}
        self._groups: list[tuple[str, str]] = []
        self._settings_at = 0.0
        self._offers: list[Offer] = []
        self._offers_at = 0.0
        self._searches: dict[str, tuple[float, list[int]]] = {}
        self._products: dict[int, Product] = {}
        self._amounts: dict[int, int] = {}

    # ------------------------------------------------------------ requests

    def _xsrf(self) -> str | None:
        cookie = self.session.cookie_jar.filter_cookies(URL(SITE)).get("XSRF-TOKEN")
        return cookie.value if cookie else None

    async def _raw(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        auth: bool = True,
        xsrf: bool = False,
    ) -> Any:
        headers = {**_HEADERS, "X-Correlation-Id": str(uuid.uuid4())}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if xsrf and (token := self._xsrf()):
            headers["X-XSRF-TOKEN"] = token
        try:
            async with self.session.request(
                method,
                url,
                params=params,
                json=body,
                headers=headers,
                timeout=TIMEOUT,
                allow_redirects=False,
            ) as response:
                if response.status in (301, 302, 303, 307):
                    where = response.headers.get("Location", "")
                    if "queue-it" in where.lower():
                        raise NemligError("Nemlig.com har kø lige nu. Prøv igen om lidt")
                    raise NemligError(f"Nemlig.com sendte videre (HTTP {response.status})")
                if response.status in (401, 403):
                    raise RemaAuthError("Nemlig.com authentication was rejected")
                if response.status >= 400:
                    raise NemligError(f"Nemlig.com answered HTTP {response.status}")
                return await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            # Never expose request URLs, credentials or response bodies.
            raise RemaConnectionError("Could not reach Nemlig.com") from None

    async def _async_token(self, *, force: bool = False) -> str:
        if not force and self._token and time.monotonic() - self._token_at < TOKEN_TTL:
            return self._token
        data = await self._raw("GET", f"{SITE}/webapi/Token", auth=False)
        token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise NemligError("Nemlig.com did not hand out a token")
        self._token, self._token_at = token, time.monotonic()
        return token

    async def async_login(self, *, force: bool = False) -> int:
        """Session cookies -> token -> login -> the account's token and number."""
        async with self._login_lock:
            if not force and self._logged_in and self.user_id:
                await self._async_token()
                return self.user_id
            self._logged_in = False
            self._token = None
            # The front page gives the session its cookies (and the XSRF token).
            try:
                async with self.session.get(
                    f"{SITE}/", headers=_HEADERS, timeout=TIMEOUT, allow_redirects=False
                ) as response:
                    where = response.headers.get("Location", "")
                    if "queue-it" in where.lower():
                        raise NemligError("Nemlig.com har kø lige nu. Prøv igen om lidt")
                    await response.read()
            except (aiohttp.ClientError, TimeoutError):
                raise RemaConnectionError("Could not reach Nemlig.com") from None
            await self._async_token(force=True)
            try:
                answer = await self._raw(
                    "POST",
                    f"{SITE}/webapi/login",
                    body={
                        "Username": self.email,
                        "Password": self.password,
                        "CheckForExistingProducts": True,
                        "DoMerge": True,
                        "AppInstalled": False,
                        "SaveExistingBasket": False,
                    },
                    xsrf=True,
                )
            except NemligError as err:
                if "HTTP 4" in str(err):
                    raise RemaAuthError("Nemlig.com did not accept the login") from None
                raise
            if not isinstance(answer, dict) or (
                answer.get("ErrorMessage") and not answer.get("RedirectUrl")
            ):
                raise RemaAuthError("Nemlig.com did not accept the login")
            await self._async_token(force=True)
            user = await self._raw("GET", f"{SITE}/webapi/user/GetCurrentUser")
            uid = _pid((user or {}).get("DebitorId")) if isinstance(user, dict) else None
            if uid is None:
                raise RemaAuthError("Nemlig.com did not confirm the account")
            self.user_id, self._logged_in = uid, True
            self._settings_at = 0.0  # the account's delivery zone and prices
            return uid

    async def _call(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        xsrf: bool = False,
    ) -> Any:
        """A logged-in call; logged in again once if the session has ended."""
        await self.async_login()
        for attempt in (0, 1):
            try:
                return await self._raw(method, url, params=params, body=body, xsrf=xsrf)
            except RemaAuthError:
                if attempt:
                    raise
                await self.async_login(force=True)
        raise RemaAuthError("Nemlig.com login expired")

    # ------------------------------------------------------------ settings and offers

    async def _async_settings(self) -> dict[str, Any]:
        """The account's delivery zone, time slot and the catalogue's stamp."""
        if self._settings and time.monotonic() - self._settings_at < SETTINGS_TTL:
            return self._settings
        page = await self._call("GET", f"{SITE}/tilbud", params={"GetAsJson": 1})
        settings = page.get("Settings") if isinstance(page, dict) else None
        if not isinstance(settings, dict) or not settings.get("TimeslotUtc"):
            raise NemligError("Nemlig.com's offer page could not be read")
        self._settings = settings
        self._groups = offer_groups(page.get("content"))
        self._settings_at = time.monotonic()
        return settings

    def _base(self, settings: dict[str, Any]) -> str:
        return (
            f"{SITE}/webapi/{settings.get('CombinedProductsAndSitecoreTimestamp') or 'x'}/"
            f"{settings['TimeslotUtc']}/{settings.get('DeliveryZoneId') or 0}/"
            f"{settings.get('UserId') or self.user_id or 0}"
        )

    async def async_offers(self) -> list[Offer]:
        """This week's offers on Nemlig's offer page (kept for an hour)."""
        if self._offers and time.monotonic() - self._offers_at < OFFERS_TTL:
            return self._offers
        settings = await self._async_settings()
        start, end = week_of(datetime.now(UTC))
        offers: dict[str, Offer] = {}
        for heading, group in self._groups:
            try:
                data = await self._call(
                    "GET",
                    f"{self._base(settings)}/Products/GetByProductGroupId",
                    params={"productGroupId": group, "sortorder": "default"},
                )
            except NemligError as err:
                _LOGGER.debug("Nemlig.com's %s could not be read: %s", heading, err)
                continue
            items = data.get("Products") if isinstance(data, dict) else None
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                offer = to_offer(item, start, end)
                if offer is not None and offer.id not in offers:
                    offers[offer.id] = offer
                    if (product := to_product(item)) is not None:
                        self._remember(product)
        self._offers, self._offers_at = list(offers.values()), time.monotonic()
        return self._offers

    async def async_catalogs(self) -> list[Catalog]:
        """This week's offers as one avis (Nemlig has no printed one)."""
        offers = await self.async_offers()
        start, end = week_of(datetime.now(UTC))
        week = start.isocalendar().week
        return [
            Catalog(
                id=f"nemlig-{start.date().isoformat()}",
                label=f"Nemlig.com tilbud uge {week}",
                valid_from=start,
                valid_to=end,
                offer_count=len(offers) or None,
            )
        ]

    # ------------------------------------------------------------ search

    def _remember(self, product: Product) -> None:
        self._products[product.id] = product
        if len(self._products) > MAX_PRODUCTS:
            for pid in list(self._products)[: MAX_PRODUCTS // 2]:
                del self._products[pid]
            self._searches.clear()

    async def async_search(self, query: str, limit: int = 12) -> list[Product]:
        """Products for a search with the account's prices, best first (kept an hour)."""
        text = " ".join(str(query or "").split()).lower()[:80]
        if not text:
            return []
        limit = max(1, min(limit, 40))
        key = f"{limit}|{text}"
        cached = self._searches.get(key)
        if cached and time.monotonic() - cached[0] < SEARCH_CACHE:
            return [self._products[i] for i in cached[1] if i in self._products]
        settings = await self._async_settings()
        data = await self._call(
            "GET",
            SEARCH,
            params={
                "query": text,
                "take": limit,
                "skip": 0,
                "recipeCount": 0,
                "timestamp": settings.get("CombinedProductsAndSitecoreTimestamp") or "",
                "timeslotUtc": settings["TimeslotUtc"],
                "deliveryZoneId": settings.get("DeliveryZoneId") or 0,
            },
        )
        block = (data or {}).get("Products") if isinstance(data, dict) else None
        hits = block.get("Products") if isinstance(block, dict) else None
        products = [
            p for p in (to_product(h) for h in hits or [] if isinstance(h, dict)) if p is not None
        ]
        for product in products:
            self._remember(product)
        self._searches[key] = (time.monotonic(), [p.id for p in products])
        return products

    def known(self, product_ids: list[int]) -> list[Product]:
        """Products found before (by a search or on the offer page)."""
        return [self._products[i] for i in product_ids if i in self._products]

    # ------------------------------------------------------------ basket

    async def async_select_location(self, *, force: bool = True) -> None:
        """Nemlig delivers to the account's address: nothing to choose."""

    async def async_list(self) -> ShoppingList:
        """The basket as it is now."""
        data = await self._call("GET", f"{SITE}/webapi/basket/GetBasket")
        if not isinstance(data, dict):
            raise NemligError("Nemlig.com returned an unexpected basket")
        items = basket_items(data)
        self._amounts = {item.id: item.amount for item in items}
        return ShoppingList(id=1, name=NEMLIG_NAME, items=items)

    def amount(self, product_id: int, shopping_list: ShoppingList | None = None) -> int:
        """How many of a product the basket has, as last read or set here."""
        if product_id in self._amounts:
            return self._amounts[product_id]
        items = shopping_list.items if shopping_list else []
        return next((i.amount for i in items if i.id == product_id), 0)

    async def async_set_amount(self, product_id: int, amount: int, *, verify: bool = True) -> None:
        """Set an absolute quantity (Nemlig's AddToBasket sets, it doesn't add)."""
        async with self._change:
            data: Any = None
            # A timed-out write may have succeeded; the check after it tells.
            try:
                data = await self._call(
                    "POST",
                    f"{SITE}/webapi/basket/AddToBasket",
                    body={
                        "ProductId": str(product_id),
                        "quantity": max(0, int(amount)),
                        "AffectPartialQuantity": False,
                        "disableQuantityValidation": False,
                    },
                    xsrf=True,
                )
            except RemaConnectionError:
                data = None
            if isinstance(data, dict) and "Lines" in data:
                items = basket_items(data)
                self._amounts = {item.id: item.amount for item in items}
            else:
                self._amounts[product_id] = amount
            if not verify:
                return
            if (await self.async_confirm({product_id: amount})) != {product_id}:
                raise NemligError("Nemlig.com bekræftede ikke antallet. Prøv igen")

    async def async_confirm(self, targets: dict[int, int]) -> set[int]:
        """The products whose quantity in the basket is now the wanted one (one read)."""
        if not targets:
            return set()
        shopping = await self.async_list()
        actual = {item.id: item.amount for item in shopping.items}
        return {pid for pid, amount in targets.items() if actual.get(pid, 0) == amount}

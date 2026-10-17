"""Client for the REMA 1000 Denmark web API.

REMA 1000 has no public API. This client talks to the same endpoints as
rema1000.dk and shop.rema1000.dk, so it may break if REMA changes their site.

Login flow (as used by the webshop):
1. GET  {site}/konto/auth                  -> the site starts an OAuth2/PKCE
                                              authorization and redirects to
                                              login.rema1000.dk
2. POST cphapp.rema1000.dk/api/oauth2/login -> e-mail + password, returns the
                                              authorize URL to continue with
3. GET  that URL                           -> authorize -> {site}/api/auth/callback
                                              which sets access_token and
                                              refresh_token cookies
The access token is a JWT (about 1 hour) sent as a Bearer token to
api.digital.rema1000.dk. It is renewed with POST {site}/api/auth/refresh,
and if that fails we log in again.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import logging
import re
import time
from typing import Any
from urllib.parse import unquote

import aiohttp
from yarl import URL

_LOGGER = logging.getLogger(__name__)

LOGIN_API_URL = "https://cphapp.rema1000.dk/api/oauth2/login"
LOGIN_HOST = "login.rema1000.dk"
LOGIN_ORIGIN = f"https://{LOGIN_HOST}"
# The webshop flow is tried first because it was observed end to end.
SITES = ("https://shop.rema1000.dk", "https://rema1000.dk")
API_BASE = "https://api.digital.rema1000.dk/api"

TJEK_DEFAULT_BASE = "https://squid-api.tjek.com"
TJEK_DEALER_ID = "11deC"  # REMA 1000 Danmark on Tjek / eTilbudsavis

STORE_ID = 1
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
TOKEN_REFRESH_MARGIN = 120  # seconds before expiry we renew the token

BASE_HEADERS = {
    "Accept": "application/json",
    "X-Device": "web",
    "X-Locale": "da",
    "X-Timezone": "Copenhagen/Europe",
}

_AMOUNT_PREFIX = re.compile(r"^\s*(\d+)\s*[x×*]\s*(.+?)\s*$", re.IGNORECASE)


class RemaError(Exception):
    """Base error for the REMA 1000 client."""


class RemaAuthError(RemaError):
    """Login rejected or session can no longer be renewed."""


class RemaConnectionError(RemaError):
    """REMA 1000 could not be reached."""


class RemaApiError(RemaError):
    """REMA 1000 answered with something unexpected."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------- models


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp from the API."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _float(value: Any) -> float | None:
    """Convert a number-ish API value to float."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _name_of(value: Any) -> str | None:
    """Department/category is an object with a name, or sometimes just a name."""
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else None
    return str(value) if value else None


def split_amount(text: str) -> tuple[int, str]:
    """Split '3 x mælk' into (3, 'mælk'). Plain text gives amount 1."""
    if match := _AMOUNT_PREFIX.match(text):
        return max(1, int(match.group(1))), match.group(2)
    return 1, text.strip()


@dataclass(slots=True)
class ShoppingListItem:
    """An item on a shopping list."""

    id: int
    name: str
    bought: bool
    amount: int
    product_id: int | None
    underline: str | None = None
    price: float | None = None
    max_quantity: int = 0
    price_over_max: float | None = None
    deposit: float = 0.0
    is_on_discount: bool = False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ShoppingListItem:
        """Create from an API item."""
        store_item = data.get("store_item") or {}
        pricing = store_item.get("pricing") or {}
        return cls(
            id=int(data["id"]),
            name=str(data.get("name") or store_item.get("name") or ""),
            bought=bool(data.get("bought")),
            amount=int(data.get("amount") or 1),
            product_id=data.get("store_item_id"),
            underline=store_item.get("underline"),
            price=_float(pricing.get("price")),
            max_quantity=int(pricing.get("max_quantity") or 0),
            price_over_max=_float(pricing.get("price_over_max")),
            deposit=_float(pricing.get("deposit")) or 0.0,
            is_on_discount=bool(pricing.get("is_on_discount")),
        )

    @property
    def total_price(self) -> float | None:
        """Price for the whole amount, incl. max-quantity rules and deposit."""
        if self.price is None:
            return None
        amount = self.amount
        if self.max_quantity and amount > self.max_quantity and self.price_over_max:
            total = (
                self.max_quantity * self.price + (amount - self.max_quantity) * self.price_over_max
            )
        else:
            total = amount * self.price
        return round(total + self.deposit * amount, 2)


@dataclass(slots=True)
class ShoppingList:
    """A shopping list with its items."""

    id: int
    name: str
    items: list[ShoppingListItem] = field(default_factory=list)

    @property
    def unbought_total(self) -> float:
        """Estimated price of all items not yet bought."""
        return round(
            sum(item.total_price or 0.0 for item in self.items if not item.bought),
            2,
        )

    def find(self, *, product_id: int | None, name: str | None) -> ShoppingListItem | None:
        """Find an existing item the way REMA's own web code does."""
        wanted = name.strip().lower() if name else None
        for item in self.items:
            if product_id and item.product_id == product_id:
                return item
            if wanted and not product_id and item.name.strip().lower() == wanted:
                return item
        return None


@dataclass(slots=True)
class Product:
    """A product from the REMA 1000 catalogue."""

    id: int
    name: str
    underline: str | None
    department: str | None
    category: str | None
    price: float | None
    normal_price: float | None
    compare_unit: str | None
    compare_unit_price: float | None
    is_advertised: bool
    is_campaign: bool
    price_valid_to: str | None
    upcoming_price: float | None
    upcoming_from: str | None
    upcoming_is_advertised: bool
    is_organic: bool
    labels: list[str]
    image: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], now: datetime | None = None) -> Product:
        """Create from a product search result."""
        now = now or datetime.now(UTC)
        active: list[dict[str, Any]] = []
        upcoming: list[dict[str, Any]] = []
        for price in data.get("prices") or []:
            start = _parse_dt(price.get("starting_at"))
            end = _parse_dt(price.get("ending_at"))
            if start and start > now:
                upcoming.append(price)
            elif end is None or end >= now:
                active.append(price)

        def _price(entry: dict[str, Any]) -> float:
            return _float(entry.get("price")) or float("inf")

        if not data.get("prices") and isinstance(data.get("pricing"), dict):
            # Some endpoints (shopping lists, favourites) give one "pricing" block.
            pricing = data["pricing"]
            active = [
                {
                    "price": pricing.get("price"),
                    "is_advertised": pricing.get("is_advertised"),
                    "is_campaign": pricing.get("is_on_discount"),
                    "ending_at": pricing.get("price_changes_on"),
                }
            ]
            if pricing.get("normal_price") not in (None, pricing.get("price")):
                active.append({"price": pricing.get("normal_price")})

        best = min(active, key=_price) if active else None
        regular = [p for p in active if not p.get("is_campaign") and not p.get("is_advertised")]
        normal = max(regular, key=_price) if regular else best
        next_price = min(upcoming, key=_price) if upcoming else None

        labels = [str(label.get("name")) for label in data.get("labels") or [] if label.get("name")]
        underline = data.get("underline")
        organic = (
            any("økolog" in label.lower() for label in labels)
            or (bool(underline) and "ØKOLOGISK" in str(underline).upper())
            or bool(re.search(r"(^|[^A-ZÆØÅ])ØKO", str(data.get("name") or "").upper()))
        )
        images = data.get("images") or []
        image = None
        if images and isinstance(images[0], dict):
            image = images[0].get("medium") or images[0].get("small")

        return cls(
            id=int(data["id"]),
            name=str(data.get("name") or ""),
            underline=underline,
            department=_name_of(data.get("department")),
            category=_name_of(data.get("category")),
            price=_float(best.get("price")) if best else None,
            normal_price=_float(normal.get("price")) if normal else None,
            compare_unit=best.get("compare_unit") if best else None,
            compare_unit_price=_float(best.get("compare_unit_price")) if best else None,
            is_advertised=bool(best and best.get("is_advertised")),
            is_campaign=bool(best and best.get("is_campaign")),
            price_valid_to=best.get("ending_at") if best else None,
            upcoming_price=_float(next_price.get("price")) if next_price else None,
            upcoming_from=next_price.get("starting_at") if next_price else None,
            upcoming_is_advertised=bool(next_price and next_price.get("is_advertised")),
            is_organic=organic,
            labels=labels,
            image=image,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict."""
        return asdict(self)


@dataclass(slots=True)
class Catalog:
    """A tilbudsavis (offer catalogue) from Tjek."""

    id: str
    label: str | None
    valid_from: datetime | None
    valid_to: datetime | None
    offer_count: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Catalog:
        """Create from a Tjek catalog."""
        return cls(
            id=str(data["id"]),
            label=data.get("label") or data.get("name"),
            valid_from=_parse_dt(data.get("run_from")),
            valid_to=_parse_dt(data.get("run_till")),
            offer_count=data.get("offer_count"),
        )


@dataclass(slots=True)
class Offer:
    """A single offer in a tilbudsavis."""

    id: str
    heading: str
    description: str | None
    price: float | None
    pre_price: float | None
    quantity: str | None
    valid_from: str | None
    valid_to: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Offer:
        """Create from a Tjek offer."""
        pricing = data.get("pricing") or {}
        quantity = data.get("quantity") or {}
        size = quantity.get("size") or {}
        unit = (quantity.get("unit") or {}).get("symbol")
        unit = {"pcs": "stk."}.get(unit, unit) if unit else unit
        pieces = (quantity.get("pieces") or {}).get("from")
        parts: list[str] = []
        if pieces and pieces != 1:
            parts.append(f"{pieces} stk.")
        if size.get("from") and unit:
            parts.append(
                f"{size['from']:g} {unit}"
                if isinstance(size["from"], (int, float))
                else f"{size['from']} {unit}"
            )
        return cls(
            id=str(data.get("id")),
            heading=str(data.get("heading") or ""),
            description=data.get("description"),
            price=_float(pricing.get("price")),
            pre_price=_float(pricing.get("pre_price")),
            quantity=" / ".join(parts) or None,
            valid_from=data.get("run_from"),
            valid_to=data.get("run_till"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict."""
        return asdict(self)


# --------------------------------------------------------------------- client


def _jwt_claims(token: str) -> dict[str, Any]:
    """Decode the payload of a JWT without verifying it."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError) as err:
        raise RemaApiError("Access token could not be read") from err
    if not isinstance(claims, dict):
        raise RemaApiError("Access token could not be read")
    return claims


class RemaClient:
    """Talk to REMA 1000 on behalf of one account."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        """Initialize the client. The session must have its own cookie jar."""
        self._session = session
        self._email = email
        self._password = password
        self._site: str | None = None
        self._access_token: str | None = None
        self._expires_at: float = 0
        self._user_id: int | None = None
        self._lock = asyncio.Lock()
        self._tjek: tuple[str, str] | None = None
        self._favorites: tuple[float, list[Product]] | None = None

    @property
    def user_id(self) -> int | None:
        """Return the REMA user id of the logged-in account."""
        return self._user_id

    # ------------------------------------------------------------ auth

    async def async_login(self) -> int:
        """Log in with e-mail and password. Returns the REMA user id."""
        last_error: RemaError | None = None
        for site in SITES:
            try:
                await self._async_login_via(site)
            except RemaAuthError:
                raise
            except RemaError as err:
                _LOGGER.debug("Login via %s failed: %s", site, err)
                last_error = err
                continue
            assert self._user_id is not None
            return self._user_id
        raise last_error or RemaApiError("Login failed")

    async def _async_login_via(self, site: str) -> None:
        """Run the browser login flow against one of REMA's sites."""
        self._session.cookie_jar.clear()
        # 1. Let the site start the OAuth2/PKCE authorization.
        start = await self._async_fetch(
            "GET",
            f"{site}/konto/auth",
            params={"redirect_uri": "/konto"},
            headers={"Accept": "text/html"},
        )
        if start.host != LOGIN_HOST:
            raise RemaApiError(f"Login did not reach {LOGIN_HOST} (ended at {start.host})")

        # 2. Send the credentials, like login.rema1000.dk does.
        try:
            async with self._session.post(
                LOGIN_API_URL,
                json={"email": self._email, "password": self._password},
                headers={
                    **BASE_HEADERS,
                    "X-Language": "da",
                    "Origin": LOGIN_ORIGIN,
                    "Referer": str(start),
                },
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403, 422):
                    raise RemaAuthError("E-mail or password was rejected")
                if resp.status >= 400:
                    raise RemaApiError(f"Login returned HTTP {resp.status}", resp.status)
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RemaConnectionError(f"Could not reach REMA 1000: {err}") from err

        redirect = data.get("redirect_uri") if isinstance(data, dict) else None
        if not redirect:
            raise RemaApiError("Login response had no redirect_uri")
        redirect = re.sub(r"^http://", "https://", redirect)

        # 3. Follow authorize -> site callback, which sets the token cookies.
        await self._async_fetch("GET", redirect, headers={"Accept": "text/html"})
        token = self._cookie(site, "access_token")
        if not token:
            raise RemaApiError(f"No access token after login via {site}")
        self._site = site
        self._set_token(token)
        _LOGGER.debug("Logged in to REMA 1000 via %s as user %s", site, self._user_id)

    async def _async_fetch(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> URL:
        """Request a page following redirects; return where we ended up."""
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                headers=headers,
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                await resp.read()
                if resp.status >= 400:
                    raise RemaApiError(f"{url} returned HTTP {resp.status}", resp.status)
                return resp.url
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RemaConnectionError(f"Could not reach REMA 1000: {err}") from err

    def _cookie(self, site: str, name: str) -> str | None:
        """Read a cookie the site has set."""
        morsel = self._session.cookie_jar.filter_cookies(URL(site)).get(name)
        return unquote(morsel.value) if morsel and morsel.value else None

    def _set_token(self, token: str) -> None:
        """Store a new access token and read its claims."""
        claims = _jwt_claims(token)
        self._access_token = token
        self._expires_at = float(claims.get("exp") or time.time() + 3000)
        if claims.get("sub") is not None:
            self._user_id = int(claims["sub"])

    async def _async_refresh(self) -> None:
        """Renew the access token using the refresh token cookie."""
        if not self._site:
            raise RemaAuthError("Not logged in")
        try:
            async with self._session.post(
                f"{self._site}/api/auth/refresh",
                headers={**BASE_HEADERS, "Origin": self._site},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status >= 400:
                    raise RemaAuthError(f"Token refresh returned HTTP {resp.status}")
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RemaConnectionError(f"Could not reach REMA 1000: {err}") from err
        token = None
        if isinstance(data, dict):
            token = (data.get("tokens") or {}).get("access_token")
        token = token or self._cookie(self._site, "access_token")
        if not token:
            raise RemaAuthError("Token refresh gave no access token")
        self._set_token(token)

    async def _async_ensure_token(self, force: bool = False) -> None:
        """Make sure we hold a valid access token."""
        async with self._lock:
            if (
                not force
                and self._access_token
                and self._expires_at - time.time() > TOKEN_REFRESH_MARGIN
            ):
                return
            if self._access_token:
                try:
                    await self._async_refresh()
                except RemaConnectionError:
                    raise
                except RemaError as err:
                    _LOGGER.debug("Token refresh failed, logging in again: %s", err)
                else:
                    return
            await self.async_login()

    # ------------------------------------------------------------ requests

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: Any = None,
        retry: bool = True,
    ) -> Any:
        """Call api.digital.rema1000.dk with the access token."""
        await self._async_ensure_token()
        headers = {
            **BASE_HEADERS,
            "Authorization": f"Bearer {self._access_token}",
            "Origin": self._site or SITES[0],
        }
        try:
            async with self._session.request(
                method,
                f"{API_BASE}{path}",
                params=params,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401 and retry:
                    await self._async_ensure_token(force=True)
                    return await self._async_request(
                        method, path, params=params, payload=payload, retry=False
                    )
                if resp.status == 401:
                    raise RemaAuthError("Access token rejected")
                if resp.status >= 400:
                    body = (await resp.text())[:300]
                    raise RemaApiError(
                        f"{method} {path} returned HTTP {resp.status}: {body}", resp.status
                    )
                if resp.status == 204:
                    return None
                text = await resp.text()
                return json.loads(text) if text else None
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RemaConnectionError(f"Could not reach REMA 1000: {err}") from err

    # ------------------------------------------------------------ shopping lists

    async def async_get_lists(self) -> list[dict[str, Any]]:
        """Return the account's shopping lists (raw)."""
        await self._async_ensure_token()
        data = await self._async_request(
            "GET",
            f"/v3/users/{self._user_id}/shopping-lists",
            params={
                "per_page": 100,
                "include": "users,items_count",
                "sort": "-latest_activity_at",
            },
        )
        return list((data or {}).get("data") or [])

    async def async_get_primary_list_id(self) -> int:
        """Return the id of the primary shopping list (the one in the app)."""
        lists = await self.async_get_lists()
        if not lists:
            raise RemaApiError("The account has no shopping lists")
        for entry in lists:
            if entry.get("is_primary"):
                return int(entry["id"])
        return int(lists[0]["id"])

    async def async_get_list(self, list_id: int) -> ShoppingList:
        """Return a shopping list with items."""
        data = await self._async_request(
            "GET", f"/v2/shoppinglists/{list_id}", params={"with": "users,items"}
        )
        return ShoppingList(
            id=int(data["id"]),
            name=str(data.get("name") or ""),
            items=[ShoppingListItem.from_api(item) for item in data.get("items") or []],
        )

    async def async_get_primary_list(self) -> ShoppingList:
        """Return the primary shopping list with items."""
        return await self.async_get_list(await self.async_get_primary_list_id())

    async def async_create_item(
        self,
        list_id: int,
        *,
        amount: int = 1,
        product_id: int | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Add a product (by id) or a free-text item to a list."""
        payload: dict[str, Any] = {"amount": amount, "store_id": STORE_ID}
        if product_id:
            payload["store_item_id"] = product_id
        elif name:
            payload["name"] = name
        else:
            raise ValueError("product_id or name is required")
        result: dict[str, Any] = await self._async_request(
            "POST", f"/v2/shoppinglists/{list_id}/items", payload=payload
        )
        return result

    async def async_update_item(self, list_id: int, item_id: int, **changes: Any) -> dict[str, Any]:
        """Change amount, bought state or name of an item."""
        result: dict[str, Any] = await self._async_request(
            "PATCH", f"/v2/shoppinglists/{list_id}/items/{item_id}", payload=changes
        )
        return result

    async def async_delete_items(self, list_id: int, item_ids: list[int]) -> None:
        """Delete items from a list (one request, like the webshop)."""
        if not item_ids:
            return
        await self._async_request(
            "PATCH",
            f"/v2/shoppinglists/{list_id}",
            payload={"items": [{"id": item_id, "delete": True} for item_id in item_ids]},
        )

    async def async_add_to_list(
        self,
        shopping_list: ShoppingList,
        *,
        amount: int = 1,
        product_id: int | None = None,
        name: str | None = None,
    ) -> None:
        """Add to a list, merging with an existing line like REMA's app does.

        A line that was already bought starts over at the new amount instead of
        adding to what was bought last time, and is always set back to unbought.
        """
        existing = shopping_list.find(product_id=product_id, name=name)
        if existing is None:
            await self.async_create_item(
                shopping_list.id, amount=amount, product_id=product_id, name=name
            )
            return
        new_amount = amount if existing.bought else existing.amount + amount
        await self.async_update_item(shopping_list.id, existing.id, amount=new_amount, bought=False)
        existing.amount = new_amount
        existing.bought = False

    # ------------------------------------------------------------ products

    async def async_search_products(
        self, query: str, limit: int = 24, at: datetime | None = None
    ) -> list[Product]:
        """Search the REMA 1000 catalogue, priced as of now or a later time."""
        data = await self._async_request(
            "GET",
            "/search/products",
            params={"per_page": max(1, min(limit, 100)), "page": 1, "query": query},
        )
        now = at or datetime.now(UTC)
        products: list[Product] = []
        for entry in (data or {}).get("data") or []:
            try:
                products.append(Product.from_api(entry, now))
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.debug("Skipping product that could not be read: %s", err)
        return products

    async def async_get_favorites(self, force: bool = False) -> list[Product]:
        """The account's favourite products (the hearts in the app), with prices.

        Cached for 15 minutes; the list can be a few hundred products long.
        """
        if not force and self._favorites and time.monotonic() - self._favorites[0] < 900:
            return self._favorites[1]
        await self._async_ensure_token()
        now = datetime.now(UTC)
        products: list[Product] = []
        seen: set[int] = set()
        page = 1
        while page <= 40:
            data = await self._async_request(
                "GET",
                f"/v3/users/{self._user_id}/favorites",
                params={"include": "product", "page": page, "per_page": 100},
            )
            entries = list((data or {}).get("data") or [])
            for entry in entries:
                raw = entry.get("product") if isinstance(entry, dict) else None
                if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
                    raw = raw["data"]  # some APIs wrap includes in {"data": ...}
                if not isinstance(raw, dict):
                    raw = entry if isinstance(entry, dict) and entry.get("name") else None
                if not raw or not raw.get("id") or not raw.get("name"):
                    continue
                try:
                    product = Product.from_api(raw, now)
                except (KeyError, TypeError, ValueError) as err:
                    _LOGGER.debug("Skipping favourite that could not be read: %s", err)
                    continue
                if product.id not in seen:
                    seen.add(product.id)
                    products.append(product)
            pagination = ((data or {}).get("meta") or {}).get("pagination") or {}
            last_page = pagination.get("last_page") or page
            if not entries or page >= last_page:
                break
            page += 1
        self._favorites = (time.monotonic(), products)
        return products

    # ------------------------------------------------------------ offers (Tjek)

    async def _async_tjek_config(self) -> tuple[str, str]:
        """Read the public Tjek API key from the webshop's runtime config."""
        if self._tjek:
            return self._tjek
        html = ""
        for site in SITES:
            try:
                async with self._session.get(
                    f"{site}/", headers={"Accept": "text/html"}, timeout=REQUEST_TIMEOUT
                ) as resp:
                    if resp.status < 400:
                        html = await resp.text()
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("Could not load %s for Tjek config: %s", site, err)
                continue
            if "tjek" in html:
                break
        block = re.search(r"tjek:\{([^}]*)\}", html)
        key = re.search(r'api_key:"([^"]+)"', block.group(1)) if block else None
        if not key:
            raise RemaApiError("Could not find the offer (Tjek) API key on rema1000.dk")
        base = re.search(r'api_base_url:"([^"]+)"', block.group(1)) if block else None
        self._tjek = (base.group(1) if base else TJEK_DEFAULT_BASE, key.group(1))
        return self._tjek

    async def _async_tjek(self, path: str, params: dict[str, Any]) -> Any:
        """Call the Tjek API."""
        base, key = await self._async_tjek_config()
        try:
            async with self._session.get(
                f"{base}{path}",
                params={**params, "api_key": key},
                headers={"Accept": "application/json", "X-Api-Key": key},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    self._tjek = None  # key may have rotated, read it again next time
                if resp.status >= 400:
                    body = (await resp.text())[:300]
                    raise RemaApiError(
                        f"Tjek {path} returned HTTP {resp.status}: {body}", resp.status
                    )
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RemaConnectionError(f"Could not reach Tjek: {err}") from err

    async def async_get_catalogs(self) -> list[Catalog]:
        """Return REMA 1000's current and upcoming tilbudsaviser."""
        data = await self._async_tjek(
            "/v2/catalogs", {"dealer_ids": TJEK_DEALER_ID, "limit": 24, "offset": 0}
        )
        catalogs: list[Catalog] = []
        for entry in data or []:
            try:
                catalogs.append(Catalog.from_api(entry))
            except (KeyError, TypeError) as err:
                _LOGGER.debug("Skipping catalog that could not be read: %s", err)
        return catalogs

    async def async_get_offers(self, catalog_id: str, max_offers: int = 1000) -> list[Offer]:
        """Return all offers in a tilbudsavis."""
        offers: list[Offer] = []
        offset = 0
        page_size = 100
        while offset < max_offers:
            data = await self._async_tjek(
                "/v2/offers",
                {"catalog_ids": catalog_id, "limit": page_size, "offset": offset},
            )
            page = list(data or [])
            offers.extend(Offer.from_api(entry) for entry in page)
            if len(page) < page_size:
                break
            offset += page_size
        return offers

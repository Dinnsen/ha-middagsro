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
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, time as clock_time, timedelta
import json
import logging
import re
import time
from typing import Any
from urllib.parse import unquote
from zoneinfo import ZoneInfo

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
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, sock_connect=10)
TOKEN_REFRESH_MARGIN = 120  # seconds before expiry we renew the token
# A busy or briefly broken server: try again after a moment, twice.
RETRY_STATUSES = frozenset({429, 502, 503, 504})
RETRY_DELAYS = (1.0, 3.0)
PRIMARY_LIST_TTL = 15 * 60  # seconds the primary list's id is remembered
OFFER_PRODUCTS_TTL = 6 * 3600  # seconds Tjek's products of an offer are remembered
TJEK_CONFIG_RETRY = 5 * 60  # seconds before the Tjek key is looked for again after a failure

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


# How long the last prices still count when REMA has none for the moment.
PRICE_GAP = timedelta(days=2)
DANISH_TIME = ZoneInfo("Europe/Copenhagen")


def week_end(moment: datetime) -> datetime:
    """The first sunday 00:00 UTC at or after a moment: when REMA's new prices start.

    That is 02:00 danish summer time (01:00 in winter).
    """
    utc = moment.astimezone(UTC)
    sunday = utc.date() + timedelta(days=(6 - utc.weekday()) % 7)
    turn = datetime.combine(sunday, clock_time(), UTC)
    if turn < utc:
        turn = datetime.combine(sunday + timedelta(days=7), clock_time(), UTC)
    return turn


def parse_time(value: Any) -> datetime | None:
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
        ended: list[tuple[datetime, dict[str, Any]]] = []
        latest_start: datetime | None = None  # of the prices that apply now
        for price in data.get("prices") or []:
            start = parse_time(price.get("starting_at"))
            end = parse_time(price.get("ending_at"))
            if start and start > now:
                upcoming.append(price)
            elif end is None or end >= now:
                active.append(price)
                if start and (latest_start is None or start > latest_start):
                    latest_start = start
            else:
                ended.append((end, price))
        # REMA's prices for a week end before the avis does (the avis runs to
        # saturday night), so a price that ended still applies until REMA's
        # new prices start (sunday 02:00 danish time), unless one replaced it.
        active += [
            price
            for end, price in ended
            if now < week_end(end) and (latest_start is None or latest_start < end)
        ]
        if not active and ended:
            # Sunday night, before the new week's prices start: the last ones.
            last = max(end for end, _ in ended)
            if now - last <= PRICE_GAP:
                active = [price for end, price in ended if last - end <= timedelta(hours=1)]

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

        def plain(entry: dict[str, Any]) -> bool:
            return not entry.get("is_campaign") and not entry.get("is_advertised")

        regular = [p for p in active if plain(p)]
        if not regular:
            # During an offer REMA often has no normal price at the same time:
            # use the one that comes after the offer, else the one before it.
            after = [p for p in upcoming if plain(p)]
            before = [(end, p) for end, p in ended if plain(p)]
            if after:
                regular = [min(after, key=lambda p: parse_time(p.get("starting_at")) or now)]
            elif before:
                regular = [max(before, key=lambda item: item[0])[1]]
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
            valid_from=parse_time(data.get("run_from")),
            valid_to=parse_time(data.get("run_till")),
            offer_count=data.get("offer_count"),
        )

    def runs_within(self, other: Catalog) -> bool:
        """True if this avis runs inside another one's period."""
        return bool(
            self.valid_from
            and self.valid_to
            and other.valid_from
            and other.valid_to
            and other.valid_from <= self.valid_from
            and self.valid_to <= other.valid_to
        )


_NUTRITION_NAMES = {
    "fedt": "fat_g",
    "kulhydrat": "carbs_g",
    "kostfibre": "fiber_g",
    "protein": "protein_g",
    "salt": "salt_g",
}


def parse_nutrition(entries: Any) -> dict[str, float]:
    """REMA's nutrition table (per 100 g/ml): 'Energi' '932 KJ / 224 kcal', 'Fedt' '16', '< 0,5'."""
    out: dict[str, float] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip().lower()
        value = str(entry.get("value") or "")
        if name == "energi":
            match = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", value, re.IGNORECASE)
            if match:
                out["kcal"] = float(match.group(1).replace(",", "."))
            continue
        key = _NUTRITION_NAMES.get(name)
        match = re.search(r"\d+(?:[.,]\d+)?", value)
        if key and match:
            # "< 0,5" is next to nothing.
            out[key] = 0.0 if "<" in value else float(match.group(0).replace(",", "."))
    return out if "kcal" in out else {}


def is_insert(catalog: Catalog, catalogs: list[Catalog]) -> bool:
    """An insert (indstik): a smaller avis inside another avis's week.

    "Uge 42 Indstik" (thursday to saturday, 12 offers) runs inside "Uge 42",
    and its offers are in the week's avis too. It is out on wednesday, before
    it starts, so it must not be taken for next week's avis. A month-long avis
    without offers ("Meget mere sæson") holds no inserts.
    """
    return any(
        other.id != catalog.id
        and catalog.runs_within(other)
        and (other.offer_count or 0) > 0
        and (other.offer_count or 0) >= (catalog.offer_count or 0)
        and other.valid_from is not None
        and other.valid_to is not None
        and catalog.valid_from is not None
        and catalog.valid_to is not None
        and other.valid_to - other.valid_from > catalog.valid_to - catalog.valid_from
        for other in catalogs
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
    # REMA's product ids for the offer (from Tjek); None when not looked up.
    product_ids: tuple[int, ...] | None = None
    # The names Tjek gives the offer's products ("REMA 1000 laksefilet 600g").
    product_names: tuple[str, ...] = ()
    # Tjek lists products without a REMA id (or none at all), so the ids are
    # not the whole offer: other products may still fit it by name.
    unlinked: bool = False
    # Tjek's names for those products ("Arla Skyr Airy Jordbær").
    unlinked_names: tuple[str, ...] = ()

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


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def _json_or_error(text: str, what: str) -> Any:
    """The body as JSON; a page of HTML (maintenance, bot check) is an API error."""
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError as err:
        raise RemaApiError(f"{what} did not return JSON: {text[:80]!r}") from err


def _retry_after(header: str | None, default: float) -> float:
    """Seconds to wait as the server asks (at most a minute), else the default."""
    try:
        return min(60.0, max(0.5, float(header or "")))
    except ValueError:
        return default


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
        self._tjek_lock = asyncio.Lock()
        self._tjek_failed_at: float | None = None
        self._favorites: tuple[float, list[Product]] | None = None
        self._nutrition: dict[int, dict[str, float]] = {}
        self._offer_products: dict[
            str, tuple[float, tuple[tuple[int, ...], tuple[str, ...], tuple[str, ...]]]
        ] = {}
        self._primary_list: tuple[float, int] | None = None

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
                text = await resp.text()
                if resp.status in (401, 422) or (resp.status == 400 and _is_json(text)):
                    # The login service itself says no: wrong e-mail or password.
                    raise RemaAuthError("E-mail or password was rejected")
                if resp.status >= 400:
                    # Bot protection, maintenance, a 403 or a 5xx: REMA is unhappy
                    # right now, which is no reason to ask for the password again.
                    raise RemaApiError(f"Login returned HTTP {resp.status}", resp.status)
                data = _json_or_error(text, "login")
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
                if resp.status in RETRY_STATUSES or resp.status >= 500:
                    # REMA is busy: not a reason to log in again with the password.
                    raise RemaConnectionError(f"Token refresh returned HTTP {resp.status}")
                if resp.status >= 400:
                    raise RemaAuthError(f"Token refresh returned HTTP {resp.status}")
                data = _json_or_error(await resp.text(), "token refresh")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RemaConnectionError(f"Could not reach REMA 1000: {err}") from err
        token = None
        if isinstance(data, dict):
            token = (data.get("tokens") or {}).get("access_token")
        token = token or self._cookie(self._site, "access_token")
        if not token:
            raise RemaAuthError("Token refresh gave no access token")
        self._set_token(token)

    async def _async_ensure_token(self, stale: str | None = None) -> None:
        """Make sure we hold a valid access token.

        ``stale``: a token REMA just rejected. If another request already renewed
        it meanwhile, the new one is used; otherwise it is renewed once.
        """
        async with self._lock:
            if stale is not None and self._access_token != stale:
                return  # renewed by another request already
            if (
                stale is None
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
        """Call api.digital.rema1000.dk with the access token.

        A rejected token is renewed once. A busy server (429, 502-504) is tried
        again after a moment, twice, when the request can safely be repeated.
        """
        await self._async_ensure_token()
        token = self._access_token
        headers = {
            **BASE_HEADERS,
            "Authorization": f"Bearer {token}",
            "Origin": self._site or SITES[0],
        }
        attempt = 0
        while True:
            delay = 0.0
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
                        await self._async_ensure_token(stale=token)
                        return await self._async_request(
                            method, path, params=params, payload=payload, retry=False
                        )
                    if resp.status == 401:
                        # Just renewed and still refused: REMA's side, try later.
                        raise RemaApiError("Access token rejected after renewal", 401)
                    if (
                        resp.status in RETRY_STATUSES
                        and attempt < len(RETRY_DELAYS)
                        and (method == "GET" or path == "/v3/batch")  # both only read
                    ):
                        delay = _retry_after(resp.headers.get("Retry-After"), RETRY_DELAYS[attempt])
                        attempt += 1
                        _LOGGER.debug(
                            "%s %s: HTTP %s, trying again in %ss", method, path, resp.status, delay
                        )
                    elif resp.status >= 400:
                        body = (await resp.text())[:300]
                        raise RemaApiError(
                            f"{method} {path} returned HTTP {resp.status}: {body}", resp.status
                        )
                    else:
                        if resp.status == 204:
                            return None
                        return _json_or_error(await resp.text(), f"{method} {path}")
            except (aiohttp.ClientError, TimeoutError) as err:
                raise RemaConnectionError(f"Could not reach REMA 1000: {err}") from err
            await asyncio.sleep(delay)

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

    async def async_get_primary_list_id(self, force: bool = False) -> int:
        """The id of the primary shopping list (the one in the app), remembered a while."""
        if (
            not force
            and self._primary_list
            and time.monotonic() - self._primary_list[0] < PRIMARY_LIST_TTL
        ):
            return self._primary_list[1]
        lists = [entry for entry in await self.async_get_lists() if isinstance(entry, dict)]
        if not lists:
            raise RemaApiError("The account has no shopping lists")
        chosen = next((entry for entry in lists if entry.get("is_primary")), lists[0])
        try:
            list_id = int(chosen["id"])
        except (KeyError, TypeError, ValueError) as err:
            raise RemaApiError("The shopping lists have no id") from err
        self._primary_list = (time.monotonic(), list_id)
        return list_id

    async def async_get_list(self, list_id: int) -> ShoppingList:
        """Return a shopping list with items."""
        data = await self._async_request(
            "GET", f"/v2/shoppinglists/{list_id}", params={"with": "users,items"}
        )
        if not isinstance(data, dict) or "id" not in data:
            raise RemaApiError(f"Shopping list {list_id} came back without data")
        return ShoppingList(
            id=int(data["id"]),
            name=str(data.get("name") or ""),
            items=[
                ShoppingListItem.from_api(item)
                for item in data.get("items") or []
                if isinstance(item, dict)
            ],
        )

    async def async_get_primary_list(self) -> ShoppingList:
        """Return the primary shopping list with items.

        If the remembered list is gone (deleted, or another made primary in the
        app), the lists are read again.
        """
        try:
            return await self.async_get_list(await self.async_get_primary_list_id())
        except RemaApiError as err:
            if err.status not in (403, 404) or self._primary_list is None:
                raise
            return await self.async_get_list(await self.async_get_primary_list_id(force=True))

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

    # ------------------------------------------------------------------ recipes

    async def async_get_recipes(
        self,
        *,
        tag: str | None = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "-popularity",
        query: str | None = None,
    ) -> dict[str, Any]:
        """A page of REMA 1000's own recipes (raw entities and pagination), or a search."""
        if query:
            data = await self._async_request(
                "GET",
                "/search/recipes",
                params={"query": query, "page": page, "per_page": per_page},
            )
            return data if isinstance(data, dict) else {}
        params: dict[str, Any] = {
            "filter[type]": "recipe",
            "per_page": per_page,
            "page": page,
            "sort": sort,
        }
        if tag:
            params["filter[tags.sys.id]"] = tag
        data = await self._async_request("GET", "/rema1000dk/entities", params=params)
        return data if isinstance(data, dict) else {}

    async def async_get_recipe(self, slug: str) -> dict[str, Any] | None:
        """One of REMA 1000's recipes by its slug (raw entity), or None."""
        data = await self._async_request(
            "GET", "/rema1000dk/entities", params={"filter[type]": "recipe", "filter[slug]": slug}
        )
        items = (data or {}).get("data") if isinstance(data, dict) else None
        return (
            items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else None
        )

    async def async_search_products(
        self, query: str, limit: int = 24, at: datetime | None = None
    ) -> list[Product]:
        """Search the REMA 1000 catalogue, priced as of now or a later time."""
        return (await self.async_search_products_at(query, limit, [at or datetime.now(UTC)]))[0]

    async def async_search_products_at(
        self, query: str, limit: int, times: list[datetime]
    ) -> list[list[Product]]:
        """Search once and price the results at each of several times."""
        data = await self._async_request(
            "GET",
            "/search/products",
            params={"per_page": max(1, min(limit, 100)), "page": 1, "query": query},
        )
        priced: list[list[Product]] = [[] for _ in times]
        for entry in (data or {}).get("data") or []:
            try:
                versions = [Product.from_api(entry, moment) for moment in times]
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.debug("Skipping product that could not be read: %s", err)
                continue
            for products, product in zip(priced, versions, strict=True):
                products.append(product)
        return priced

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
        """Read the public Tjek API key from the webshop's runtime config.

        One request at a time, and after a failure not again for a few minutes
        (so a burst of offer lookups doesn't download the front page eight times).
        """
        async with self._tjek_lock:
            if self._tjek:
                return self._tjek
            failed = self._tjek_failed_at
            if failed is not None and time.monotonic() - failed < TJEK_CONFIG_RETRY:
                raise RemaApiError("The offer (Tjek) API key could not be read a moment ago")
            try:
                self._tjek = await self._async_read_tjek_config()
            except RemaError:
                self._tjek_failed_at = time.monotonic()
                raise
            self._tjek_failed_at = None
            return self._tjek

    async def _async_read_tjek_config(self) -> tuple[str, str]:
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
        return (base.group(1) if base else TJEK_DEFAULT_BASE, key.group(1))

    async def _async_tjek(
        self, path: str, params: dict[str, Any], payload: dict[str, Any] | None = None
    ) -> Any:
        """Call the Tjek API (GET, or POST with a payload)."""
        base, key = await self._async_tjek_config()
        attempt = 0
        while True:
            delay = 0.0
            try:
                async with self._session.request(
                    "GET" if payload is None else "POST",
                    f"{base}{path}",
                    params={**params, "api_key": key},
                    json=payload,
                    headers={"Accept": "application/json", "X-Api-Key": key},
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status in (401, 403):
                        self._tjek = None  # key may have rotated, read it again next time
                    if resp.status in RETRY_STATUSES and attempt < len(RETRY_DELAYS):
                        delay = _retry_after(resp.headers.get("Retry-After"), RETRY_DELAYS[attempt])
                        attempt += 1
                    elif resp.status >= 400:
                        body = (await resp.text())[:300]
                        raise RemaApiError(
                            f"Tjek {path} returned HTTP {resp.status}: {body}", resp.status
                        )
                    else:
                        return _json_or_error(await resp.text(), f"Tjek {path}")
            except (aiohttp.ClientError, TimeoutError) as err:
                raise RemaConnectionError(f"Could not reach Tjek: {err}") from err
            await asyncio.sleep(delay)

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

    async def async_get_offer_products(self, offers: list[Offer]) -> list[Offer]:
        """The offers with the REMA products each one is for (``product_ids``).

        Tjek knows which of REMA's products an offer covers (the webshop shows
        them when an offer is opened). An offer that can't be looked up keeps
        ``product_ids=None``. Products Tjek lists without a REMA id (a brand
        REMA's webshop doesn't link, e.g. *Arla Skyr Airy*) make the offer
        ``unlinked``: the ids are then not all of it. ``product_names`` are
        Tjek's names for the products, also those REMA's webshop doesn't sell
        (a *partivare*, only in the shops).
        """
        semaphore = asyncio.Semaphore(6)
        now = time.monotonic()
        failed: list[str] = []

        def cached(offer_id: str) -> bool:
            entry = self._offer_products.get(offer_id)
            return entry is not None and now - entry[0] < OFFER_PRODUCTS_TTL

        async def lookup(offer: Offer) -> None:
            if cached(offer.id):
                return
            async with semaphore:
                try:
                    data = await self._async_tjek(
                        "/v4/rpc/get_offer_products", {}, {"id": offer.id}
                    )
                except RemaError as err:
                    failed.append(str(err))
                    return
            if not isinstance(data, dict):
                failed.append(f"offer {offer.id}: no data")
                return
            entries = [
                entry
                for entry in (data or {}).get("offer_products") or []
                if isinstance(entry, dict)
            ]
            ids = [
                int(entry["external_id"])
                for entry in entries
                if str(entry.get("external_id") or "").isdigit()
            ]
            names = [str(entry.get("name") or "").strip() for entry in entries]
            unlinked = [
                name
                for entry, name in zip(entries, names, strict=True)
                if not str(entry.get("external_id") or "").isdigit()
            ]
            self._offer_products[offer.id] = (
                now,
                (
                    tuple(dict.fromkeys(ids)),
                    tuple(dict.fromkeys(n for n in names if n)),
                    # None listed at all: unlinked too, with no names to go by.
                    tuple(unlinked) if entries else ("",),
                ),
            )

        await asyncio.gather(*(lookup(offer) for offer in offers))
        if failed:
            _LOGGER.warning(
                "%d of %d offer lookups at Tjek failed (last: %s); some offers won't be "
                "matched to REMA's products",
                len(failed),
                len(offers),
                failed[-1],
            )
        if len(self._offer_products) > 5000:  # a year of aviser: forget the oldest
            for key in sorted(self._offer_products, key=lambda k: self._offer_products[k][0])[
                :2500
            ]:
                del self._offer_products[key]
        found: list[Offer] = []
        for offer in offers:
            if offer.id not in self._offer_products:
                found.append(offer)
                continue
            ids, names, unlinked = self._offer_products[offer.id][1]
            found.append(
                replace(
                    offer,
                    product_ids=ids,
                    product_names=names,
                    unlinked=bool(unlinked),
                    unlinked_names=tuple(n for n in unlinked if n),
                )
            )
        return found

    async def async_get_products(
        self, product_ids: list[int], at: datetime | None = None
    ) -> list[Product]:
        """REMA products by id, priced as of now or a later time."""
        moment = at or datetime.now(UTC)
        products: list[Product] = []
        for start in range(0, len(product_ids), 20):
            chunk = product_ids[start : start + 20]
            data = await self._async_request(
                "POST",
                "/v3/batch",
                payload={
                    "requests": [
                        {"uri": f"/api/v3/products/{pid}", "method": "GET"} for pid in chunk
                    ]
                },
            )
            for answer in data or []:
                body = answer.get("body") if isinstance(answer, dict) else None
                entry = body.get("data") if isinstance(body, dict) else None
                if not isinstance(entry, dict) or answer.get("status") != 200:
                    continue
                try:
                    products.append(Product.from_api(entry, moment))
                except (KeyError, TypeError, ValueError) as err:
                    _LOGGER.debug("Skipping product that could not be read: %s", err)
        return products

    async def async_get_nutrition(self, product_ids: list[int]) -> dict[int, dict[str, float]]:
        """REMA's nutrition per 100 g/ml for products (as the app shows it), cached.

        Products without nutrition (fruit and vegetables, free text) are left out.
        """
        cache = self._nutrition
        semaphore = asyncio.Semaphore(6)

        async def lookup(pid: int) -> None:
            async with semaphore:
                try:
                    data = await self._async_request(
                        "GET", f"/v3/products/{pid}", params={"include": "nutrition_info"}
                    )
                except RemaError as err:
                    _LOGGER.debug("Nutrition of %s not found: %s", pid, err)
                    return
            entry = (data or {}).get("data") if isinstance(data, dict) else None
            cache[pid] = parse_nutrition((entry or {}).get("nutrition_info"))

        await asyncio.gather(
            *(lookup(pid) for pid in dict.fromkeys(product_ids) if pid not in cache)
        )
        if len(cache) > 3000:
            for pid in list(cache)[:1500]:  # the oldest looked up
                del cache[pid]
        return {pid: cache[pid] for pid in product_ids if cache.get(pid)}

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
            for entry in page:
                try:
                    offers.append(Offer.from_api(entry))
                except (KeyError, TypeError, ValueError, AttributeError) as err:
                    _LOGGER.debug("Skipping offer that could not be read: %s", err)
            if len(page) < page_size:
                break
            offset += page_size
        return offers

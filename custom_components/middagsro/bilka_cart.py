"""BilkaToGo account and cart, using the webshop's observed login flow."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import re
import time
from typing import Any

import aiohttp

from .api import RemaAuthError, RemaConnectionError, ShoppingList, ShoppingListItem
from .bilka import _SCRIPT, SCRIPT_LIMIT, SITE, TIMEOUT, BilkaError, BilkaSearch, _kr

CONF_PICKUP = "bilka_pickup"
CONF_PICKUP_NAME = "bilka_pickup_name"
CONF_PRICE_STORE = "bilka_price_store"
API = "https://api.bilkatogo.dk/api"
IDENTITY = "https://accounts.eu1.gigya.com"
_LOGIN_KEY = re.compile(r'NUXT_ENV_GIGYA_API_KEY:"([A-Za-z0-9_-]+)"')
_LOGIN_HOST = re.compile(r'NUXT_ENV_GIGYA_BASE_URL:"([^"]+)"')
LOCATION_CHECK = 300  # seconds the active pickup store is trusted before a cart change


def cart_items(data: dict[str, Any], store_id: str) -> list[ShoppingListItem]:
    """Read products only; packaging and packing service are not groceries."""
    items: list[ShoppingListItem] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            if node.get("headline") in ("Services", "Emballage"):
                return
            product = node.get("product")
            if isinstance(product, dict) and "quantity" in node:
                try:
                    pid = int(product.get("objectID") or product["id"])
                    amount = int(node["quantity"])
                except (KeyError, TypeError, ValueError):
                    raise BilkaError("BilkaToGo returned an invalid cart line") from None
                if amount > 0:
                    local = (product.get("storeData") or {}).get(store_id) or {}
                    items.append(
                        ShoppingListItem(
                            id=pid,
                            product_id=pid,
                            name=str(product.get("name") or pid),
                            bought=False,
                            amount=amount,
                            price=_kr(local.get("price"))
                            or _kr(product.get("sales_price"))
                            or _kr(product.get("price")),
                        )
                    )
            else:
                for child in node.values():
                    visit(child)

    visit(data.get("lines", []))
    return items


def _locations(data: dict[str, Any]) -> list[dict[str, str]]:
    """The physical Bilka stores in an AvailableDeliveryAddresses answer."""
    return [
        {"id": str(a["id"]), "name": str(a["name"]), "sid": str(a["sid"]), "zip": str(a["zip"])}
        for a in data.get("addresses") or []
        if isinstance(a, dict)
        and a.get("facility") == 3
        and all(a.get(key) for key in ("id", "name", "sid", "zip"))
    ]


class BilkaCart:
    """An account's remote cart. Never performs checkout or chooses a time slot."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        search: BilkaSearch,
        email: str,
        password: str,
        pickup: str = "",
    ) -> None:
        """Keep credentials in the config entry; tokens live only in memory."""
        self.session = session
        self.search = search
        self.email = email
        self.password = password
        self.pickup = pickup
        self.store_id = search.store_id
        self.pickup_name = ""
        self.user_id: int | None = None
        self._jwt: str | None = None
        self._expires = 0.0
        self._login_key: str | None = None
        self._login_lock = asyncio.Lock()
        self._change = asyncio.Lock()
        self._amounts: dict[int, int] = {}  # the cart as last read or set here
        self._location_checked = 0.0

    async def _json(
        self,
        url: str,
        *,
        method: str = "GET",
        fields: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        jwt: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Origin": SITE, "Referer": f"{SITE}/"}
        if jwt:
            # Bilka's backend incorrectly treats this header as case-sensitive.
            headers["jwt_token"] = jwt
        try:
            async with self.session.request(
                method,
                url,
                data=fields,
                params=params,
                headers=headers,
                timeout=TIMEOUT,
                allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise RemaAuthError("BilkaToGo authentication was rejected")
                if response.status != 200:
                    raise BilkaError(f"BilkaToGo answered HTTP {response.status}")
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            # Do not expose request URLs, credentials or response bodies in diagnostics.
            raise RemaConnectionError("Could not read BilkaToGo") from None
        if not isinstance(data, dict):
            raise BilkaError("BilkaToGo returned an unexpected response")
        return data

    async def _key(self) -> str:
        if self._login_key:
            return self._login_key
        page = await self.search._async_text(f"{SITE}/", 2_000_000)
        for src in reversed(list(dict.fromkeys(_SCRIPT.findall(page)))):
            bundle = await self.search._async_text(f"{SITE}{src}", SCRIPT_LIMIT)
            key, host = _LOGIN_KEY.search(bundle), _LOGIN_HOST.search(bundle)
            if key and host and host.group(1) == IDENTITY:
                self._login_key = key.group(1)
                return self._login_key
        raise BilkaError("BilkaToGo's login settings were not found")

    async def async_login(self, *, force: bool = False) -> int:
        """Salling login -> JWT -> Bilka account session."""
        async with self._login_lock:
            if not force and self.user_id and time.monotonic() < self._expires:
                return self.user_id
            try:
                key = await self._key()
            except (aiohttp.ClientError, TimeoutError):
                raise RemaConnectionError("Could not read BilkaToGo login settings") from None
            login = await self._json(
                f"{IDENTITY}/accounts.login",
                method="POST",
                fields={
                    "apiKey": key,
                    "loginID": self.email,
                    "password": self.password,
                    "include": "profile",
                    "httpStatusCodes": "true",
                },
            )
            if login.get("errorCode", 0):
                raise RemaAuthError("Salling Group login requires authentication")
            token = (login.get("sessionInfo") or {}).get("cookieValue")
            if not token:
                raise RemaAuthError("Salling Group login requires an additional step")
            jwt = await self._json(
                f"{IDENTITY}/accounts.getJWT",
                method="POST",
                fields={
                    "apiKey": key,
                    "login_token": str(token),
                    "expiration": "86400",
                    "httpStatusCodes": "true",
                },
            )
            access = jwt.get("id_token")
            if jwt.get("errorCode", 0) or not isinstance(access, str) or not access:
                raise RemaAuthError("Salling Group did not issue a login token")
            auth = await self._json(
                f"{API}/auth/LoginJWT",
                method="POST",
                fields={},
                params={"u": "w"},
                jwt=access,
            )
            uid = auth.get("uid")
            if not isinstance(uid, int) or uid <= 0:
                raise RemaAuthError("BilkaToGo did not confirm the account")
            self._jwt = access
            self._expires = time.monotonic() + 23 * 3600
            self.user_id = uid
            return uid

    async def _shop(
        self,
        action: str,
        *,
        version: int = 6,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.async_login()
        for attempt in (0, 1):
            try:
                return await self._json(
                    f"{API}/shop/v{version}/{action}",
                    params={"u": "w", **(params or {})},
                    jwt=self._jwt,
                )
            except RemaAuthError:
                if attempt:
                    raise
                await self.async_login(force=True)
        raise RemaAuthError("BilkaToGo login expired")

    async def async_locations(self) -> list[dict[str, str]]:
        """Physical Bilka stores only, not private addresses or delivery slots."""
        return _locations(
            await self._shop("AvailableDeliveryAddresses", params={"orderByZipcode": 1})
        )

    async def async_select_location(self, *, force: bool = True) -> None:
        """Make the configured store the active pickup store in the BilkaToGo app.

        The configuration warns about this: the cart's prices and assortment are
        the active store's, so it is set when Home Assistant logs in and checked
        again (and set back, if it was changed in the app) before changes to the
        cart. It never chooses a pickup time.
        """
        if not force and time.monotonic() - self._location_checked < LOCATION_CHECK:
            return
        data = await self._shop("AvailableDeliveryAddresses", params={"orderByZipcode": 1})
        chosen = next((a for a in _locations(data) if a["id"] == self.pickup), None)
        if chosen is None:
            raise BilkaError("Vælg et Bilka-varehus, der findes, under Omkonfigurér")
        if str((data.get("activeAddress") or {}).get("id")) != self.pickup:
            await self._shop(
                "SetDeliveryAddress", params={"id": self.pickup, "zipcode": chosen["zip"]}
            )
            checked = await self._shop("AvailableDeliveryAddresses", params={"orderByZipcode": 1})
            if str((checked.get("activeAddress") or {}).get("id")) != self.pickup:
                raise BilkaError("BilkaToGo skiftede ikke til det valgte varehus. Prøv igen")
        self.store_id, self.pickup_name = chosen["sid"], chosen["name"]
        self.search.set_store(self.store_id)
        self._location_checked = time.monotonic()

    async def async_list(self) -> ShoppingList:
        """The current cart, excluding checkout services."""
        data = await self._shop(
            "Cart", params={"without_cache": 1, "extra": "deliveryAddress,deliveryDate"}
        )
        if data.get("uid") != self.user_id:
            raise RemaAuthError("BilkaToGo did not return the account's cart")
        items = cart_items(data, self.store_id)
        self._amounts = {item.id: item.amount for item in items}
        return ShoppingList(id=1, name="BilkaToGo", items=items)

    def amount(self, product_id: int, shopping_list: ShoppingList | None = None) -> int:
        """How many of a product the cart has, as last read or set here."""
        if product_id in self._amounts:
            return self._amounts[product_id]
        items = shopping_list.items if shopping_list else []
        return next((i.amount for i in items if i.id == product_id), 0)

    async def async_set_amount(self, product_id: int, amount: int, *, verify: bool = True) -> None:
        """Set an absolute quantity; verify uncertain responses instead of adding again.

        Without ``verify`` the cart is read once afterwards for all the changes
        (``async_confirm``), instead of once for each.
        """
        async with self._change:
            await self.async_select_location(force=False)
            # A timed-out write may have succeeded; the check after it tells.
            with suppress(RemaConnectionError):
                await self._shop(
                    "ChangeLineCount",
                    params={
                        "productId": product_id,
                        "count": amount,
                        "fullCart": 0,
                    },
                )
            if not verify:
                self._amounts[product_id] = amount
                return
            if (await self.async_confirm({product_id: amount})) != {product_id}:
                raise BilkaError("BilkaToGo bekræftede ikke antallet. Prøv igen")

    async def async_confirm(self, targets: dict[int, int]) -> set[int]:
        """The products whose quantity in the cart is now the wanted one (one read)."""
        if not targets:
            return set()
        shopping = await self.async_list()
        actual = {item.id: item.amount for item in shopping.items}
        return {pid for pid, amount in targets.items() if actual.get(pid, 0) == amount}

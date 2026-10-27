"""Another shop than REMA 1000: its avis from Tjek, and the family's own shopping list.

With REMA 1000 the app logs in to the family's REMA account: its products and
prices, its recipes and the list in the REMA app. Another shop (Netto, føtex,
Lidl ...) has none of that online, so it takes no login: the week's avis comes
from Tjek (as REMA's does), every item is free text priced only when it is on
offer, and the shopping list is kept here in Home Assistant.

``StoreClient`` answers the same calls as ``RemaClient``, so the rest of the app
works the same; what needs REMA simply finds nothing.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from homeassistant.helpers.storage import Store

from .api import Catalog, Offer, Product, RemaClient, ShoppingList, ShoppingListItem
from .bilka import BILKA_ID, BilkaSearch
from .bilka_cart import BilkaCart, BilkaError
from .chains import CHAINS, is_food_catalog
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

REMA = "rema"
CONF_STORE = "store"
LIST_ID = 1
LIST_NAME = "Indkøbsliste"
MAX_ITEMS = 500

# The shops to choose between: REMA 1000 first, then the chains on Tjek.
STORES: dict[str, str] = {REMA: "REMA 1000", **CHAINS}

# What only works with REMA 1000 (shown when another shop is chosen).
REMA_ONLY = (
    "Priser på alle varer (kun tilbudsvarer har en pris)",
    "Indkøbslisten i REMA-appen (listen er i Home Assistant)",
    "REMA's opskrifter",
    "Valg af præcis vare til en ingrediens",
    "Næringsindhold",
    "REMA-favoritter og købte varer",
    "Sammenligning med andre butikkers tilbud",
    "Budgettets prognose (beløb bogføres selv)",
)


# What Bilka has online too: its prices on every item (Bilka ToGo).
_WITH_PRICES = {
    "Priser på alle varer (kun tilbudsvarer har en pris)",
    "Valg af præcis vare til en ingrediens",
    "Budgettets prognose (beløb bogføres selv)",
}


def rema_only(store: str) -> list[str]:
    """What doesn't work with a shop (only with REMA 1000)."""
    if store == REMA:
        return []
    if store == BILKA_ID:
        return [line for line in REMA_ONLY if line not in _WITH_PRICES]
    return list(REMA_ONLY)


def store_of(data: Any) -> str:
    """The shop an entry is for (entries from before the choice are REMA 1000)."""
    store = str((data or {}).get(CONF_STORE) or REMA)
    return store if store in STORES else REMA


def genitive(name: str) -> str:
    """ "Nettos", but "føtex'" (and REMA 1000's, as REMA writes it)."""
    if name == "REMA 1000":
        return "REMA 1000's"
    return f"{name}'" if name[-1:].lower() in "sxz" else f"{name}s"


def store_name(store: str) -> str:
    """REMA 1000, Netto, føtex ..."""
    return STORES.get(store, store)


class StoreClient(RemaClient):
    """A shop without login: its avis from Tjek, and a shopping list kept here."""

    def __init__(
        self, hass: HomeAssistant, session: aiohttp.ClientSession, entry_id: str, dealer_id: str
    ) -> None:
        """Initialize for a shop (its Tjek dealer id)."""
        super().__init__(session, "", "")
        self.dealer_id = dealer_id
        self._list: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry_id}.list")
        self._items: list[dict[str, Any]] | None = None
        self._next_id = 1

    @property
    def has_prices(self) -> bool:
        """Only offers have a price."""
        return False

    async def async_login(self) -> int:
        """Nothing to log in to; the list is read."""
        await self._async_items()
        return 0

    # ------------------------------------------------------------ the list

    async def _async_items(self) -> list[dict[str, Any]]:
        if self._items is None:
            stored = await self._list.async_load() or {}
            self._items = [
                item
                for item in stored.get("items") or []
                if isinstance(item, dict) and isinstance(item.get("id"), int) and item.get("name")
            ]
            self._next_id = max(
                [int(stored.get("next_id") or 1), *(i["id"] + 1 for i in self._items)]
            )
        return self._items

    async def _async_save(self) -> None:
        await self._list.async_save({"items": self._items or [], "next_id": self._next_id})

    async def async_get_lists(self) -> list[dict[str, Any]]:
        """The one list."""
        return [{"id": LIST_ID, "name": LIST_NAME, "is_primary": True}]

    async def async_get_primary_list_id(self, force: bool = False) -> int:
        """The one list."""
        return LIST_ID

    async def async_get_list(self, list_id: int) -> ShoppingList:
        """The list with its items."""
        return ShoppingList(
            id=LIST_ID,
            name=LIST_NAME,
            items=[
                ShoppingListItem(
                    id=item["id"],
                    name=str(item["name"]),
                    bought=bool(item.get("bought")),
                    amount=int(item.get("amount") or 1),
                    product_id=None,
                )
                for item in await self._async_items()
            ],
        )

    async def async_create_item(
        self,
        list_id: int,
        *,
        amount: int = 1,
        product_id: int | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Add a line (always free text: there are no products)."""
        text = str(name or "").strip()[:200]
        if not text:
            raise ValueError("name is required")
        items = await self._async_items()
        item = {"id": self._next_id, "name": text, "amount": max(1, int(amount)), "bought": False}
        self._next_id += 1
        items.append(item)
        del items[:-MAX_ITEMS]
        await self._async_save()
        return dict(item)

    async def async_update_item(self, list_id: int, item_id: int, **changes: Any) -> dict[str, Any]:
        """Change amount, bought state or name of a line."""
        items = await self._async_items()
        item = next((i for i in items if i["id"] == item_id), None)
        if item is None:
            return {}
        if "amount" in changes:
            item["amount"] = max(1, int(changes["amount"] or 1))
        if "bought" in changes:
            item["bought"] = bool(changes["bought"])
        if str(changes.get("name") or "").strip():
            item["name"] = str(changes["name"]).strip()[:200]
        await self._async_save()
        return dict(item)

    async def async_delete_items(self, list_id: int, item_ids: list[int]) -> None:
        """Remove lines."""
        if not item_ids:
            return
        gone = set(item_ids)
        items = await self._async_items()
        items[:] = [i for i in items if i["id"] not in gone]
        await self._async_save()

    # ------------------------------------------------------------ the shop's avis

    async def async_get_catalogs(self) -> list[Catalog]:
        """The shop's food aviser (not its toy or electronics catalogues)."""
        return [c for c in await super().async_get_catalogs() if is_food_catalog(c.label)]

    async def async_get_offer_products(self, offers: list[Offer]) -> list[Offer]:
        """No products online: an offer is bought as the avis has it."""
        return [replace(o, product_ids=(), product_names=(), unlinked=False) for o in offers]

    # ------------------------------------------------------------ only at REMA

    async def async_search_products_at(
        self, query: str, limit: int, times: list[datetime]
    ) -> list[list[Product]]:
        """No products online."""
        return [[] for _ in times]

    async def async_get_products(
        self, product_ids: list[int], at: datetime | None = None
    ) -> list[Product]:
        """No products online."""
        return []

    async def async_get_favorites(self, force: bool = False) -> list[Product]:
        """No favourites in an app."""
        return []

    async def async_get_nutrition(self, product_ids: list[int]) -> dict[int, dict[str, float]]:
        """No nutrition tables."""
        return {}

    async def async_get_recipes(self, **kwargs: Any) -> dict[str, Any]:
        """REMA's recipes need a REMA account."""
        return {}

    async def async_get_recipe(self, slug: str) -> dict[str, Any] | None:
        """REMA's recipes need a REMA account."""
        return None


class BilkaStoreClient(StoreClient):
    """Bilka: its avis from Tjek, and every item priced from Bilka ToGo's webshop."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        entry_id: str,
        email: str = "",
        password: str = "",
        pickup: str = "",
    ) -> None:
        """Initialize."""
        super().__init__(hass, session, entry_id, BILKA_ID)
        self.bilka = BilkaSearch(hass)
        self.cart = BilkaCart(session, self.bilka, email, password, pickup) if email else None
        self._transfers: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry_id}.bilka_transfers"
        )
        self._receipts: dict[str, Any] | None = None
        self._transfer_lock = asyncio.Lock()

    async def async_login(self) -> int:
        """Old Bilka entries remain local until login is added in Reconfigure."""
        if self.cart is None:
            return await super().async_login()
        uid = await self.cart.async_login()
        await self.cart.async_select_location()
        return uid

    async def async_get_list(self, list_id: int) -> ShoppingList:
        """Read the remote cart when this entry has a BilkaToGo login."""
        return await self.cart.async_list() if self.cart else await super().async_get_list(list_id)

    async def async_create_item(
        self,
        list_id: int,
        *,
        amount: int = 1,
        product_id: int | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """A remote cart accepts concrete products only."""
        if self.cart is None:
            return await super().async_create_item(
                list_id, amount=amount, product_id=product_id, name=name
            )
        if not product_id:
            raise BilkaError("Vælg en BilkaToGo-vare til ingrediensen, før den sendes")
        await self.cart.async_set_amount(product_id, max(1, amount))
        return {"id": product_id}

    async def async_update_item(self, list_id: int, item_id: int, **changes: Any) -> dict[str, Any]:
        """Cart products can change quantity, but cannot be ticked off as bought."""
        if self.cart is None:
            return await super().async_update_item(list_id, item_id, **changes)
        if changes.get("bought"):
            raise BilkaError("BilkaToGo-kurven kan ikke afkrydses. Gennemfør købet i BilkaToGo")
        if "amount" in changes:
            await self.cart.async_set_amount(item_id, max(1, int(changes["amount"])))
        return {"id": item_id}

    async def async_delete_items(self, list_id: int, item_ids: list[int]) -> None:
        """Remove only groceries, never the cart's packing services."""
        if self.cart is None:
            await super().async_delete_items(list_id, item_ids)
            return
        for item_id in item_ids:
            await self.cart.async_set_amount(item_id, 0)

    async def async_add_once(
        self,
        shopping_list: ShoppingList,
        *,
        operation_id: str,
        amount: int,
        product_id: int | None = None,
        name: str | None = None,
    ) -> None:
        """Persist the target before writing; a repeated plan send reuses it."""
        if self.cart is None:
            await self.async_add_to_list(
                shopping_list, amount=amount, product_id=product_id, name=name
            )
            return
        if not product_id:
            raise BilkaError("Vælg en BilkaToGo-vare til ingrediensen, før den sendes")
        async with self._transfer_lock:
            if self._receipts is None:
                self._receipts = await self._transfers.async_load() or {}
            receipt = self._receipts.get(operation_id)
            if receipt and receipt.get("done"):
                return
            if receipt is None:
                current = await self.cart.async_list()
                existing = next((i.amount for i in current.items if i.id == product_id), 0)
                receipt = {
                    "product_id": product_id,
                    "target": existing + max(1, amount),
                    "done": False,
                }
                self._receipts[operation_id] = receipt
                await self._transfers.async_save(self._receipts)
            elif receipt.get("product_id") != product_id:
                raise BilkaError(
                    "Et tidligere forsøg gælder en anden vare; genskab kurven før nyt forsøg"
                )
            await self.cart.async_set_amount(product_id, int(receipt["target"]))
            receipt["done"] = True
            await self._transfers.async_save(self._receipts)

    @property
    def has_prices(self) -> bool:
        """Every item has Bilka ToGo's price."""
        return True

    async def async_search_products_at(
        self, query: str, limit: int, times: list[datetime]
    ) -> list[list[Product]]:
        """Bilka ToGo's products, at today's prices (the webshop shows no later ones)."""
        products = await self.bilka.async_search(query, limit)
        return [list(products) for _ in times]

    async def async_get_products(
        self, product_ids: list[int], at: datetime | None = None
    ) -> list[Product]:
        """Products found before."""
        return self.bilka.known(product_ids)

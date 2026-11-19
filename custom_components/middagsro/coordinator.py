"""Data update coordinators for REMA 1000."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    Catalog,
    Receipt,
    RemaAuthError,
    RemaClient,
    RemaError,
    ShoppingList,
    is_week_avis,
    parse_time,
)
from .bilka import BilkaError
from .const import (
    DOMAIN,
    LIST_SCAN_INTERVAL,
    OFFERS_SCAN_INTERVAL,
    RECEIPTS_SCAN_INTERVAL,
    STORAGE_VERSION,
)
from .receipts import aggregate_items, spending_overview
from .store_client import BilkaStoreClient

if TYPE_CHECKING:
    from .favorites import FavoriteOffers
    from .mealplan import MealPlanner
    from .storage import RemaPlanStore

_LOGGER = logging.getLogger(__name__)


@dataclass
class RemaRuntimeData:
    """Objects kept for a config entry while it is loaded."""

    client: RemaClient
    shopping_list: RemaShoppingListCoordinator
    offers: RemaOffersCoordinator
    store: RemaPlanStore
    planner: MealPlanner
    favorite_offers: FavoriteOffers
    receipts: RemaReceiptsCoordinator | None = None


type RemaConfigEntry = ConfigEntry[RemaRuntimeData]


class RemaShoppingListCoordinator(DataUpdateCoordinator[ShoppingList]):
    """Keep the primary shopping list in sync."""

    config_entry: RemaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RemaConfigEntry, client: RemaClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} shopping list",
            update_interval=LIST_SCAN_INTERVAL,
        )
        self.client = client
        # One change to the list at a time: a send and a quick add must not
        # both read the list, then write their own idea of it.
        self._change = asyncio.Lock()
        # Also put added items on another to-do list (another shop than REMA 1000).
        self.mirror: Callable[[list[dict[str, Any]]], Awaitable[None]] | None = None

    async def _async_update_data(self) -> ShoppingList:
        """Fetch the primary list. It is looked up every time so a change of
        primary list in the app is followed automatically."""
        try:
            return await self.client.async_get_primary_list()
        except RemaAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"email": self.config_entry.data[CONF_EMAIL]},
            ) from err
        except RemaError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_add_items(
        self,
        items: list[dict[str, Any]],
        on_added: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Add items ({product_id|name, amount}) to the primary list.

        ``on_added`` is told about each item as soon as it is on the list, so a
        caller knows what got there if a later item fails.
        """
        added: list[dict[str, Any]] = []
        cart = isinstance(self.client, BilkaStoreClient) and self.client.cart is not None
        async with self._change:
            if cart and any(not item.get("product_id") for item in items):
                raise BilkaError(
                    f"Vælg en {getattr(self.client, 'cart_label', 'BilkaToGo')}-vare til alle "
                    "ingredienser, før listen sendes"
                )
            shopping_list = await self.client.async_get_primary_list()
            # BilkaToGo: written one by one, confirmed together with one read of the cart.
            pending: list[dict[str, Any]] = []
            try:
                for item in items:
                    if isinstance(self.client, BilkaStoreClient) and item.get("transfer_id"):
                        await self.client.async_add_once(
                            shopping_list,
                            operation_id=str(item["transfer_id"]),
                            amount=int(item.get("amount") or 1),
                            product_id=item.get("product_id"),
                            name=item.get("name"),
                        )
                        if cart:
                            pending.append(item)
                            continue
                    else:
                        await self.client.async_add_to_list(
                            shopping_list,
                            amount=int(item.get("amount") or 1),
                            product_id=item.get("product_id"),
                            name=item.get("name"),
                        )
                    added.append(item)
                    if on_added is not None:
                        on_added(item)
            finally:
                try:
                    if pending and isinstance(self.client, BilkaStoreClient):
                        done = await self.client.async_confirm_transfers()
                        for item in pending:
                            if str(item["transfer_id"]) in done:
                                added.append(item)
                                if on_added is not None:
                                    on_added(item)
                finally:
                    # Refresh right away (not debounced) so HA shows the change at once.
                    await self.async_refresh()
                    if self.mirror is not None and added:
                        await self.mirror(added)
            if len(added) < len(items):
                label = getattr(self.client, "cart_label", "Butikken")
                raise BilkaError(
                    f"{label} bekræftede ikke alle varer i kurven. Send listen igen for resten"
                )

    async def async_take_items(self, items: list[dict[str, Any]]) -> int:
        """Take items ({product_id|name, amount}) off the primary list again: the
        amount is lowered, and a line that gets to nothing is removed. A line that
        is bought already is left as it is. Returns how many lines were changed."""
        changed = 0
        async with self._change:
            shopping_list = await self.client.async_get_primary_list()
            gone: list[int] = []
            for item in items:
                found = shopping_list.find(product_id=item.get("product_id"), name=item.get("name"))
                if found is None or found.bought or found.id in gone:
                    continue
                left = found.amount - int(item.get("amount") or 1)
                if left > 0:
                    await self.client.async_update_item(shopping_list.id, found.id, amount=left)
                    found.amount = left
                else:
                    gone.append(found.id)
                changed += 1
            if gone:
                await self.client.async_delete_items(shopping_list.id, gone)
            if changed:
                await self.async_refresh()
        return changed

    async def async_clear(self, bought_only: bool = False) -> int:
        """Remove the items from the primary list (only the bought ones). Returns how many."""
        async with self._change:
            shopping_list = await self.client.async_get_primary_list()
            ids = [item.id for item in shopping_list.items if item.bought or not bought_only]
            if not ids:
                return 0
            await self.client.async_delete_items(shopping_list.id, ids)
            await self.async_refresh()
            return len(ids)


@dataclass
class OffersData:
    """Tilbudsaviser for REMA 1000."""

    current: Catalog | None = None
    upcoming: Catalog | None = None
    catalogs: list[Catalog] = field(default_factory=list)
    first_seen: dict[str, str] = field(default_factory=dict)


class RemaOffersCoordinator(DataUpdateCoordinator[OffersData]):
    """Track the current and next tilbudsavis.

    The first time a catalogue is seen is stored, so we learn when REMA
    publishes next week's avis.
    """

    config_entry: RemaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RemaConfigEntry, client: RemaClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} offers",
            update_interval=OFFERS_SCAN_INTERVAL,
        )
        self.client = client
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.catalogs"
        )
        self._first_seen: dict[str, str] | None = None

    async def _async_update_data(self) -> OffersData:
        """Fetch catalogues from Tjek."""
        if self._first_seen is None:
            try:
                stored = await self._store.async_load() or {}
            except HomeAssistantError as err:  # a damaged file: start over
                _LOGGER.warning("Could not read when the aviser were first seen: %s", err)
                stored = {}
            self._first_seen = dict(stored.get("first_seen") or {})
        try:
            catalogs = await self.client.async_get_catalogs()
        except RemaError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        now = datetime.now(UTC)
        changed = False
        for catalog in catalogs:
            if catalog.id not in self._first_seen:
                self._first_seen[catalog.id] = now.isoformat()
                changed = True
                _LOGGER.info(
                    "Ny REMA 1000 tilbudsavis fundet: %s (gyldig %s - %s)",
                    catalog.label,
                    catalog.valid_from,
                    catalog.valid_to,
                )
        # Aviser from months ago are gone for good: forget when they were first seen.
        old = [
            key
            for key, seen in self._first_seen.items()
            if (now - (parse_time(seen) or now)).days > 90
        ]
        for key in old:
            del self._first_seen[key]
        if changed or old:
            await self._store.async_save({"first_seen": self._first_seen})

        # An insert (indstik) is part of its week's avis, whose offers it
        # repeats, and a weeks-long avis without offers ("Meget Mere") is no
        # week's avis either: neither is the week's avis itself, nor next week's.
        weekly = [c for c in catalogs if is_week_avis(c, catalogs)]
        running = [
            c for c in weekly if c.valid_from and c.valid_to and c.valid_from <= now <= c.valid_to
        ]
        future = sorted(
            (c for c in weekly if c.valid_from and c.valid_from > now),
            key=lambda c: c.valid_from or now,
        )
        current = max(running, key=lambda c: c.offer_count or 0) if running else None
        return OffersData(
            current=current,
            upcoming=future[0] if future else None,
            catalogs=catalogs,
            first_seen=dict(self._first_seen),
        )


class RemaReceiptsCoordinator(DataUpdateCoordinator[list[Receipt]]):
    """Keep the account's digital receipts (kvitteringer) in sync.

    Only for REMA 1000 accounts. Receipts come from the Scan Selv backend, a
    different host than the webshop API; if it refuses the token or is down the
    coordinator fails soft so the rest of the integration keeps working.

    The whole history is kept (persisted to disk) so the item statistics and
    the budget booking have every purchase, not just the newest. Each poll only
    asks for receipts since the newest one it already has, with a little
    overlap, so the fetch stays small.
    """

    config_entry: RemaConfigEntry

    # The history is bounded so a very old account cannot grow without limit.
    MAX_KEEP = 2000
    # The account's own login plus up to this many extra receipt-only logins.
    MAX_EXTRA_LOGINS = 4
    PRIMARY = "primary"

    def __init__(self, hass: HomeAssistant, entry: RemaConfigEntry, client: RemaClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} receipts",
            update_interval=RECEIPTS_SCAN_INTERVAL,
        )
        self.client = client
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.receipts"
        )
        # Extra receipt-only logins (other household REMA accounts) are kept apart.
        self._logins_store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.receipt_logins"
        )
        self._logins: list[dict[str, str]] = []
        self._extra_clients: dict[str, RemaClient] = {}
        self._loaded = False
        self._cache: list[Receipt] = []
        # Which login each receipt came from (receipt id -> "primary" or a login id),
        # and which logins a full history has already been pulled for.
        self._sources: dict[str, str] = {}
        self._known: set[str] = set()
        # Per-item statistics across the whole history (the "Varer" tab).
        self.items: list[dict[str, Any]] = []
        # Spend grouped by week/month/year for the economy overview.
        self.overview: dict[str, Any] = {}

    # ---------------------------------------------------- extra receipt logins

    async def async_load_logins(self) -> None:
        """Read the stored extra receipt logins and build their clients."""
        try:
            raw = await self._logins_store.async_load() or {}
        except HomeAssistantError as err:
            _LOGGER.warning("Could not read the extra receipt logins: %s", err)
            raw = {}
        self._logins = [
            {
                "id": str(lg.get("id") or uuid.uuid4().hex[:8]),
                "email": str(lg["email"]),
                "password": str(lg.get("password") or ""),
                "label": str(lg.get("label") or lg["email"]),
            }
            for lg in raw.get("logins") or []
            if isinstance(lg, dict) and lg.get("email")
        ]
        self._rebuild_clients()

    def _rebuild_clients(self) -> None:
        """Make a fresh client (own session) for each extra login."""
        self._extra_clients = {
            lg["id"]: RemaClient(async_create_clientsession(self.hass), lg["email"], lg["password"])
            for lg in self._logins
        }

    def logins_public(self) -> list[dict[str, Any]]:
        """The extra logins for the panel (without passwords), with receipt counts."""
        counts = Counter(self._sources.values())
        return [
            {
                "id": lg["id"],
                "email": lg["email"],
                "label": lg["label"],
                "count": counts.get(lg["id"], 0),
            }
            for lg in self._logins
        ]

    async def async_add_login(self, email: str, password: str, label: str) -> dict[str, Any]:
        """Add an extra REMA login used only for its receipts. Validates the sign-in."""
        email = email.strip()
        if not email or not password:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="receipt_login_missing"
            )
        if any(lg["email"].lower() == email.lower() for lg in self._logins):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="receipt_login_exists"
            )
        if len(self._logins) >= self.MAX_EXTRA_LOGINS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="receipt_login_too_many",
                translation_placeholders={"max": str(self.MAX_EXTRA_LOGINS)},
            )
        client = RemaClient(async_create_clientsession(self.hass), email, password)
        try:
            await client.async_get_receipts(limit=1)
        except RemaAuthError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="receipt_login_auth",
                translation_placeholders={"email": email},
            ) from err
        except RemaError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="receipt_login_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        login = {
            "id": uuid.uuid4().hex[:8],
            "email": email,
            "password": password,
            "label": label.strip() or email,
        }
        self._logins.append(login)
        self._extra_clients[login["id"]] = client
        await self._logins_store.async_save({"logins": self._logins})
        await self.async_request_refresh()
        return {"id": login["id"], "email": email, "label": login["label"]}

    async def async_remove_login(self, login_id: str) -> list[str]:
        """Remove an extra login and its receipts. Returns the dropped receipt ids."""
        before = len(self._logins)
        self._logins = [lg for lg in self._logins if lg["id"] != login_id]
        if len(self._logins) == before:
            return []
        self._extra_clients.pop(login_id, None)
        self._known.discard(login_id)
        await self._logins_store.async_save({"logins": self._logins})
        removed = [rid for rid, src in self._sources.items() if src == login_id]
        if removed:
            gone = set(removed)
            self._cache = [r for r in self._cache if r.id not in gone]
            for rid in removed:
                self._sources.pop(rid, None)
            await self._persist()
            self._recompute(self._cache)
            self.async_set_updated_data(self._cache)
        return removed

    # ------------------------------------------------------------- fetch cycle

    def _sources_and_clients(self) -> list[tuple[str, RemaClient]]:
        """The primary account and each extra login, with its client."""
        extra = [(lg["id"], self._extra_clients[lg["id"]]) for lg in self._logins]
        return [(self.PRIMARY, self.client), *extra]

    def _since_for(self, source: str) -> datetime | None:
        """Fetch only receipts newer than this source's newest known one."""
        newest = max(
            (r.date for r in self._cache if self._sources.get(r.id) == source and r.date),
            default=None,
        )
        return newest - timedelta(days=2) if newest else None

    async def _load_stored(self) -> None:
        """Read the persisted receipts and their source map."""
        try:
            raw = await self._store.async_load() or {}
        except HomeAssistantError as err:  # a damaged file: start over
            _LOGGER.warning("Could not read the stored receipts: %s", err)
            raw = {}
        out: list[Receipt] = []
        for stored in raw.get("receipts") or []:
            try:
                out.append(Receipt.from_dict(stored))
            except (TypeError, ValueError):
                continue
        self._cache = out
        self._sources = {
            str(k): str(v) for k, v in (raw.get("sources") or {}).items() if isinstance(v, str)
        }
        for receipt in out:  # receipts from before the source map default to the primary
            self._sources.setdefault(receipt.id, self.PRIMARY)
        self._known = {str(s) for s in raw.get("known") or []}
        if out and self.PRIMARY not in self._known:
            self._known.add(self.PRIMARY)

    async def _persist(self) -> None:
        """Save the receipts, their source map and which logins are fully fetched."""
        try:
            await self._store.async_save(
                {
                    "receipts": [r.as_dict() for r in self._cache],
                    "sources": self._sources,
                    "known": sorted(self._known),
                }
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Could not save the receipts: %s", err)

    def _recompute(self, receipts: list[Receipt]) -> None:
        """Refresh the per-item statistics and the spend overview."""
        self.items = aggregate_items(receipts)
        self.overview = spending_overview(
            receipts, dt_util.get_default_time_zone(), dt_util.now().date()
        )

    def _merge_tagged(self, fresh: list[tuple[str, Receipt]]) -> list[Receipt]:
        """Merge freshly fetched receipts into the cache, tagging each by source."""
        by_id: dict[str, Receipt] = {r.id: r for r in self._cache}
        for source, receipt in fresh:
            by_id[receipt.id] = receipt
            self._sources[receipt.id] = source
        merged = sorted(
            by_id.values(),
            key=lambda r: r.date or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )[: self.MAX_KEEP]
        kept = {r.id for r in merged}
        self._sources = {rid: src for rid, src in self._sources.items() if rid in kept}
        return merged

    async def _async_update_data(self) -> list[Receipt]:
        """Fetch receipts from the primary account and each extra login, merge, persist."""
        if not self._loaded:
            await self._load_stored()
            self._loaded = True
        stored = self._cache
        fresh: list[tuple[str, Receipt]] = []
        primary_failed = False
        for source, client in self._sources_and_clients():
            since = self._since_for(source) if source in self._known else None
            try:
                got = await client.async_get_receipts(since=since)
            except RemaAuthError as err:
                if source == self.PRIMARY:
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="auth_failed",
                        translation_placeholders={"email": self.config_entry.data[CONF_EMAIL]},
                    ) from err
                _LOGGER.warning("Extra receipt login %s could not sign in", source)
                continue
            except RemaError as err:
                if source == self.PRIMARY:
                    primary_failed = True
                _LOGGER.debug("Receipts fetch failed for %s: %s", source, err)
                continue
            self._known.add(source)
            fresh += [(source, receipt) for receipt in got]
        if primary_failed and not stored:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": "scan backend"},
            )
        merged = self._merge_tagged(fresh)
        if merged != stored or fresh:
            self._cache = merged
            await self._persist()
        self._recompute(merged)
        return merged

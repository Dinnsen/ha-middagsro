"""REMA 1000's recipes, kept in Home Assistant: every dinner recipe with its products.

REMA links every ingredient of its recipes to one of its products. The catalogue
reads all of REMA's dinner recipes, a page a minute so REMA is never pressed,
and keeps them on this Home Assistant (nothing of REMA's is copied anywhere
else). It is read again once a week, so the products are REMA's current ones.

A recipe is *ready* when every ingredient that is bought has a product: then a
plan can use it without anyone checking its items.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import RemaError, parse_time
from .const import DOMAIN
from .rema_recipes import (
    VEGETARIAN_TAG,
    _ingredients,
    _product,
    _tags,
    current_price,
    image_url,
    to_recipe,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from .api import RemaClient

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
# The categories read: together they hold REMA's dinners (a recipe in several is
# read once). Aftensmad first, in REMA's order of popularity.
SWEEP_TAGS = (
    "6mjo9YHow8fdXyG4LhmHoK",  # Aftensmad
    "13gnXZJQl6zEqH0Qnse3W5",  # Nem hverdagsmad
    "lw0hPueEJErVe4xopoDEy",  # Mad for børn
    "2rdeKY4498Ma5tPsizr0Er",  # Kødfri
    "7yfezsL41ufC4kYdHXjN8d",  # Fisk & skaldyr
)
PER_PAGE = 20
MAX_PAGES = 60  # per category: REMA has about 19 pages of dinners
PAGE_PAUSE = 60.0  # seconds between two pages
SWEEP_EVERY = timedelta(days=7)
CHECK_EVERY = timedelta(hours=12)
FIRST_CHECK = 300  # seconds after start, so Home Assistant is up first


def entry_from(entity: dict[str, Any], rank: int, now: datetime) -> dict[str, Any] | None:
    """What the catalogue keeps of one of REMA's recipes."""
    fields = entity.get("fields") or {}
    slug, title = fields.get("slug"), str(fields.get("title") or "").strip()
    if not slug or not title:
        return None
    form = fields.get("customForm") or {}
    prices: dict[str, list[dict[str, Any]]] = {}
    ready = True
    for item in _ingredients(entity):
        digital, active = _product(item)
        if item.get("isExcludedFromShoppingList") or digital.get("is_basic_ingredient"):
            continue
        if not active.get("id"):
            ready = False
            continue
        prices[str(active["id"])] = [
            {k: p.get(k) for k in ("price", "is_advertised", "starting_at", "ending_at")}
            for p in active.get("prices") or []
            if isinstance(p, dict)
        ]
    recipe = to_recipe(entity)
    recipe.pop("id", None)
    tags = _tags(entity)
    return {
        "slug": str(slug),
        "title": title[:300],
        "image": image_url(fields.get("image"), 480),
        "servings": int((form.get("servings") or {}).get("amount") or 0) or None,
        "total_minutes": int(form.get("totalTime") or 0) or None,
        "tags": [str((t.get("fields") or {}).get("title") or "") for t in tags][:6],
        "tag_ids": [str(t.get("id")) for t in tags if t.get("id")],
        "vegetarian": any(t.get("id") == VEGETARIAN_TAG for t in tags),
        "rank": rank,
        "ready": ready and bool(recipe["ingredients"]),
        "recipe": recipe,
        "prices": prices,
        "seen": now.isoformat(),
    }


def card(entry: dict[str, Any], now: datetime) -> dict[str, Any]:
    """A recipe card, priced now (as rema_recipes.summary has it)."""
    on_offer = 0
    cost = 0.0
    for prices in entry.get("prices", {}).values():
        price, offer = current_price({"prices": prices}, now)
        on_offer += offer
        cost += price or 0
    return {
        "slug": entry["slug"],
        "title": entry["title"],
        "image": entry.get("image"),
        "servings": entry.get("servings"),
        "total_minutes": entry.get("total_minutes"),
        "tags": entry.get("tags", []),
        "vegetarian": bool(entry.get("vegetarian")),
        "ingredients": len(entry["recipe"].get("ingredients") or []),
        "on_offer": on_offer,
        "cost": round(cost, 2),
        "ready": bool(entry.get("ready")),
    }


def _words(entry: dict[str, Any]) -> str:
    names = " ".join(str(i.get("name") or "") for i in entry["recipe"].get("ingredients") or [])
    return f"{entry['title']} {names}".lower()


class RemaRecipeCatalog:
    """All of REMA's dinner recipes, read slowly and kept here."""

    def __init__(self, hass: HomeAssistant, entry_id: str, client: RemaClient) -> None:
        """Initialize."""
        self.hass = hass
        self.client = client
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry_id}.rema_recipes"
        )
        self.recipes: dict[str, dict[str, Any]] = {}
        self.swept: str | None = None  # when the last whole read finished (ISO)
        self.running = False
        self.pages = 0  # pages read in the running sweep
        self._task: asyncio.Task[None] | None = None
        self._unsubs: list[Callable[[], None]] = []
        self.pause = PAGE_PAUSE

    async def async_load(self) -> None:
        """Load what was read before."""
        data = await self._store.async_load() or {}
        self.recipes = {
            str(slug): entry
            for slug, entry in (data.get("recipes") or {}).items()
            if isinstance(entry, dict) and isinstance(entry.get("recipe"), dict)
        }
        self.swept = data.get("swept") if isinstance(data.get("swept"), str) else None

    async def _async_save(self) -> None:
        await self._store.async_save({"recipes": self.recipes, "swept": self.swept})

    @property
    def complete(self) -> bool:
        """Has every recipe been read at least once?"""
        return self.swept is not None and bool(self.recipes)

    def status(self) -> dict[str, Any]:
        """For the panel: how many, how many ready, and when."""
        return {
            "count": len(self.recipes),
            "ready": sum(1 for e in self.recipes.values() if e.get("ready")),
            "swept": self.swept,
            "running": self.running,
            "pages": self.pages,
        }

    def due(self, now: datetime | None = None) -> bool:
        """Is it time to read REMA's recipes again?"""
        last = parse_time(self.swept) if self.swept else None
        return last is None or (now or dt_util.utcnow()) - last >= SWEEP_EVERY

    @callback
    def async_start(self) -> None:
        """Read the recipes now and then, when a REMA account is there to read them."""
        if not getattr(self.client, "has_prices", False):
            return  # another shop: REMA's recipes need a REMA account

        @callback
        def check(_now: Any = None) -> None:
            if self.due() and not self.running:
                self._task = self.hass.async_create_background_task(
                    self.async_sweep(), f"{DOMAIN} REMA recipes"
                )

        self._unsubs.append(async_call_later(self.hass, FIRST_CHECK, check))
        self._unsubs.append(async_track_time_interval(self.hass, check, CHECK_EVERY))

    @callback
    def async_stop(self) -> None:
        """Stop reading (on unload)."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._task and not self._task.done():
            self._task.cancel()

    async def async_sweep(self) -> None:
        """Read every dinner recipe, a page at a time with a pause between pages."""
        self.running, self.pages = True, 0
        seen: dict[str, dict[str, Any]] = {}
        try:
            for tag in SWEEP_TAGS:
                page, last = 1, 1
                while page <= min(last, MAX_PAGES):
                    if self.pages:
                        await asyncio.sleep(self.pause)
                    data = await self.client.async_get_recipes(
                        tag=tag, page=page, per_page=PER_PAGE, sort="-popularity"
                    )
                    self.pages += 1
                    now = dt_util.utcnow()
                    for entity in data.get("data") or []:
                        if not isinstance(entity, dict):
                            continue
                        entry = entry_from(entity, len(seen), now)
                        if entry is not None and entry["slug"] not in seen:
                            seen[entry["slug"]] = entry
                    pagination = (data.get("meta") or {}).get("pagination") or {}
                    last = int(pagination.get("last_page") or page)
                    page += 1
        except RemaError as err:
            _LOGGER.info("REMA's recipes could not be read (tried again later): %s", err)
            return
        finally:
            self.running = False
        if not seen:
            return
        # A recipe REMA took down is gone here too.
        self.recipes = seen
        self.swept = dt_util.utcnow().isoformat()
        await self._async_save()
        _LOGGER.info("Read %d of REMA's recipes (%d ready)", len(seen), self.status()["ready"])

    def page(
        self, tag: str | None, page: int, query: str | None, per_page: int = PER_PAGE
    ) -> dict[str, Any] | None:
        """A page of cards from the catalogue, as REMA's API would give it; None
        when the catalogue can't answer it (not read yet, a category it skips)."""
        if not self.complete or (tag and tag not in SWEEP_TAGS):
            return None
        entries = sorted(self.recipes.values(), key=lambda e: e.get("rank", 0))
        if tag:
            entries = [e for e in entries if tag in e.get("tag_ids", [])]
        if query:
            words = query.lower().split()
            entries = [e for e in entries if all(w in _words(e) for w in words)]
        total = len(entries)
        last = max(1, -(-total // per_page))
        now = dt_util.utcnow()
        chunk = entries[(page - 1) * per_page : page * per_page]
        return {
            "recipes": [card(e, now) for e in chunk],
            "page": page,
            "last_page": last,
            "total": total,
        }

    def recipe(self, slug: str) -> dict[str, Any] | None:
        """One recipe in the collection's shape (not saved), if the catalogue has it."""
        entry = self.recipes.get(slug)
        if entry is None:
            return None
        recipe = copy.deepcopy(entry["recipe"])
        recipe["id"] = None
        return recipe

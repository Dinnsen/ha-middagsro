"""Recipes from the Danish recipe sites the family chooses (Valdemarsro, Madens Verden ...).

The sites are searched by their sitemaps: every recipe's address, whose last part
is its name ("kylling-i-cremet-parmesan-og-hvidloegssauce"). A search matches the
words of that name, so nothing but the sitemaps is read until a recipe is opened -
then its page is read like a link the family pasted (the recipe data most sites
have). The sitemaps are kept for a day. Each site's robots.txt is respected.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import logging
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiohttp

from .recipes import HEADERS, async_fetch_page, clean_recipe, page_session, parse_recipe_page

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CACHE_SECONDS = 24 * 3600
SITEMAP_LIMIT = 15_000_000  # bytes of one sitemap file
MAX_SITEMAPS = 40  # files of one site
MAX_RESULTS = 40
TIMEOUT = aiohttp.ClientTimeout(total=30)


@dataclass(frozen=True, slots=True)
class Site:
    """A recipe site."""

    id: str
    name: str
    base: str
    # What a recipe's address looks like (others are articles, categories ...).
    recipe: str = r"^/[a-z0-9-]+/?$"
    # Sitemaps with these words are not recipes.
    skip_maps: tuple[str, ...] = ("page", "category", "tag", "author", "attachment", "media")


SITES: dict[str, Site] = {
    site.id: site
    for site in (
        Site("valdemarsro", "Valdemarsro", "https://www.valdemarsro.dk"),
        Site("madensverden", "Madens Verden", "https://madensverden.dk"),
        Site("louisesmadblog", "Louises madblog", "https://www.louisesmadblog.dk"),
        Site("dkkogebogen", "DK-kogebogen", "https://www.dk-kogebogen.dk", r"^/opskrifter/\d+/[a-z0-9-]+/?$"),
        Site("arla", "Arla", "https://www.arla.dk", r"^/opskrifter/[a-z0-9-]+/?$"),
    )
}  # fmt: skip

# Not recipes, whatever the address looks like.
_NOT_RECIPES = re.compile(
    r"madplan|indkoebsliste|guide|tips|konkurrence|nyhedsbrev|om-mig|kontakt|inspiration"
)
_DANISH = str.maketrans({"æ": "ae", "ø": "oe", "å": "aa", "é": "e", "ü": "u", "ö": "oe", "ä": "ae"})
_BACK = ((r"oe", "ø"), (r"aa", "å"), (r"ae", "æ"))


def ascii_words(text: str) -> list[str]:
    """Words as a site writes them in an address: æ is ae, ø oe, å aa."""
    return re.findall(r"[a-z0-9]+", text.lower().translate(_DANISH))


def title_from_slug(slug: str) -> str:
    """ "kylling-i-hvidloegssauce" -> "Kylling i hvidløgssauce" (a fair guess at the title)."""
    words = []
    for part in slug.strip("/").split("-"):
        word = part
        for plain, danish in _BACK:
            word = word.replace(plain, danish)
        words.append(word)
    text = " ".join(w for w in words if w)
    return text[:1].upper() + text[1:]


@dataclass(slots=True)
class _Index:
    """A site's recipes: (address, words of its name, title)."""

    recipes: list[tuple[str, frozenset[str], str]] = field(default_factory=list)
    disallowed: list[str] = field(default_factory=list)
    loaded: float = 0.0


class RecipeSites:
    """Search the chosen sites, and read a recipe from one of them."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self._indexes: dict[str, _Index] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _get(self, url: str, limit: int = SITEMAP_LIMIT) -> str:
        session = page_session(self.hass)
        async with session.get(
            url, headers={**HEADERS, "Accept": "*/*"}, timeout=TIMEOUT, allow_redirects=True
        ) as resp:
            if resp.status >= 400:
                raise aiohttp.ClientError(f"HTTP {resp.status}")
            raw = await resp.content.read(limit)
            return raw.decode(resp.charset or "utf-8", errors="replace")

    async def _robots(self, site: Site) -> tuple[list[str], list[str]]:
        """(sitemaps, disallowed paths) from the site's robots.txt."""
        try:
            text = await self._get(f"{site.base}/robots.txt", 200_000)
        except (aiohttp.ClientError, TimeoutError):
            return [], []
        maps: list[str] = []
        disallowed: list[str] = []
        applies = False
        for raw_line in text.splitlines():
            line = raw_line.split("#")[0].strip()
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "sitemap" and value:
                maps.append(value)
            elif key == "user-agent":
                applies = value == "*"
            elif key == "disallow" and applies and value:
                disallowed.append(value)
        return maps, disallowed

    async def _index(self, site: Site) -> _Index:
        """The site's recipes (read again after a day)."""
        lock = self._locks.setdefault(site.id, asyncio.Lock())
        async with lock:
            index = self._indexes.get(site.id)
            if index and time.monotonic() - index.loaded < CACHE_SECONDS:
                return index
            maps, disallowed = await self._robots(site)
            queue = maps or [f"{site.base}/sitemap.xml", f"{site.base}/sitemap_index.xml"]
            seen: set[str] = set()
            found: dict[str, tuple[str, frozenset[str], str]] = {}
            pattern = re.compile(site.recipe)
            while queue and len(seen) < MAX_SITEMAPS:
                url = queue.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                try:
                    text = await self._get(url)
                except (aiohttp.ClientError, TimeoutError) as err:
                    _LOGGER.debug("Could not read %s: %s", url, err)
                    continue
                locs = re.findall(r"<loc>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</loc>", text)
                if "<sitemapindex" in text:
                    queue += [
                        loc
                        for loc in locs
                        if not any(word in loc.lower() for word in site.skip_maps)
                    ]
                    continue
                for loc in locs:
                    path = urlparse(loc).path
                    if (
                        not pattern.match(path)
                        or _NOT_RECIPES.search(path)
                        or any(_blocked(path, rule) for rule in disallowed)
                    ):
                        continue
                    slug = [part for part in path.split("/") if part][-1]
                    found[loc] = (loc, frozenset(ascii_words(slug)), title_from_slug(slug))
            index = _Index(list(found.values()), disallowed, time.monotonic())
            if index.recipes or site.id not in self._indexes:
                self._indexes[site.id] = index
            return self._indexes[site.id]

    async def async_search(
        self, site_ids: list[str], query: str, limit: int = MAX_RESULTS
    ) -> list[dict[str, Any]]:
        """Recipes on the sites whose name has every word of the query, best first."""
        words = [w for w in ascii_words(query) if len(w) > 2]
        if not words:
            return []
        sites = [SITES[s] for s in site_ids if s in SITES]
        indexes = await asyncio.gather(*(self._index(site) for site in sites))
        hits: list[tuple[int, int, int, dict[str, Any]]] = []
        for order, (site, index) in enumerate(zip(sites, indexes, strict=True)):
            for url, name_words, title in index.recipes:
                if all(any(w.startswith(q) or q in w for w in name_words) for q in words):
                    # Exact words first, then short names (the dish itself, not a variant).
                    exact = sum(q in name_words for q in words)
                    hits.append(
                        (-exact, len(name_words), order, {"site": site.id, "site_name": site.name,
                                                          "url": url, "title": title})
                    )  # fmt: skip
        hits.sort(key=lambda h: h[:3])
        # A few from each site in turn, so one big site doesn't fill the list.
        out: list[dict[str, Any]] = []
        taken: dict[str, int] = {}
        for _, _, _, hit in hits:
            if taken.get(hit["site"], 0) < max(4, limit // max(1, len(sites))):
                out.append(hit)
                taken[hit["site"]] = taken.get(hit["site"], 0) + 1
            if len(out) >= limit:
                break
        return out

    async def async_recipe(
        self, url: str, extract: Callable[[str], Awaitable[dict[str, Any]]] | None = None
    ) -> dict[str, Any] | None:
        """The recipe on a page of one of the sites, in the collection's shape (not saved).

        A page without recipe data is read by the AI (extract), when it is given.
        """
        site = site_of(url)
        page = await async_fetch_page(self.hass, url)
        found = parse_recipe_page(page)
        if (not found or not found.get("ingredients")) and extract is not None:
            found = await extract(page)
        if not found or not found.get("ingredients"):
            return None
        recipe = clean_recipe({**found, "source": "web"})
        recipe["id"] = None
        recipe["site"] = site.name if site else urlparse(url).hostname
        recipe["url"] = url
        return recipe

    async def async_candidates(
        self, site_ids: list[str], words: list[str], per_word: int = 3, most: int = 12
    ) -> list[dict[str, Any]]:
        """Recipes to offer the AI for a plan: a few for each of the week's main items."""
        urls: list[str] = []
        for word in words:
            for hit in (await self.async_search(site_ids, word, limit=per_word * 3))[:per_word]:
                if hit["url"] not in urls:
                    urls.append(hit["url"])
        semaphore = asyncio.Semaphore(4)

        async def read(url: str) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    return await self.async_recipe(url)
                except Exception as err:
                    _LOGGER.debug("Could not read %s: %s", url, err)
                    return None

        recipes = await asyncio.gather(*(read(url) for url in urls[: most * 2]))
        return [r for r in recipes if r][:most]


def _blocked(path: str, rule: str) -> bool:
    """Whether a robots.txt Disallow rule covers a path ("*" is anything, "$" the end)."""
    pattern = re.escape(rule).replace(r"\*", ".*")
    if pattern.endswith(r"\$"):
        pattern = pattern[:-2] + "$"
    return re.match(pattern, path) is not None


def site_of(url: str) -> Site | None:
    """The site an address is on."""
    host = urlparse(url).hostname or ""
    return next(
        (s for s in SITES.values() if (urlparse(s.base).hostname or "").removeprefix("www.")
         == host.removeprefix("www.")),
        None,
    )  # fmt: skip

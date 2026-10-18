"""Mealie: the family's own recipes, saving the plan's recipes, and Mealie's calendar.

Uses the Mealie integration that is already set up in Home Assistant (its
address and API token), so nothing has to be entered twice. Mealie's API:
- GET  /api/recipes                  the recipes (summaries)
- GET  /api/recipes/{slug}           one recipe with ingredients and steps
- POST /api/recipes                  a new recipe (returns its slug)
- PATCH /api/recipes/{slug}          its ingredients, steps, times …
- POST /api/households/mealplans     a dinner on a day (recipe or note)
- DELETE /api/households/mealplans/{id}
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import date
import logging
import random
import re
import time
from typing import Any
import uuid

import aiohttp

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

MEALIE_DOMAIN = "mealie"
CACHE_SECONDS = 3600
PROMPT_RECIPES = 40  # the most recipes (with ingredients) shown to the AI
TIMEOUT = aiohttp.ClientTimeout(total=30)


class MealieError(HomeAssistantError):
    """Mealie could not be reached or answered with an error."""


def mealie_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """The Mealie integration's account, if it is set up and loaded."""
    entries = [
        e
        for e in hass.config_entries.async_entries(MEALIE_DOMAIN)
        if e.state is ConfigEntryState.LOADED
    ]
    return entries[0] if entries else None


def _minutes(text: Any) -> int:
    """'1 time 15 minutter', 'PT35M', '35 min' -> minutes (0 if unknown)."""
    value = str(text or "").lower()
    if match := re.fullmatch(r"pt(?:(\d+)h)?(?:(\d+)m)?", value):
        return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    hours = re.search(r"(\d+)\s*(?:t|h|time)", value)
    minutes = re.search(r"(\d+)\s*m", value)
    total = (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)
    if not total and (plain := re.fullmatch(r"\s*(\d+)\s*", value)):
        total = int(plain.group(1))
    return total


def _ingredient_text(item: Any) -> str:
    """One of Mealie's ingredients as text: '600 g laksefilet'."""
    if not isinstance(item, dict):
        return str(item or "").strip()
    for key in ("display", "originalText", "note"):
        if str(item.get(key) or "").strip():
            return str(item[key]).strip()
    food = (item.get("food") or {}).get("name") if isinstance(item.get("food"), dict) else None
    return str(food or "").strip()


def clean_recipe(data: dict[str, Any]) -> dict[str, Any]:
    """A Mealie recipe in the shape the planner uses."""
    steps = [
        str(step.get("text") or "").strip()
        for step in data.get("recipeInstructions") or []
        if isinstance(step, dict) and str(step.get("text") or "").strip()
    ]
    return {
        "id": data.get("id"),
        "slug": data.get("slug"),
        "name": str(data.get("name") or "").strip(),
        "description": str(data.get("description") or "").strip()[:300],
        "servings": data.get("recipeServings") or None,
        "total_minutes": _minutes(data.get("totalTime")),
        "active_minutes": _minutes(data.get("prepTime")),
        "ingredients": [
            t for t in (_ingredient_text(i) for i in data.get("recipeIngredient") or []) if t
        ],
        "steps": steps,
    }


class MealieLink:
    """Talks to the Mealie that Home Assistant's Mealie integration is set up for."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self._summaries: tuple[float, list[dict[str, Any]]] | None = None
        self._details: dict[str, dict[str, Any]] = {}
        self._group: str | None = None

    @property
    def available(self) -> bool:
        """True if Mealie is set up in Home Assistant."""
        return mealie_entry(self.hass) is not None

    @property
    def url(self) -> str | None:
        """Mealie's address, for links."""
        entry = mealie_entry(self.hass)
        return str(entry.data.get("host") or "").rstrip("/") or None if entry else None

    def recipe_url(self, slug: str) -> str | None:
        """A link to a recipe in Mealie."""
        return f"{self.url}/g/{self._group or 'home'}/r/{slug}" if self.url else None

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        entry = mealie_entry(self.hass)
        if entry is None:
            raise MealieError("Mealie er ikke sat op i Home Assistant")
        session = async_get_clientsession(self.hass, entry.data.get("verify_ssl", True))
        url = f"{str(entry.data['host']).rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {entry.data['api_token']}",
            "Accept": "application/json",
        }
        try:
            async with session.request(
                method, url, headers=headers, timeout=TIMEOUT, **kwargs
            ) as resp:
                if resp.status >= 400:
                    text = (await resp.text())[:200]
                    raise MealieError(f"Mealie svarede {resp.status} på {path}: {text}")
                if resp.status == 204:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MealieError(f"Kunne ikke nå Mealie: {err}") from err

    async def async_group(self) -> str:
        """The group the user's recipes are in (for links)."""
        if self._group is None:
            try:
                me = await self._request("GET", "/api/users/self")
                self._group = str((me or {}).get("groupSlug") or "home")
            except MealieError:
                self._group = "home"
        return self._group

    async def async_summaries(self, force: bool = False) -> list[dict[str, Any]]:
        """All recipes (name, slug, id, description), cached for an hour."""
        if not force and self._summaries and time.monotonic() - self._summaries[0] < CACHE_SECONDS:
            return self._summaries[1]
        items: list[dict[str, Any]] = []
        page = 1
        while page <= 20:
            data = await self._request(
                "GET", "/api/recipes", params={"page": page, "perPage": 200, "orderBy": "name"}
            )
            batch = [
                i for i in (data or {}).get("items") or [] if isinstance(i, dict) and i.get("slug")
            ]
            items += batch
            if page >= int((data or {}).get("total_pages") or 1) or not batch:
                break
            page += 1
        self._summaries = (time.monotonic(), items)
        return items

    async def async_recipe(self, slug: str) -> dict[str, Any]:
        """One recipe with ingredients and steps, cached."""
        if slug not in self._details:
            self._details[slug] = clean_recipe(await self._request("GET", f"/api/recipes/{slug}"))
        return self._details[slug]

    async def async_prompt_recipes(self, avoid: list[str] | None = None) -> list[dict[str, Any]]:
        """Up to PROMPT_RECIPES of the family's recipes, with ingredients, for the AI.

        With more recipes than that, a new mix each time, so all of them get a turn.
        """
        summaries = await self.async_summaries()
        recent = {name.lower() for name in avoid or []}
        fresh = [s for s in summaries if str(s.get("name") or "").lower() not in recent]
        chosen = fresh if len(fresh) <= PROMPT_RECIPES else random.sample(fresh, PROMPT_RECIPES)
        semaphore = asyncio.Semaphore(6)

        async def details(summary: dict[str, Any]) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    return await self.async_recipe(summary["slug"])
                except MealieError as err:
                    _LOGGER.debug("Mealie recipe %s not read: %s", summary["slug"], err)
                    return None

        found = await asyncio.gather(*(details(s) for s in chosen))
        return [r for r in found if r and r["name"]]

    async def async_save_recipe(self, day: dict[str, Any]) -> dict[str, Any]:
        """Save a plan's recipe in Mealie. Returns its slug, id and link."""
        name = str(day.get("dish") or "").strip()
        if not name:
            raise MealieError("Dagen har ingen ret")
        slug = await self._request("POST", "/api/recipes", json={"name": name})
        slug = str(slug or "").strip('"')
        if not slug:
            raise MealieError("Mealie lavede ikke opskriften")
        ingredients = [
            " ".join(
                p
                for p in (str(i.get("amount") or "").strip(), str(i.get("name") or "").strip())
                if p
            )
            for i in day.get("ingredients") or []
        ]
        patch: dict[str, Any] = {
            "description": "Fra REMA 1000-madplanen i Home Assistant."
            + (f" {day['tip']}" if day.get("tip") else ""),
            "recipeServings": day.get("servings") or None,
            "recipeYield": f"{day['servings']} personer" if day.get("servings") else "",
            "totalTime": f"{day['total_minutes']} minutter" if day.get("total_minutes") else None,
            "prepTime": f"{day['active_minutes']} minutter" if day.get("active_minutes") else None,
            "recipeIngredient": [
                {
                    "referenceId": str(uuid.uuid4()),
                    "note": text,
                    "display": text,
                    "originalText": text,
                    "quantity": 0,
                    "unit": None,
                    "food": None,
                }
                for text in ingredients
                if text
            ],
            "recipeInstructions": [
                {
                    "id": str(uuid.uuid4()),
                    "title": "",
                    "summary": "",
                    "text": str(step.get("text") or ""),
                    "ingredientReferences": [],
                }
                for step in day.get("steps") or []
                if str(step.get("text") or "").strip()
            ],
        }
        saved = await self._request("PATCH", f"/api/recipes/{slug}", json=patch)
        self._summaries = None  # a new recipe in the list
        await self.async_group()
        return {
            "slug": slug,
            "id": (saved or {}).get("id"),
            "url": self.recipe_url(slug),
        }

    async def async_recipe_id(self, slug: str) -> str | None:
        """A recipe's id (Mealie's calendar wants the id, not the slug)."""
        try:
            return (await self.async_recipe(slug)).get("id")
        except MealieError:
            return None

    async def async_sync_calendar(self, plan: dict[str, Any]) -> int:
        """Put the plan's dinners in Mealie's calendar, replacing what it put there before.

        Returns how many dinners are in the calendar now.
        """
        count = 0
        for day in plan.get("days") or []:
            if old := day.pop("mealie_entry", None):
                try:
                    await self._request("DELETE", f"/api/households/mealplans/{old}")
                except MealieError as err:
                    _LOGGER.debug("Old Mealie entry %s not deleted: %s", old, err)
            if not day.get("dish"):
                continue
            entry: dict[str, Any] = {"date": day["date"], "entryType": "dinner"}
            recipe_id = await self.async_recipe_id(day["mealie"]) if day.get("mealie") else None
            if recipe_id:
                entry["recipeId"] = recipe_id
            else:
                entry["title"] = day["dish"]
                entry["text"] = "Fra REMA 1000-madplanen"
            made = await self._request("POST", "/api/households/mealplans", json=entry)
            day["mealie_entry"] = (made or {}).get("id")
            count += 1
        for skipped in plan.get("skipped_entries") or []:
            with contextlib.suppress(MealieError):
                await self._request("DELETE", f"/api/households/mealplans/{skipped}")
        plan.pop("skipped_entries", None)
        plan["mealie_synced"] = date.today().isoformat()
        return count

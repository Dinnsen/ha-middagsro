"""Stored settings, favourite dishes and meal plans."""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORE_VERSION = 1
MAX_PLANS = 52

ORGANIC_MODES = ("only", "prefer", "none")
EGG_LEVELS = ("caged", "free_range", "organic")  # skrabeæg < frilandsæg < økologiske æg
FAVORITE_FREQUENCIES = ("weekly", "biweekly", "monthly", "on_offer", "inspiration")
AVOID_OPTIONS = ("meat", "pork", "beef", "fish", "shellfish", "animal_products", "spicy")
ALLERGY_OPTIONS = (
    "gluten",
    "lactose",
    "milk",
    "egg",
    "nuts",
    "peanuts",
    "soy",
    "sesame",
    "celery",
    "mustard",
    "fish",
    "shellfish",
    "molluscs",
    "lupin",
    "sulphites",
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "ai_task_entity": None,
    "start_weekday": 6,  # 0 = monday ... 6 = sunday (the avis starts on sunday)
    "days": 7,
    "budget": 500,
    "organic": "prefer",
    "organic_max_extra_pct": 20,
    "avoid": [],
    "avoid_other": "",
    "allergies": [],
    "allergies_other": "",
    "household": [
        {"role": "adult", "age": 40, "sex": "male"},
        {"role": "adult", "age": 40, "sex": "female"},
        {"role": "child", "age": 8, "sex": "female"},
        {"role": "child", "age": 5, "sex": "male"},
    ],
    "must_haves": [],
    "min_vegetarian": 0,
    "max_vegetarian": 1,
    "leftover_days": 2,
    "fixed_days": [{"weekday": 3, "text": "Rugbrødsdag (kun denne ene dag med rugbrød)"}],
    "max_cook_minutes_weekday": 30,
    "no_repeat_weeks": 3,
    "pantry": "salt, peber, olie, smør, mel, sukker, eddike, bouillon",
    "wishes": "Sund, varieret og børnevenlig mad, som er let at lave og hurtig at rydde op efter.",
    "egg_min": "caged",
    "milk_organic": False,
    "produce_organic": False,
    "auto_generate": False,
    "auto_send": False,
}


def _clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def clean_settings(raw: dict[str, Any]) -> dict[str, Any]:
    """Merge user input with defaults and keep values in sane ranges."""
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    for key in settings:
        if key in raw:
            settings[key] = raw[key]
    settings["start_weekday"] = _clamp(settings["start_weekday"], 0, 6, 6)
    settings["days"] = _clamp(settings["days"], 1, 14, 7)
    settings["budget"] = _clamp(settings["budget"], 0, 100000, 500)
    settings["organic_max_extra_pct"] = _clamp(settings["organic_max_extra_pct"], 0, 500, 20)
    settings["min_vegetarian"] = _clamp(settings["min_vegetarian"], 0, 14, 0)
    settings["max_vegetarian"] = _clamp(settings["max_vegetarian"], 0, 14, 1)
    settings["leftover_days"] = _clamp(settings["leftover_days"], 0, 7, 2)
    settings["max_cook_minutes_weekday"] = _clamp(settings["max_cook_minutes_weekday"], 5, 300, 30)
    settings["no_repeat_weeks"] = _clamp(settings["no_repeat_weeks"], 0, 52, 3)
    if settings["organic"] not in ORGANIC_MODES:
        settings["organic"] = "prefer"
    settings["avoid"] = [a for a in settings["avoid"] or [] if a in AVOID_OPTIONS]
    settings["allergies"] = [a for a in settings["allergies"] or [] if a in ALLERGY_OPTIONS]
    for key in ("avoid_other", "allergies_other", "pantry", "wishes"):
        settings[key] = str(settings[key] or "")[:2000]
    settings["ai_task_entity"] = settings["ai_task_entity"] or None
    settings["auto_generate"] = bool(settings["auto_generate"])
    settings["auto_send"] = bool(settings["auto_send"])
    if settings["egg_min"] not in EGG_LEVELS:
        settings["egg_min"] = "caged"
    settings["milk_organic"] = bool(settings["milk_organic"])
    settings["produce_organic"] = bool(settings["produce_organic"])
    settings["household"] = [
        {
            "role": "child" if member.get("role") == "child" else "adult",
            "age": _clamp(member.get("age"), 0, 120, 30),
            "sex": member.get("sex") if member.get("sex") in ("male", "female") else "other",
        }
        for member in settings["household"] or []
        if isinstance(member, dict)
    ][:20]
    settings["must_haves"] = [
        {
            "name": str(item.get("name") or "").strip()[:200],
            "product_id": int(item["product_id"]) if item.get("product_id") else None,
            "amount": _clamp(item.get("amount"), 1, 99, 1),
        }
        for item in settings["must_haves"] or []
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ][:50]
    settings["fixed_days"] = [
        {"weekday": _clamp(item.get("weekday"), 0, 6, 0), "text": str(item.get("text") or "")[:300]}
        for item in settings["fixed_days"] or []
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ][:14]
    return settings


class RemaPlanStore:
    """Persist settings, favourites and plan history for one account."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the store."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry_id}.mealplans"
        )
        self.settings: dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self.favorites: list[dict[str, Any]] = []
        self.plans: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        """Load from disk."""
        data = await self._store.async_load() or {}
        self.settings = clean_settings(data.get("settings") or {})
        self.favorites = list(data.get("favorites") or [])
        self.plans = list(data.get("plans") or [])

    async def async_save(self) -> None:
        """Write to disk."""
        await self._store.async_save(
            {"settings": self.settings, "favorites": self.favorites, "plans": self.plans}
        )

    # ------------------------------------------------------------- settings

    async def async_set_settings(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Replace the settings."""
        self.settings = clean_settings(raw)
        await self.async_save()
        return self.settings

    # ------------------------------------------------------------- favourites

    async def async_save_favorite(self, favorite: dict[str, Any]) -> dict[str, Any]:
        """Create or update a favourite dish."""
        text = str(favorite.get("text") or "").strip()[:1000]
        if not text:
            raise ValueError("A favourite needs a description")
        frequency = favorite.get("frequency")
        if frequency not in FAVORITE_FREQUENCIES:
            frequency = "inspiration"
        if fav_id := favorite.get("id"):
            for existing in self.favorites:
                if existing["id"] == fav_id:
                    existing.update(text=text, frequency=frequency)
                    await self.async_save()
                    return existing
        new = {"id": uuid.uuid4().hex[:10], "text": text, "frequency": frequency, "last_used": None}
        self.favorites.append(new)
        await self.async_save()
        return new

    async def async_delete_favorite(self, fav_id: str) -> None:
        """Delete a favourite dish."""
        self.favorites = [f for f in self.favorites if f["id"] != fav_id]
        await self.async_save()

    def favorites_due(self, start: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split favourites into (should be on the plan, inspiration/on offer)."""
        gaps = {"weekly": 0, "biweekly": 13, "monthly": 27}
        due: list[dict[str, Any]] = []
        optional: list[dict[str, Any]] = []
        for fav in self.favorites:
            gap = gaps.get(fav.get("frequency", ""))
            if gap is None:
                optional.append(fav)
                continue
            last = fav.get("last_used")
            if not last or (start - date.fromisoformat(last)).days > gap:
                due.append(fav)
            else:
                optional.append(fav)
        return due, optional

    # ------------------------------------------------------------- plans

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        """Return a plan by id."""
        return next((p for p in self.plans if p["id"] == plan_id), None)

    @property
    def latest_plan(self) -> dict[str, Any] | None:
        """The newest plan."""
        return self.plans[0] if self.plans else None

    def plan_for_start(self, start: date) -> dict[str, Any] | None:
        """Return the newest plan that starts on a date."""
        return next((p for p in self.plans if p.get("start_date") == start.isoformat()), None)

    def recent_dishes(self, before: date, weeks: int) -> list[str]:
        """Dish names from plans in the weeks before a date."""
        if weeks <= 0:
            return []
        dishes: list[str] = []
        for plan in self.plans:
            start = date.fromisoformat(plan["start_date"])
            if 0 < (before - start).days <= weeks * 7 + 6:
                dishes.extend(day.get("dish", "") for day in plan.get("days", []))
        return [d for d in dishes if d]

    async def async_add_plan(self, plan: dict[str, Any]) -> None:
        """Store a new plan and mark used favourites."""
        self.plans.insert(0, plan)
        del self.plans[MAX_PLANS:]
        used = {day.get("favorite_id") for day in plan.get("days", []) if day.get("favorite_id")}
        for fav in self.favorites:
            if fav["id"] in used:
                fav["last_used"] = plan["start_date"]
        await self.async_save()

    async def async_mark_sent(self, plan_id: str) -> None:
        """Mark a plan as sent to the REMA list."""
        if plan := self.get_plan(plan_id):
            plan["status"] = "sent"
            plan["sent_at"] = datetime.now().astimezone().isoformat()
            await self.async_save()

    async def async_delete_plan(self, plan_id: str) -> None:
        """Delete a plan."""
        self.plans = [p for p in self.plans if p["id"] != plan_id]
        await self.async_save()

"""Stored settings, favourite dishes and meal plans."""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta
from typing import Any
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store

from .chains import CHAINS
from .const import DOMAIN
from .dishes import dish_key, matches_any

STORE_VERSION = 1
MAX_PLANS = 52
MAX_NOTE = 1000

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
    # Don't send a must-have that is on the REMA list already (and not bought).
    "must_haves_once": False,
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
    "shop_late_week": False,  # also shop thursday-saturday, for offers that start thursday
    "disliked_dishes": [],
    # Things the AI must remember for every plan ("altid frisk broccoli til laks").
    "rules": [],
    # Nutrition per adult's dinner, aimed for as closely as possible.
    "nutrition_enabled": False,
    "protein_pct": 30,
    "carb_pct": 45,
    "fat_pct": 25,
    "kcal_min": 600,
    "kcal_max": 800,
    # Mealie (when its integration is set up): the family's recipes first, and its calendar.
    "mealie_recipes": False,
    "mealie_calendar": False,
    # Other chains whose offers are shown (Tjek dealer ids, see chains.py).
    "chains": [],
    # Tell when something on the watch list is on offer: "" (off), "persistent_notification"
    # (in Home Assistant) or a notify service ("notify.mobile_app_telefon").
    "watch_notify": "",
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
    notify = str(settings["watch_notify"] or "").strip()[:120]
    settings["watch_notify"] = (
        notify if notify == "persistent_notification" or notify.startswith("notify.") else ""
    )
    settings["auto_generate"] = bool(settings["auto_generate"])
    settings["auto_send"] = bool(settings["auto_send"])
    settings["must_haves_once"] = bool(settings["must_haves_once"])
    settings["shop_late_week"] = bool(settings["shop_late_week"])
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
    for key in ("disliked_dishes", "rules"):
        settings[key] = [
            text for text in (str(item or "").strip()[:300] for item in settings[key] or []) if text
        ][:50]
    settings["nutrition_enabled"] = bool(settings["nutrition_enabled"])
    settings["mealie_recipes"] = bool(settings["mealie_recipes"])
    settings["mealie_calendar"] = bool(settings["mealie_calendar"])
    settings["chains"] = list(
        dict.fromkeys(c for c in settings["chains"] or [] if isinstance(c, str) and c in CHAINS)
    )
    for key, default in (("protein_pct", 30), ("carb_pct", 45), ("fat_pct", 25)):
        settings[key] = _clamp(settings[key], 0, 100, default)
    settings["kcal_min"] = _clamp(settings["kcal_min"], 100, 3000, 600)
    settings["kcal_max"] = max(settings["kcal_min"], _clamp(settings["kcal_max"], 100, 3000, 800))
    settings["fixed_days"] = [
        {"weekday": _clamp(item.get("weekday"), 0, 6, 0), "text": str(item.get("text") or "")[:300]}
        for item in settings["fixed_days"] or []
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ][:14]
    return settings


def ensure_line_ids(plan: dict[str, Any]) -> None:
    """Give every shopping line an id, so the panel can change one."""
    for line in plan.get("shopping") or []:
        if isinstance(line, dict) and not line.get("id"):
            line["id"] = uuid.uuid4().hex[:8]


def plan_period(plan: dict[str, Any]) -> tuple[str, str]:
    """The first and last day a plan decides, as ISO dates.

    Its start date is its first dinner; days skipped before it ("we have food
    sunday to tuesday") are part of it too.
    """
    start = min([plan.get("start_date", ""), *(plan.get("skipped") or [])])
    return start, plan.get("end_date", "")


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
        self.note = ""  # the family's wishes for the next plan only
        self.recipes: list[dict[str, Any]] = []  # the recipe collection (recipes.py)
        # The watch list (watch.py), the family's own favourite products, and the offers
        # already told about (key -> when it ends), so each is told once.
        self.watch: list[dict[str, Any]] = []
        self.own_favorites: list[dict[str, Any]] = []
        self.watch_sent: dict[str, str] = {}

    async def async_load(self) -> None:
        """Load from disk."""
        data = await self._store.async_load() or {}
        self.settings = clean_settings(data.get("settings") or {})
        self.favorites = list(data.get("favorites") or [])
        self.plans = list(data.get("plans") or [])
        self.note = str(data.get("note") or "")
        self.recipes = [r for r in data.get("recipes") or [] if isinstance(r, dict) and r.get("id")]
        self.watch = [w for w in data.get("watch") or [] if isinstance(w, dict) and w.get("key")]
        self.own_favorites = [
            p for p in data.get("own_favorites") or [] if isinstance(p, dict) and p.get("id")
        ]
        sent = data.get("watch_sent")
        self.watch_sent = (
            {str(k): str(v) for k, v in sent.items()} if isinstance(sent, dict) else {}
        )
        for plan in self.plans:
            ensure_line_ids(plan)

    async def async_save(self) -> None:
        """Write to disk."""
        for plan in self.plans:
            ensure_line_ids(plan)
        await self._store.async_save(
            {
                "settings": self.settings,
                "favorites": self.favorites,
                "plans": self.plans,
                "note": self.note,
                "recipes": self.recipes,
                "watch": self.watch,
                "own_favorites": self.own_favorites,
                "watch_sent": self.watch_sent,
            }
        )

    # ------------------------------------------------------------- settings

    async def async_set_settings(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Replace the settings."""
        self.settings = clean_settings(raw)
        await self.async_save()
        return self.settings

    # ------------------------------------------------------------- note

    async def async_set_note(self, text: str) -> str:
        """Set the wishes for the next plan (an empty text removes them)."""
        self.note = str(text or "").strip()[:MAX_NOTE]
        await self.async_save()
        return self.note

    # ------------------------------------------------------------- favourites

    async def async_save_favorite(self, favorite: dict[str, Any]) -> dict[str, Any]:
        """Create or update a favourite dish."""
        text = str(favorite.get("text") or "").strip()[:1000]
        if not text:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="favorite_text_required"
            )
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

    def favorites_due(
        self, start: date, recent: list[str] | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split favourites into (should be on the plan, inspiration/on offer).

        A favourite the family had in the last weeks (``recent`` dishes) is no
        inspiration: it would be a repeat. One that is due goes on anyway.
        """
        gaps = {"weekly": 0, "biweekly": 13, "monthly": 27}
        due: list[dict[str, Any]] = []
        optional: list[dict[str, Any]] = []
        for fav in self.favorites:
            gap = gaps.get(fav.get("frequency", ""))
            last = fav.get("last_used")
            if gap is not None and (not last or (start - date.fromisoformat(last)).days > gap):
                due.append(fav)
            elif matches_any(fav["text"], recent or []) is None:
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

    def dinner(self, day: date) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """(plan, day) for a date: the newest plan whose period has it decides.

        A newer plan replaces an older one for its whole period, also on the days it
        skips, so the day is None there (no dinner planned).
        """
        plan = self.plan_covering(day)
        if plan is None:
            return None, None
        iso = day.isoformat()
        return plan, next((d for d in plan.get("days", []) if d.get("date") == iso), None)

    def timeline(self, today: date, start_weekday: int) -> list[dict[str, Any]]:
        """This week's and the coming dinners, one entry per date, as one plan.

        From the family's first weekday of this week to the last planned day
        (at most four weeks). Each date comes from the newest plan covering it.
        """
        last = max((p.get("end_date", "") for p in self.plans), default="")
        if not last or last < today.isoformat():
            return []
        first = today - timedelta(days=(today.weekday() - start_weekday) % 7)
        end = min(date.fromisoformat(last), first + timedelta(days=27))
        out: list[dict[str, Any]] = []
        day = first
        while day <= end:
            plan, dinner = self.dinner(day)
            if plan is not None:
                week_start = day - timedelta(days=(day.weekday() - start_weekday) % 7)
                monday = next(
                    week_start + timedelta(days=i)
                    for i in range(7)
                    if (week_start + timedelta(days=i)).weekday() == 0
                )
                out.append(
                    {
                        "date": day.isoformat(),
                        "plan_id": plan["id"],
                        "skipped": dinner is None,
                        "week": monday.isocalendar().week,
                    }
                )
            day += timedelta(days=1)
        return out

    def plan_covering(self, day: date) -> dict[str, Any] | None:
        """The newest plan whose period includes a day (also if that day is skipped)."""
        iso = day.isoformat()
        return next((p for p in self.plans if plan_period(p)[0] <= iso <= plan_period(p)[1]), None)

    def recent_dishes(self, before: date, weeks: int) -> list[str]:
        """The dinners of the weeks before a date, newest first, each dish once.

        Only what was actually on the table counts: for every date, the newest plan
        covering it (a draft that was replaced never got cooked). Leftover days are
        the same dish as the day before, so they are left out.
        """
        if weeks <= 0:
            return []
        dishes: list[str] = []
        for back in range(1, weeks * 7 + 1):
            iso = (before - timedelta(days=back)).isoformat()
            covering = [p for p in self.plans if plan_period(p)[0] <= iso <= plan_period(p)[1]]
            # A plan whose list was sent is the one the family shopped for.
            plan = next((p for p in covering if p.get("sent_at")), None) or next(
                iter(covering), None
            )
            day = (
                next((d for d in plan.get("days", []) if d.get("date") == iso), None)
                if plan
                else None
            )
            if (
                day is None
                or day.get("uses_leftovers_from")
                or day.get("type") in ("rester", "tom")
            ):
                continue
            dish = str(day.get("dish") or "").strip()
            if not dish or not dish_key(dish) or dish.lower() in (d.lower() for d in dishes):
                continue
            dishes.append(dish)
        return dishes

    async def async_add_plan(self, plan: dict[str, Any]) -> None:
        """Store a new plan and mark used favourites."""
        self.plans.insert(0, plan)
        del self.plans[MAX_PLANS:]
        used = {day.get("favorite_id") for day in plan.get("days", []) if day.get("favorite_id")}
        for fav in self.favorites:
            if fav["id"] in used:
                fav["last_used"] = plan["start_date"]
        await self.async_save()

    async def async_mark_sent(self, plan_id: str, part: str = "main") -> None:
        """Mark a plan (its main list, its late-week list or all) as sent."""
        if plan := self.get_plan(plan_id):
            now = datetime.now().astimezone().isoformat()
            if part in ("main", "all"):
                plan["status"] = "sent"
                plan["sent_at"] = now
            if part in ("late", "all"):
                plan["late_sent_at"] = now
            await self.async_save()

    async def async_delete_plan(self, plan_id: str) -> None:
        """Delete a plan."""
        self.plans = [p for p in self.plans if p["id"] != plan_id]
        await self.async_save()

"""Meal plans: prompt, AI generation, product matching and sending to REMA."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, timedelta
import json
import logging
import math
import re
from typing import Any
import uuid

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .api import Catalog, Offer, Product, RemaClient, RemaError
from .const import DOMAIN
from .storage import RemaPlanStore

_LOGGER = logging.getLogger(__name__)

WEEKDAYS_DA = ("mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag")
AVOID_DA = {
    "meat": "kød",
    "pork": "svinekød",
    "beef": "oksekød",
    "fish": "fisk",
    "shellfish": "skaldyr",
    "animal_products": "alle animalske produkter (maden skal være vegansk)",
    "spicy": "stærk mad",
}
ALLERGY_DA = {
    "gluten": "gluten",
    "lactose": "laktose",
    "milk": "mælkeprotein",
    "egg": "æg",
    "nuts": "nødder",
    "peanuts": "jordnødder",
    "soy": "soja",
    "sesame": "sesam",
    "celery": "selleri",
    "mustard": "sennep",
    "fish": "fisk",
    "shellfish": "krebsdyr",
    "molluscs": "bløddyr",
    "lupin": "lupin",
    "sulphites": "sulfitter",
}
# Products REMA sells as "free from" an allergen.
FREE_FROM = {"gluten": "GLUTENFRI", "lactose": "LAKTOSEFRI", "milk": "LAKTOSEFRI"}

MAX_AI_ROUNDS = 2  # first try + one retry if the list is over budget
RECIPE_CONCURRENCY = 3
SEARCH_CONCURRENCY = 4

_SIZE_MULTI = re.compile(
    r"(\d+)\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*(KG|GR|G|LTR|LITER|L|ML|CL|DL)\b", re.IGNORECASE
)
_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(KG|GR|G|LTR|LITER|L|ML|CL|DL|STK)\b", re.IGNORECASE)
_UNIT_BASE = {
    "kg": ("g", 1000),
    "gr": ("g", 1),
    "g": ("g", 1),
    "ltr": ("ml", 1000),
    "liter": ("ml", 1000),
    "l": ("ml", 1000),
    "dl": ("ml", 100),
    "cl": ("ml", 10),
    "ml": ("ml", 1),
    "stk": ("stk", 1),
    "stk.": ("stk", 1),
    "pcs": ("stk", 1),
    "pk": ("pack", 1),
    "pakke": ("pack", 1),
    "pakker": ("pack", 1),
    "dåse": ("pack", 1),
    "dåser": ("pack", 1),
    "pose": ("pack", 1),
    "poser": ("pack", 1),
    "bakke": ("pack", 1),
    "bakker": ("pack", 1),
    "flaske": ("pack", 1),
    "flasker": ("pack", 1),
    "glas": ("pack", 1),
}
# REMA abbreviates some words in product names.
_ABBREVIATIONS = {"hk": "hakket", "øko": "økologisk", "økologiske": "økologisk"}
# Extra words that make a product something else than what was asked for.
_DIFFERENT_WORDS = {
    "løse",
    "søde",
    "grønt",
    "grøntsager",
    "blanding",
    "mix",
    "pålæg",
    "marineret",
    "krydret",
    "kryddret",
    "paneret",
    "panerede",
    "røget",
    "citronpeber",
    "chili",
    "sauce",
    "dressing",
    "salat",
    "suppe",
    "juice",
    "snack",
    "chips",
}
# First parts of compound words that make it another product (hvidløg is not løg).
_DIFFERENT_PREFIXES = {
    "hvid", "perle", "hvidløgs", "rød", "forårs", "sukker",
    # kakaomælk, havremælk, kærnemælk … are not mælk
    "kakao", "chokolade", "kokos", "mandel", "havre", "soja", "kærne",
}  # fmt: skip
# Words in product names that say nothing about what the product is.
_NEUTRAL_WORDS = {
    "rema",
    "og",
    "med",
    "i",
    "af",
    "til",
    "en",
    "et",
    "dansk",
    "danske",
    "økologisk",
    "kl",
    "stk",
    "gr",
    "g",
    "kg",
    "ltr",
    "ml",
    "fedt",
    "frisk",
    "friske",
}


def signal_plans_updated(entry_id: str) -> str:
    """Dispatcher signal sent when plans or generation status change."""
    return f"{DOMAIN}_{entry_id}_plans_updated"


def next_start(today: date, weekday: int) -> date:
    """The next day (today included) that is the given weekday."""
    return today + timedelta(days=(weekday - today.weekday()) % 7)


def to_base(amount: float, unit: str | None) -> tuple[str, float] | None:
    """Convert an amount to grams, millilitres or pieces."""
    if not unit:
        return None
    base = _UNIT_BASE.get(unit.strip().lower())
    if not base:
        return None
    return base[0], amount * base[1]


def package_size(underline: str | None) -> tuple[str, float] | None:
    """Read the package size from REMA's underline, e.g. '500 GR. / REMA 1000'."""
    if not underline:
        return None
    text = underline.split("/")[0]
    if match := _SIZE_MULTI.search(text):
        count = int(match.group(1))
        size = to_base(float(match.group(2).replace(",", ".")), match.group(3))
        return (size[0], size[1] * count) if size else None
    if match := _SIZE.search(text):
        return to_base(float(match.group(1).replace(",", ".")), match.group(2))
    return None


def packages_needed(amount: float | None, unit: str | None, product: Product) -> int:
    """How many packages of a product cover an amount."""
    if not amount or amount <= 0:
        return 1
    need = to_base(amount, unit)
    if need is None:
        return 1
    if need[0] == "pack":  # cans, packs, bags: one package each
        return max(1, min(20, math.ceil(need[1])))
    size = package_size(product.underline)
    if size and need[0] == size[0] and size[1] > 0:
        return max(1, min(20, math.ceil(need[1] / size[1] - 0.05)))
    if need[0] == "stk" and size is None:
        return max(1, min(20, math.ceil(need[1])))  # loose items sold per piece
    return 1  # e.g. 8 pitabrød from one 375 g bag


_ACCENTS = str.maketrans("éèêëáàâíìîïóòôúùûüç", "eeeeaaaiiiiooouuuuc")


def _tokens(text: str) -> list[str]:
    """Lower-case words of a product name, with REMA's abbreviations expanded."""
    words = re.findall(r"[a-zæøå]+", text.lower().translate(_ACCENTS))
    return [_ABBREVIATIONS.get(w, w) for w in words]


def search_queries(line: dict[str, Any]) -> list[str]:
    """What to search REMA for, best guess first.

    REMA names minced meat "HK. ...KØD", so "kyllingefars" is also tried as
    "hakket kylling", and the line's own name is tried last.
    """
    queries = [line["search"]]
    for word in _tokens(line["search"]):
        if word.endswith("fars") and len(word) > 4:
            meat = word[:-4].rstrip("e")
            queries.append(f"hakket {meat}")
    queries.append(line["name"])
    unique: list[str] = []
    for query in queries:
        if query and query.lower() not in (q.lower() for q in unique):
            unique.append(query)
    return unique


def name_fit(search_words: list[str], product_name: str) -> tuple[int, float]:
    """How well a product name fits the searched words.

    Returns (number of searched words found, price penalty factor). Danish
    compound words count as a match ("skrabeæg" is æg, "laksefileter" is laks),
    but cost a little more than the plain word. Words that make it a different
    product ("søde kartofler", "oksekød 35% grønt", "broccoliblanding",
    "hvidløg" for løg) cost a lot, so they are only chosen if nothing else fits.
    """
    name = [t for t in _tokens(product_name) if len(t) > 1]
    matched = 0
    penalty = 1.0
    for word in search_words:
        if word in name:
            matched += 1
            continue
        compound = next((t for t in name if t.startswith(word) or t.endswith(word)), None)
        if compound is None:
            continue
        matched += 1
        rest = compound[len(word) :] if compound.startswith(word) else compound[: -len(word)]
        # Danish joins compounds with -e- or -s- (laks-e-pålæg, hvidløg-s-...).
        parts = {rest, rest.strip("es")}
        different = parts & (_DIFFERENT_WORDS | _DIFFERENT_PREFIXES)
        penalty += 5.0 if different else 0.15
    for token in name:
        if token in _NEUTRAL_WORDS or any(word in token or token in word for word in search_words):
            continue
        penalty += 5.0 if token in _DIFFERENT_WORDS else 0.15
    return matched, penalty


def extract_json(data: Any) -> dict[str, Any]:
    """Get the JSON object out of an AI answer."""
    if isinstance(data, dict):
        return data
    text = str(data or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("The AI answer contained no JSON object")
    return json.loads(text[start : end + 1])


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ prompt


_EGG_LEVEL = {"caged": 0, "free_range": 1, "organic": 2}
_NOT_EGGS = {"pålæg", "indlæg", "tillæg", "oplæg", "pålægs"}
_NOT_DAIRY_MILK = ("kokos", "mandel", "havre", "soja", "ris", "kakao", "kærne")


def egg_level(product: Product) -> int:
    """0 = skrabeæg (or unknown), 1 = frilandsæg, 2 = økologiske æg."""
    text = f"{product.name} {product.underline or ''}".upper()
    if product.is_organic or re.search(r"(^|[^A-ZÆØÅ])ØKO", text):
        return 2
    if "FRILAND" in text:
        return 1
    return 0


def line_kind(line: dict[str, Any]) -> str | None:
    """Is a shopping line eggs, (dairy) milk or fruit & vegetables?"""
    tokens = _tokens(f"{line.get('search') or ''} {line.get('name') or ''}")
    if any(t == "æg" or (t.endswith("æg") and t not in _NOT_EGGS) for t in tokens):
        return "egg"
    if any(
        "mælk" in t and "chokolade" not in t and not t.startswith(_NOT_DAIRY_MILK) for t in tokens
    ):
        return "milk"
    category = str(line.get("category") or "").lower()
    if "frugt" in category or "grønt" in category:
        return "produce"
    return None


def _household_lines(settings: dict[str, Any]) -> list[str]:
    lines = []
    for member in settings["household"]:
        role = "Voksen" if member["role"] == "adult" else "Barn"
        sex = {"male": "dreng/mand", "female": "pige/kvinde"}.get(member["sex"], "")
        lines.append(f"- {role}, {member['age']} år{', ' + sex if sex else ''}")
    return lines or ["- 2 voksne"]


def build_prompt(
    *,
    settings: dict[str, Any],
    dates: list[date],
    catalog: Catalog | None,
    offers: list[Offer],
    favorites_due: list[dict[str, Any]],
    favorites_optional: list[dict[str, Any]],
    recent_dishes: list[str],
    feedback: str | None = None,
) -> str:
    """Build the instructions for the AI."""
    s = settings
    day_list = ", ".join(f"{WEEKDAYS_DA[d.weekday()]} {d.isoformat()}" for d in dates)
    out: list[str] = [
        "Du er en erfaren dansk madplanlægger. Familien handler i REMA 1000 i Danmark.",
        f"Lav en madplan med aftensmad for {len(dates)} dage: {day_list}.",
        "",
        "HUSSTAND (beregn mængder til hele husstanden; børn spiser mindre end voksne):",
        *_household_lines(s),
        "",
        "KRAV – SKAL OVERHOLDES:",
    ]
    allergies = [ALLERGY_DA[a] for a in s["allergies"]]
    if s["allergies_other"].strip():
        allergies.append(s["allergies_other"].strip())
    if allergies:
        out.append(f"- Allergier – må ALDRIG indgå, heller ikke som spor: {', '.join(allergies)}.")
    avoid = [AVOID_DA[a] for a in s["avoid"]]
    if s["avoid_other"].strip():
        avoid.append(s["avoid_other"].strip())
    if avoid:
        out.append(f"- Undgå helt: {', '.join(avoid)}.")
    out.append(
        f"- Vegetarretter: mindst {s['min_vegetarian']} og højst {s['max_vegetarian']} i perioden."
    )
    if s["leftover_days"]:
        out.append(
            f"- Præcis {s['leftover_days']} dage er restedage: retten dagen før laves i dobbelt "
            'portion, og dagen efter spises resten (type "rester", angiv uses_leftovers_from, '
            "ingen nye ingredienser). Rester må ikke ligge på første dag."
        )
    else:
        out.append("- Ingen restedage; hver dag er en ny ret.")
    for fixed in s["fixed_days"]:
        matching = [d for d in dates if d.weekday() == fixed["weekday"]]
        for day in matching:
            out.append(
                f"- {WEEKDAYS_DA[day.weekday()]} {day.isoformat()}: {fixed['text']} "
                '(fast dag – tæller ikke som restedag, type "fast")'
            )
    out.append(
        f"- Mandag til fredag højst {s['max_cook_minutes_weekday']} minutters aktiv tilberedning."
    )
    if recent_dishes:
        out.append(
            "- Disse retter fra de seneste uger må IKKE gentages: " + "; ".join(recent_dishes) + "."
        )
    if s["budget"]:
        out.append(f"- Hele indkøbslisten skal koste under {s['budget']} kr. med REMA 1000-priser.")
    organic = {
        "only": "Brug udelukkende økologiske varer, hvor REMA 1000 har dem.",
        "prefer": f"Foretræk økologiske varer, når de højst er {s['organic_max_extra_pct']} % dyrere.",
        "none": "Vælg de billigste varer; økologi er ikke et krav.",
    }[s["organic"]]
    out.append(f"- Økologi: {organic}")
    if s["egg_min"] != "caged":
        eggs = "mindst frilandsæg" if s["egg_min"] == "free_range" else "økologiske æg"
        out.append(f"- Æg skal være {eggs}.")
    if s["milk_organic"]:
        out.append("- Mælk skal være økologisk.")
    if s["produce_organic"]:
        out.append("- Frugt og grønt skal være økologisk.")
    if feedback:
        out.append(f"- VIGTIGT fra sidste forsøg: {feedback}")

    out += ["", "ØNSKER:"]
    if s["wishes"].strip():
        out.append(f"- {s['wishes'].strip()}")
    out.append(
        "- Byg retterne op omkring ugens tilbud nedenfor, og marker tilbudsvarer på "
        "indkøbslisten med tilbuddets id."
    )
    if favorites_due:
        out.append("- Disse familiefavoritter SKAL med i perioden (angiv favorite_id på dagen):")
        out += [f"  [{f['id']}] {f['text']}" for f in favorites_due]
    if favorites_optional:
        out.append(
            '- Familiefavoritter til inspiration (ikke krav). Dem markeret "kun på tilbud" '
            "bruges kun, hvis hovedingrediensen er på tilbud. Angiv favorite_id, hvis du bruger én:"
        )
        for fav in favorites_optional:
            note = " (kun på tilbud)" if fav.get("frequency") == "on_offer" else ""
            out.append(f"  [{fav['id']}] {fav['text']}{note}")
    if s["pantry"].strip():
        out.append(
            f"- Basisvarer familien altid har, som IKKE skal på indkøbslisten: {s['pantry'].strip()}."
        )
    if s["must_haves"]:
        names = ", ".join(item["name"] for item in s["must_haves"])
        out.append(
            f"- Faste ugevarer købes separat og skal IKKE på indkøbslisten: {names}. "
            "Du må gerne bruge dem i retterne."
        )

    if offers:
        label = catalog.label if catalog and catalog.label else "Ugens tilbud"
        out += ["", f"UGENS TILBUD I REMA 1000 ({label}) – id | vare | pris | mængde:"]
        for idx, offer in enumerate(offers):
            price = f"{offer.price:g} kr." if offer.price is not None else "?"
            if offer.pre_price:
                price += f" (før {offer.pre_price:g})"
            desc = (offer.description or "").split("\n")[0][:60]
            qty = offer.quantity or ""
            out.append(f"o{idx} | {offer.heading} | {price} | {qty} {desc}".rstrip())

    out += [
        "",
        "Lav KUN overblikket nu – opskrifterne skrives bagefter. Hold svaret kort og præcist; "
        "summary højst én sætning.",
        "Retternes navne skal passe til ingredienserne (kyllingefrikadeller kræver hakket "
        "kylling). Indkøbslisten skal indeholde ALLE ingredienser til alle retter, og mængderne "
        "skal dække dobbelte portioner på dage, der laver rester.",
        "",
        "INDKØBSLISTE: Saml alle ingredienser på tværs af dagene. Angiv for hver vare: navn, "
        "mængde som tal, enhed (g, kg, ml eller l når muligt; pk for pakker, dåser og poser, fx "
        "3 pk hakkede tomater; stk kun for løse enkeltvarer, fx 10 stk æg eller 2 stk "
        "peberfrugt), et søgeord til REMA 1000's varesøgning "
        '(1-3 ord, fx "hakket oksekød", "laks", "broccoli"), kategori (Frugt & grønt, Kød, '
        "Fisk, Mejeri, Brød, Kolonial, Frost eller Andet) og evt. tilbuddets id. Udelad basisvarer.",
        "",
        "Kontrollér til sidst ALLE krav og udfyld checklist ærligt. Skriv afvigelser i deviations.",
        "",
        "SVARFORMAT: Svar KUN med gyldig JSON uden markdown og uden forklaring, præcis sådan:",
        json.dumps(
            {
                "title": "Madplan uge 43",
                "summary": "Kort beskrivelse af ugen",
                "days": [
                    {
                        "date": dates[0].isoformat(),
                        "dish": "Ovnbagt laks med spinatpasta, pesto og broccoli",
                        "type": "normal | vegetar | rester | fast",
                        "favorite_id": None,
                        "uses_leftovers_from": None,
                        "makes_leftovers": False,
                        "servings": 4,
                        "active_minutes": 20,
                        "total_minutes": 35,
                    }
                ],
                "shopping": [
                    {
                        "name": "Laksefilet",
                        "amount": 600,
                        "unit": "g",
                        "search": "laks",
                        "category": "Fisk",
                        "offer": "o12",
                    }
                ],
                "checklist": [{"requirement": "Højst 1 vegetarret", "ok": True}],
                "deviations": "",
            },
            ensure_ascii=False,
        ),
        f"days skal have præcis {len(dates)} elementer i datoorden.",
    ]
    return "\n".join(out)


def build_recipe_prompt(
    *, settings: dict[str, Any], day: dict[str, Any], plan: dict[str, Any]
) -> str:
    """Instructions for the recipe of one dinner."""
    s = settings
    current = date.fromisoformat(day["date"])
    out = [
        "Du er en erfaren dansk kok, der skriver opskrifter til en børnefamilie.",
        f"Skriv opskriften på aftensmaden {WEEKDAYS_DA[current.weekday()]} {day['date']}: "
        f"{day['dish']}.",
        "",
        "HUSSTAND (mængderne skal passe til alle; børn spiser mindre):",
        *_household_lines(s),
    ]
    if day.get("makes_leftovers"):
        out.append(
            "Lav dobbelt portion – halvdelen spises som rester dagen efter. Mængderne skal "
            "dække begge dage."
        )
    allergies = [ALLERGY_DA[a] for a in s["allergies"]]
    if s["allergies_other"].strip():
        allergies.append(s["allergies_other"].strip())
    if allergies:
        out.append(f"Allergier – må ALDRIG indgå: {', '.join(allergies)}.")
    avoid = [AVOID_DA[a] for a in s["avoid"]]
    if s["avoid_other"].strip():
        avoid.append(s["avoid_other"].strip())
    if avoid:
        out.append(f"Undgå helt: {', '.join(avoid)}.")
    if current.weekday() < 5:
        out.append(f"Højst {s['max_cook_minutes_weekday']} minutters aktiv tilberedning.")
    shopping = ", ".join(
        f"{line['name']} ({line['amount']:g} {line['unit']})"
        if line.get("amount") and line.get("unit") and line["unit"] != "pk"
        else line["name"]
        for line in plan.get("shopping", [])
    )
    out += [
        f"Ugens indkøb (brug disse varer og basisvarerne; tilføj ikke nye dyre varer): {shopping}.",
        f"Basisvarer: {s['pantry'].strip() or 'salt og peber'}.",
        "",
        "Skriv til en uerfaren kok: præcise mængder, højst 10 korte trin med minutter, og ét "
        "kort tip, der gør det nemt for børnefamilien.",
        "",
        "SVARFORMAT: Svar KUN med gyldig JSON uden markdown og uden forklaring, præcis sådan:",
        json.dumps(
            {
                "ingredients": [{"name": "laksefilet", "amount": "600 g"}],
                "steps": [{"text": "Tænd ovnen på 200 grader.", "minutes": 1}],
                "tip": "Kort tip",
                "active_minutes": 20,
                "total_minutes": 35,
            },
            ensure_ascii=False,
        ),
    ]
    return "\n".join(out)


# ------------------------------------------------------------------ planner


class MealPlanner:
    """Create meal plans with AI and send them to the REMA shopping list."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        client: RemaClient,
        store: RemaPlanStore,
        get_catalogs: Callable[[], tuple[Catalog | None, Catalog | None]],
        add_items: Callable[[list[dict[str, Any]]], Any],
    ) -> None:
        """Initialize the planner."""
        self.hass = hass
        self.entry_id = entry_id
        self.client = client
        self.store = store
        self._get_catalogs = get_catalogs
        self._add_items = add_items
        self.status: dict[str, Any] = {"state": "idle", "message": None, "started": None}
        self._task: asyncio.Task[None] | None = None
        self._auto_attempted: set[str] = set()

    # ------------------------------------------------------------- status

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, signal_plans_updated(self.entry_id))

    @callback
    def _set_status(self, state: str, message: str | None = None) -> None:
        started = self.status.get("started") if state != "generating" else dt_util.now().isoformat()
        self.status = {"state": state, "message": message, "started": started}
        self._notify()

    @property
    def generating(self) -> bool:
        """True while a plan is being made."""
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------- generation

    def default_start(self) -> date:
        """The start date of the next plan."""
        return next_start(dt_util.now().date(), self.store.settings["start_weekday"])

    @callback
    def async_start_generation(self, start: date | None = None, send: bool = False) -> None:
        """Start making a plan in the background."""
        if self.generating:
            raise HomeAssistantError("Der er allerede ved at blive lavet en madplan")
        self._set_status("generating", "Laver madplan …")
        self._task = self.hass.async_create_background_task(
            self._async_run(start or self.default_start(), send),
            name=f"{DOMAIN} meal plan",
        )

    async def _async_run(self, start: date, send: bool) -> None:
        try:
            plan = await self.async_generate(start)
            if send:
                await self.async_send(plan["id"])
        except Exception as err:
            _LOGGER.exception("Could not make a meal plan")
            self._set_status("error", str(err) or err.__class__.__name__)
        else:
            self._set_status("idle")

    def _ai_entity(self) -> str | None:
        entity = self.store.settings.get("ai_task_entity")
        if entity:
            return entity
        # None lets Home Assistant use its preferred AI task entity; fall back to
        # the first one if no preference is set.
        prefs = self.hass.data.get("ai_task_preferences")
        if prefs is not None and getattr(prefs, "gen_data_entity_id", None):
            return None
        ids = self.hass.states.async_entity_ids("ai_task")
        return ids[0] if ids else None

    async def _async_offers(self, start: date) -> tuple[Catalog | None, list[Offer]]:
        current, upcoming = self._get_catalogs()
        catalog = current
        for candidate in (upcoming, current):
            if (
                candidate
                and candidate.valid_from
                and candidate.valid_to
                and candidate.valid_from.date() <= start <= candidate.valid_to.date()
            ):
                catalog = candidate
                break
        if catalog is None:
            return None, []
        try:
            return catalog, await self.client.async_get_offers(catalog.id)
        except RemaError as err:
            _LOGGER.warning("Could not load offers for the meal plan: %s", err)
            return catalog, []

    async def _async_ask_ai(self, prompt: str, task_name: str) -> dict[str, Any]:
        from homeassistant.components.ai_task import async_generate_data  # noqa: PLC0415

        entity_id = self._ai_entity()

        async def ask(instructions: str) -> Any:
            try:
                result = await async_generate_data(
                    self.hass, task_name=task_name, entity_id=entity_id, instructions=instructions
                )
            except HomeAssistantError as err:
                if "MAX_TOKENS" in str(err).upper():
                    raise HomeAssistantError(
                        f"{err} – AI'ens svar blev for langt. Hæv 'Maksimalt antal tokens' i "
                        "AI-opgavens indstillinger (fx 8000), eller lav en kortere madplan."
                    ) from err
                raise
            return result.data

        try:
            return extract_json(await ask(prompt))
        except ValueError:
            _LOGGER.debug("AI answer was not valid JSON, asking again")
        try:
            return extract_json(
                await ask(
                    prompt + "\n\nDit forrige svar var ikke gyldig JSON. Svar nu KUN med selve "
                    "JSON-objektet."
                )
            )
        except ValueError as err:
            raise HomeAssistantError(f"AI'en svarede ikke med gyldig JSON: {err}") from err

    # ------------------------------------------------------------- recipes

    @staticmethod
    def _is_leftovers(day: dict[str, Any]) -> bool:
        return bool(day.get("uses_leftovers_from")) or day.get("type") == "rester"

    async def _async_recipe(self, day: dict[str, Any], plan: dict[str, Any]) -> None:
        """Fill in ingredients and steps for one day."""
        day.pop("recipe_error", None)
        if self._is_leftovers(day):
            source = day.get("uses_leftovers_from")
            previous = next(
                (d for d in plan["days"] if d["date"] == source),
                None,
            ) or next(
                (
                    d
                    for d in reversed(plan["days"])
                    if d["date"] < day["date"] and not self._is_leftovers(d)
                ),
                None,
            )
            dish = previous["dish"] if previous else "gårsdagens ret"
            day["steps"] = [{"text": f"Varm resten af {dish} op, og server den.", "minutes": 10}]
            day["ingredients"] = []
            day["total_minutes"] = day["total_minutes"] or 15
            day["active_minutes"] = day["active_minutes"] or 5
            return
        prompt = build_recipe_prompt(settings=self.store.settings, day=day, plan=plan)
        try:
            raw = await self._async_ask_ai(prompt, f"REMA 1000 opskrift {day['date']}")
        except HomeAssistantError as err:
            _LOGGER.warning("Could not write the recipe for %s: %s", day["date"], err)
            day["recipe_error"] = str(err)
            return
        cleaned = self._clean_days(
            [{**raw, "date": day["date"]}], [date.fromisoformat(day["date"])]
        )[0]
        day["ingredients"] = cleaned["ingredients"]
        day["steps"] = cleaned["steps"]
        day["tip"] = cleaned["tip"]
        if cleaned["active_minutes"]:
            day["active_minutes"] = cleaned["active_minutes"]
        if cleaned["total_minutes"]:
            day["total_minutes"] = cleaned["total_minutes"]

    async def _async_add_recipes(self, plan: dict[str, Any]) -> None:
        """Write all recipes, a few at a time."""
        semaphore = asyncio.Semaphore(RECIPE_CONCURRENCY)
        cooking = [d for d in plan["days"] if not self._is_leftovers(d)]
        done = 0

        async def one(day: dict[str, Any]) -> None:
            nonlocal done
            async with semaphore:
                await self._async_recipe(day, plan)
            done += 1 if day in cooking else 0
            self._set_status("generating", f"Skriver opskrifter ({done}/{len(cooking)}) …")

        self._set_status("generating", f"Skriver opskrifter (0/{len(cooking)}) …")
        await asyncio.gather(*(one(day) for day in plan["days"]))

    async def async_regenerate_recipe(self, plan_id: str, day_date: str) -> dict[str, Any]:
        """Write one day's recipe again."""
        plan = self.store.get_plan(plan_id)
        day = next((d for d in plan["days"] if d["date"] == day_date), None) if plan else None
        if plan is None or day is None:
            raise HomeAssistantError("Dagen findes ikke i madplanen")
        await self._async_recipe(day, plan)
        await self.store.async_save()
        self._notify()
        if day.get("recipe_error"):
            raise HomeAssistantError(day["recipe_error"])
        return day

    async def async_generate(self, start: date) -> dict[str, Any]:
        """Make, price and store a plan. Returns the plan."""
        settings = self.store.settings
        dates = [start + timedelta(days=i) for i in range(settings["days"])]
        self._set_status("generating", "Henter ugens tilbud …")
        catalog, offers = await self._async_offers(start)
        due, optional = self.store.favorites_due(start)
        recent = self.store.recent_dishes(start, settings["no_repeat_weeks"])

        best: dict[str, Any] | None = None
        feedback: str | None = None
        for attempt in range(MAX_AI_ROUNDS):
            self._set_status(
                "generating",
                "AI'en laver madplanen …"
                if attempt == 0
                else "Planen var over budget – prøver igen …",
            )
            prompt = build_prompt(
                settings=settings,
                dates=dates,
                catalog=catalog,
                offers=offers,
                favorites_due=due,
                favorites_optional=optional,
                recent_dishes=recent,
                feedback=feedback,
            )
            raw = await self._async_ask_ai(prompt, "REMA 1000 madplan")
            self._set_status("generating", "Finder varer og priser i REMA 1000 …")
            plan = await self._async_build_plan(raw, dates, catalog, offers)
            if best is None or plan["total"] < best["total"]:
                best = plan
            if not settings["budget"] or plan["total"] <= settings["budget"]:
                break
            expensive = sorted(
                (line for line in plan["shopping"] if line.get("cost")),
                key=lambda line: line["cost"],
                reverse=True,
            )[:6]
            feedback = (
                f"Indkøbslisten kostede {plan['total']:.0f} kr., men budgettet er "
                f"{settings['budget']} kr. Dyreste varer: "
                + ", ".join(f"{line['name']} ({line['cost']:.0f} kr.)" for line in expensive)
                + ". Vælg billigere retter og flere tilbudsvarer."
            )

        assert best is not None
        best["over_budget"] = bool(settings["budget"]) and best["total"] > settings["budget"]
        await self._async_add_recipes(best)
        await self.store.async_add_plan(best)
        self._notify()
        return best

    async def _async_build_plan(
        self,
        raw: dict[str, Any],
        dates: list[date],
        catalog: Catalog | None,
        offers: list[Offer],
    ) -> dict[str, Any]:
        settings = self.store.settings
        days = self._clean_days(raw.get("days") or [], dates)
        shopping = [
            line for line in (self._clean_line(item) for item in raw.get("shopping") or []) if line
        ]
        for item in settings["must_haves"]:
            shopping.append(
                {
                    "name": item["name"],
                    "amount": item["amount"],
                    "unit": "pk",
                    "search": item["name"],
                    "category": "Faste varer",
                    "offer": None,
                    "must_have": True,
                    "product_id": item.get("product_id"),
                }
            )
        offer_names = {f"o{i}": offer.heading for i, offer in enumerate(offers)}
        for line in shopping:
            line["offer_name"] = offer_names.get(str(line.get("offer") or ""))

        semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY)

        async def match(line: dict[str, Any]) -> None:
            async with semaphore:
                await self._async_match(line)

        await asyncio.gather(*(match(line) for line in shopping))
        total = round(sum(line.get("cost") or 0 for line in shopping), 2)
        return {
            "id": uuid.uuid4().hex[:12],
            "created": dt_util.now().isoformat(),
            "start_date": dates[0].isoformat(),
            "end_date": dates[-1].isoformat(),
            "week": dates[0].isocalendar().week,
            "status": "draft",
            "sent_at": None,
            "title": str(raw.get("title") or f"Madplan uge {dates[0].isocalendar().week}")[:200],
            "summary": str(raw.get("summary") or "")[:2000],
            "days": days,
            "shopping": shopping,
            "checklist": [
                {"requirement": str(c.get("requirement") or "")[:300], "ok": bool(c.get("ok"))}
                for c in raw.get("checklist") or []
                if isinstance(c, dict)
            ],
            "deviations": str(raw.get("deviations") or "")[:2000],
            "total": total,
            "budget": settings["budget"],
            "catalog": {"id": catalog.id, "label": catalog.label} if catalog else None,
            "ai_entity": self._ai_entity(),
        }

    @staticmethod
    def _clean_days(raw_days: list[Any], dates: list[date]) -> list[dict[str, Any]]:
        by_date = {
            str(day.get("date")): day
            for day in raw_days
            if isinstance(day, dict) and day.get("date")
        }
        ordered = [d for d in raw_days if isinstance(d, dict)]
        days = []
        for idx, current in enumerate(dates):
            day = by_date.get(current.isoformat()) or (ordered[idx] if idx < len(ordered) else {})
            days.append(
                {
                    "date": current.isoformat(),
                    "weekday": WEEKDAYS_DA[current.weekday()],
                    "dish": str(day.get("dish") or "Fri aften")[:300],
                    "type": str(day.get("type") or "normal")[:20],
                    "favorite_id": day.get("favorite_id") or None,
                    "uses_leftovers_from": day.get("uses_leftovers_from") or None,
                    "makes_leftovers": bool(day.get("makes_leftovers")),
                    "servings": int(_num(day.get("servings"), 4) or 4),
                    "active_minutes": int(_num(day.get("active_minutes"), 0) or 0),
                    "total_minutes": int(_num(day.get("total_minutes"), 0) or 0),
                    "ingredients": [
                        {
                            "name": str(i.get("name") or "")[:200],
                            "amount": str(i.get("amount") or "")[:60],
                        }
                        for i in day.get("ingredients") or []
                        if isinstance(i, dict) and i.get("name")
                    ],
                    "steps": [
                        {
                            "text": str(st.get("text") if isinstance(st, dict) else st)[:1000],
                            "minutes": int(_num(st.get("minutes"), 0) or 0)
                            if isinstance(st, dict)
                            else 0,
                        }
                        for st in day.get("steps") or []
                        if st
                    ],
                    "tip": str(day.get("tip") or "")[:500],
                }
            )
        return days

    @staticmethod
    def _clean_line(item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict) or not item.get("name"):
            return None
        name = str(item["name"]).strip()[:200]
        return {
            "name": name,
            "amount": _num(item.get("amount")),
            "unit": str(item.get("unit") or "").strip().lower()[:10] or None,
            "search": str(item.get("search") or name).strip()[:80],
            "category": str(item.get("category") or "Andet")[:40],
            "offer": item.get("offer") or None,
            "must_have": False,
            "product_id": None,
        }

    async def _async_match(self, line: dict[str, Any]) -> None:
        """Pick a REMA product for a shopping line and price it."""
        line.update(product=None, packages=1, cost=None, note=None)
        try:
            products = await self.client.async_search_products(line["search"], 15)
            if not line.get("product_id") and not line.get("must_have"):
                await self._async_match_by_name(line, products)
                return
            if not products and line["search"] != line["name"]:
                products = await self.client.async_search_products(line["name"], 15)
        except RemaError as err:
            line["note"] = f"Søgning fejlede: {err}"
            return

        if line.get("product_id"):
            chosen = next((p for p in products if p.id == line["product_id"]), None)
            if chosen:
                self._apply(line, chosen, int(line["amount"] or 1))
                return
        if line.get("must_have"):
            priced = [p for p in products if p.price]
            if priced:
                self._apply(line, priced[0], int(line["amount"] or 1))
            else:
                line["note"] = "Ingen vare fundet – tilføjes som fritekst"
            return

    def _requirement(
        self, line: dict[str, Any]
    ) -> tuple[Callable[[Product], bool], str, list[str]] | None:
        """The family's rule for this kind of item: (test, label, extra searches)."""
        settings = self.store.settings
        kind = line_kind(line)
        if kind == "egg" and settings["egg_min"] != "caged":
            level = _EGG_LEVEL[settings["egg_min"]]
            if level == 1:
                return (
                    lambda p: egg_level(p) >= 1,
                    "frilandsæg eller økologiske æg",
                    ["frilandsæg", "økologiske æg"],
                )
            return lambda p: egg_level(p) >= 2, "økologiske æg", ["økologiske æg", "øko æg"]
        if (kind == "milk" and settings["milk_organic"]) or (
            kind == "produce" and settings["produce_organic"]
        ):
            label = "økologisk mælk" if kind == "milk" else "økologisk frugt og grønt"
            search = line["search"]
            return lambda p: p.is_organic, label, [f"økologisk {search}", f"øko {search}"]
        return None

    async def _async_search_candidates(
        self,
        line: dict[str, Any],
        first: list[Product],
        require: Callable[[Product], bool] | None,
    ) -> tuple[list[Product], dict[int, float]]:
        """Try the search terms in turn until a product matches by name."""
        for idx, query in enumerate(search_queries(line)):
            if idx == 0:
                products = first
            else:
                try:
                    products = await self.client.async_search_products(query, 15)
                except RemaError:
                    continue
            candidates, penalty = self._candidates(line, products, query, require)
            if candidates:
                return candidates, penalty
        return [], {}

    async def _async_match_by_name(self, line: dict[str, Any], first: list[Product]) -> None:
        """Choose the best product by name, the family's rules and price."""
        requirement = self._requirement(line)
        require = requirement[0] if requirement else None
        note: str | None = None
        candidates, penalty = await self._async_search_candidates(line, first, require)
        if not candidates and requirement:
            # None of the usual results meet the rule: search for it directly.
            for query in requirement[2]:
                try:
                    products = await self.client.async_search_products(query, 15)
                except RemaError:
                    continue
                for words in (line["search"], line["name"]):
                    candidates, penalty = self._candidates(line, products, words, require)
                    if candidates:
                        break
                if candidates:
                    break
            if not candidates:
                candidates, penalty = await self._async_search_candidates(line, first, None)
                note = f"Ingen vare opfylder kravet om {requirement[1]} – billigste valgt"
        if not candidates:
            # Better a free-text line than a wrong product.
            line["note"] = "Ingen sikker vare fundet – tilføjes som fritekst"
            return

        def package_cost(product: Product) -> float:
            return packages_needed(line["amount"], line["unit"], product) * (product.price or 0)

        cost = package_cost

        def fit(product: Product) -> tuple[float, bool]:
            return cost(product) * penalty.get(product.id, 1.0), not product.is_advertised

        settings = self.store.settings
        if line.get("prefer") == "relevance":
            # Typed by a person ("letmælk"): only products named close to it,
            # then the lowest price per litre/kilo, so 1 L beats a 250 ml carton.
            best_fit = min(penalty.get(p.id, 1.0) for p in candidates)
            candidates = [p for p in candidates if penalty.get(p.id, 1.0) <= best_fit + 0.5]
            unit = next((p.compare_unit for p in candidates if p.compare_unit_price), None)

            def unit_cost(product: Product) -> float:
                if unit is None:
                    return product.price or 0
                if product.compare_unit == unit and product.compare_unit_price:
                    return product.compare_unit_price
                return math.inf  # cannot be compared per litre/kilo

            cost = unit_cost
            # min() keeps REMA's own order on ties.
            cheapest = min(candidates, key=lambda p: (cost(p), not p.is_advertised))
        else:
            cheapest = min(candidates, key=fit)
        # An organic alternative must be the same kind of product, not just organic.
        organic = [
            p
            for p in candidates
            if p.is_organic and penalty.get(p.id, 1.0) <= penalty.get(cheapest.id, 1.0) + 0.5
        ]
        best_organic = min(organic, key=fit) if organic else None
        chosen = cheapest
        if settings["organic"] == "only":
            if best_organic:
                chosen = best_organic
            else:
                line["note"] = "Ingen økologisk variant fundet"
        elif settings["organic"] == "prefer" and best_organic:
            limit = cost(cheapest) * (1 + settings["organic_max_extra_pct"] / 100)
            if cost(best_organic) <= limit + 0.001:
                chosen = best_organic
        self._apply(line, chosen, packages_needed(line["amount"], line["unit"], chosen))
        if note:
            line["note"] = note

    def _candidates(
        self,
        line: dict[str, Any],
        products: list[Product],
        query: str,
        require: Callable[[Product], bool] | None = None,
    ) -> tuple[list[Product], dict[int, float]]:
        """Products that really are what the line asks for, and a price penalty
        for each (extra words in the name make a product a worse fit)."""
        priced = [p for p in products[:12] if p.price and (require is None or require(p))]
        if not priced:
            return [], {}
        words = [w for w in _tokens(query) if len(w) > 1 and w not in _NEUTRAL_WORDS]
        if not words:
            return [], {}
        fits = {p.id: name_fit(words, p.name) for p in priced}
        penalty = {pid: fit[1] for pid, fit in fits.items()}

        # The AI built the dish on an offer: if a matching product is on offer, use it.
        if line.get("offer"):
            on_offer = [
                p
                for p in priced
                if (p.is_advertised or p.is_campaign)
                and any(w in "".join(_tokens(p.name)) for w in words)
            ]
            if on_offer:
                return self._free_from(on_offer), penalty

        best = max(fit[0] for fit in fits.values())
        if best == 0:
            return [], penalty  # nothing is called what we searched for
        if line.get("prefer") == "relevance" and best < len(words):
            # Typed by a person: every word must fit, or "kage til Anna" could
            # become anything with "ana" in it. Free text is the safe answer.
            return [], penalty
        relevant = [p for p in priced if fits[p.id][0] == best]
        # Stay in the department of the best-fitting product (fish, not cold cuts).
        anchor = min(relevant, key=lambda p: penalty.get(p.id, 1.0)).department
        relevant = [p for p in relevant if p.department == anchor] or relevant
        return self._free_from(relevant), penalty

    def _free_from(self, relevant: list[Product]) -> list[Product]:
        """Prefer gluten-free / lactose-free products when the family needs them."""
        for allergy in self.store.settings["allergies"]:
            marker = FREE_FROM.get(allergy)
            if marker:
                free = [p for p in relevant if marker in f"{p.name} {p.underline or ''}".upper()]
                if free:
                    relevant = free
        return relevant

    @staticmethod
    def _apply(line: dict[str, Any], product: Product, packages: int) -> None:
        line["packages"] = packages
        line["cost"] = round(packages * (product.price or 0), 2)
        line["product"] = {
            "id": product.id,
            "name": product.name,
            "underline": product.underline,
            "price": product.price,
            "normal_price": product.normal_price,
            "is_advertised": product.is_advertised,
            "is_campaign": product.is_campaign,
            "is_organic": product.is_organic,
            "image": product.image,
        }

    # ------------------------------------------------------------- sending

    async def async_quick_add(self, text: str) -> dict[str, Any]:
        """Add something typed by a person: a matching REMA product, else free text."""
        amount, name = parse_quick_add(text)
        if not name:
            raise HomeAssistantError("Skriv hvad der skal på listen")
        line: dict[str, Any] = {
            "name": name,
            "search": name,
            "amount": amount,
            "unit": "pk",
            "category": None,
            "offer": None,
            "must_have": False,
            "product_id": None,
            "prefer": "relevance",
        }
        await self._async_match(line)
        product = line.get("product")
        if product:
            await self._add_items([{"product_id": product["id"], "amount": line["packages"]}])
            added = (
                f"{line['packages']} × {product['name']}"
                if line["packages"] > 1
                else product["name"]
            )
            if product.get("underline"):
                added += f" ({product['underline'].split('/')[0].strip()})"
        else:
            await self._add_items([{"name": name, "amount": amount}])
            added = f"{amount} × {name}" if amount > 1 else name
        return {
            "text": text,
            "added": added,
            "product_id": product["id"] if product else None,
            "free_text": product is None,
            "note": line.get("note"),
        }

    async def async_send(self, plan_id: str | None = None) -> dict[str, Any]:
        """Put a plan's shopping list on the primary REMA list."""
        plan = self.store.get_plan(plan_id) if plan_id else self.store.latest_plan
        if plan is None:
            raise HomeAssistantError("Der er ingen madplan at sende")
        items: list[dict[str, Any]] = []
        for line in plan["shopping"]:
            if line.get("product"):
                items.append({"product_id": line["product"]["id"], "amount": line["packages"]})
            else:
                amount = line.get("amount")
                label = line["name"]
                if amount and line.get("unit") and line["unit"] != "pk":
                    label += f" ({amount:g} {line['unit']})"
                items.append({"name": label, "amount": 1})
        await self._add_items(items)
        await self.store.async_mark_sent(plan["id"])
        self._notify()
        return plan

    # ------------------------------------------------------------- automatic

    @callback
    def async_check_auto_generate(self, upcoming: Catalog | None) -> None:
        """Make next week's plan when the new avis is out (if switched on)."""
        settings = self.store.settings
        if not settings["auto_generate"] or upcoming is None or self.generating:
            return
        start = self.default_start()
        if start == dt_util.now().date():
            start += timedelta(days=7)
        if not (
            upcoming.valid_from
            and upcoming.valid_to
            and upcoming.valid_from.date() <= start <= upcoming.valid_to.date()
        ):
            return
        key = start.isoformat()
        if self.store.plan_for_start(start) or key in self._auto_attempted:
            return
        self._auto_attempted.add(key)
        _LOGGER.info("New tilbudsavis found, making the meal plan for %s", key)
        self.async_start_generation(start, send=settings["auto_send"])

    @callback
    def async_cancel(self) -> None:
        """Stop a running generation (on unload)."""
        if self._task and not self._task.done():
            self._task.cancel()


_QUICK_COUNT = re.compile(
    r"^\s*(\d{1,2})\s*"
    r"(?:x|×|\*|stk\.?|styk(?:ker)?|pk\.?|pakk(?:e|er)|pos(?:e|er)|dås(?:e|er)|flask(?:e|er)|bakk(?:e|er))?"
    r"\s+(?!(?:g|gr|kg|gram|l|ml|dl|cl|liter)\b)(.+?)\s*$",
    re.IGNORECASE,
)
# Siri and Assist often write small numbers as words.
_NUMBER_WORDS = {
    "en": 1, "et": 1, "to": 2, "tre": 3, "fire": 4, "fem": 5, "seks": 6,
    "syv": 7, "otte": 8, "ni": 9, "ti": 10, "elleve": 11, "tolv": 12,
}  # fmt: skip
_NUMBER_WORD = re.compile(rf"^\s*({'|'.join(_NUMBER_WORDS)})(?=\s)", re.IGNORECASE)


def parse_quick_add(text: str) -> tuple[int, str]:
    """'3 x æg', '3x æg', '3 stk æg', '3 æg' and 'tre æg' -> (3, 'æg').

    '500 g mel' stays as text.
    """
    # Shortcuts can wrap the text in quotes or <...>.
    text = (text or "").strip().strip("<>\"'“”„«»").strip()
    text = _NUMBER_WORD.sub(lambda m: str(_NUMBER_WORDS[m.group(1).lower()]), text)
    if match := _QUICK_COUNT.match(text):
        return max(1, int(match.group(1))), match.group(2)
    if re.match(r"^\s*\d+\s*[x×*]\S", text):  # '3xæg'
        count, rest = re.match(r"^\s*(\d+)\s*[x×*](.+)$", text).groups()
        return max(1, int(count)), rest.strip()
    return 1, text


def plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    """The fields of a plan needed for lists."""
    return {
        key: plan.get(key)
        for key in ("id", "title", "start_date", "end_date", "week", "status", "total", "budget")
    } | {"dishes": [day["dish"] for day in plan.get("days", [])]}


def parse_date(value: str | None) -> date | None:
    """Parse an ISO date from the panel."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as err:
        raise HomeAssistantError(f"Ugyldig dato: {value}") from err

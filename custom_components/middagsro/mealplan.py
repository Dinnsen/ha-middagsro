"""Meal plans: prompt, AI generation, product matching and sending to REMA."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, timedelta
import json
import logging
import math
import re
from typing import Any, Protocol
import uuid

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .amounts import (
    line_packages,
    package_size,
    packages_needed,
    parse_amount,
    pieces_per_package,
    to_base,
)
from .api import DANISH_TIME, Catalog, Offer, Product, RemaClient, RemaError, parse_time
from .bilka import BilkaSearch
from .budget import plan_budget
from .chains import CHAINS, ChainError, ChainOffers, runs_on
from .const import DOMAIN
from .dishes import (
    check_plan,
    day_wishes,
    fixed_rest_dates,
    food_conflicts,
    household_portions,
    is_cooked,
    is_rest_text,
    same_dish,
)
from .errors import _failed, _invalid
from .ingredients import CATALOG, catalogue_entry, spec_for
from .matcher import ProductMatcher
from .matching import (
    SEARCH_CONCURRENCY,
    apply_spec,
    head_word,
    line_spec,
    merge_lines,
    needs_review,
    plan_total,
    prices_from,
)
from .mealie import MealieError, MealieLink
from .messages import async_danish
from .recipes import (
    async_extract,
    async_save_recipe,
    disliked_names,
    favorite_recipe,
    find_recipe,
    ingredient_texts,
    mark_planned,
    prompt_recipes,
    recipe_to_day,
    scale_amount,
)
from .rema_recipes import RemaRecipes
from .sites import RecipeSites
from .storage import RemaPlanStore
from .store_client import genitive
from .structures import choices_structure, plan_structure, recipe_structure, schema_library
from .words import (
    _DIFFERENT_PREFIXES,
    _DIFFERENT_WORDS,
    _name_words,
    _tokens,
    _uses_item,
    canned_tomatoes,
    ingredient_name,
    is_tap_water,
    pantry_words,
    stock_cubes,
)

_LOGGER = logging.getLogger(__name__)

# The week's main items to look for on the recipe sites.
SITE_WORDS = (
    "kylling", "kalkun", "oksekød", "svinekød", "flæsk", "mørbrad", "nakke", "kotelet",
    "lam", "laks", "torsk", "fisk", "rejer", "tun", "pølse", "bacon", "skinke", "hakket",
)  # fmt: skip
RECIPE_EXTRAS_PER_DAY = 4  # items an AI recipe may add to the list for a dinner
CHAIN_OFFERS_IN_PROMPT = 240  # other chains' offers the plan may be built on, in all
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

ISSUE_NO_AI_TASK = "no_ai_task"
# A conversation agent can stand in for an AI Task (LiteLLM, Extended OpenAI …
# only offer agents); Home Assistant's own agent can't write a plan.
AGENT_DOMAIN = "conversation"
OWN_AGENT = "conversation.home_assistant"


def ai_choices(hass: HomeAssistant) -> list[dict[str, str]]:
    """The AI Task entities, then the conversation agents that are AI models."""
    tasks = [
        {"entity_id": state.entity_id, "name": state.name, "kind": "ai_task"}
        for state in hass.states.async_all("ai_task")
    ]
    agents = [
        {"entity_id": state.entity_id, "name": state.name, "kind": "agent"}
        for state in hass.states.async_all(AGENT_DOMAIN)
        if state.entity_id != OWN_AGENT
    ]
    return tasks + agents


AI_TASK_DOCS_URL = "https://www.home-assistant.io/integrations/ai_task/"

MAX_AI_ROUNDS = 3  # first try + two more when the plan breaks a rule or the budget
RECIPE_CONCURRENCY = 3

# REMA abbreviates some words in product names.


# What an AI service says when it can't answer, and what the family can do about it.
_AI_NO_CREDIT = re.compile(
    r"\b402\b|prepayment|credits? (are )?depleted|insufficient[_ ]quota|exceeded your current "
    r"quota|billing|credit balance|payment required",
    re.IGNORECASE,
)
_AI_BUSY = re.compile(
    r"\b(429|529|503)\b|rate.?limit|resource_exhausted|overloaded|too many requests|unavailable",
    re.IGNORECASE,
)
_AI_KEY = re.compile(
    r"\b(401|403)\b|api key|api_key|permission_denied|unauthori[sz]ed|authentication",
    re.IGNORECASE,
)


def ai_provider(text: str, fallback: str | None = None) -> str:
    """Who the AI is from, as the error tells it (else the AI's name)."""
    lowered = text.lower()
    for word, name in (
        ("ai.studio", "Google AI Studio"),
        ("google", "Google AI Studio"),
        ("gemini", "Google AI Studio"),
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("mistral", "Mistral"),
    ):
        if word in lowered:
            return name
    return fallback or "AI-tjenesten"


def ai_problem(err: Exception, name: str | None = None) -> HomeAssistantError | None:
    """An AI service's error the family can do something about, in plain words (else None)."""
    text = str(err)
    if _AI_NO_CREDIT.search(text):
        return _failed("ai_no_credit", provider=ai_provider(text, name))
    if _AI_KEY.search(text) and not _AI_BUSY.search(text):
        return _failed("ai_key_failed", provider=ai_provider(text, name))
    if _AI_BUSY.search(text):
        return _failed("ai_busy", provider=ai_provider(text, name))
    return None


def signal_plans_updated(entry_id: str) -> str:
    """Dispatcher signal sent when plans or generation status change."""
    return f"{DOMAIN}_{entry_id}_plans_updated"


def next_start(today: date, weekday: int) -> date:
    """The next day (today included) that is the given weekday."""
    return today + timedelta(days=(weekday - today.weekday()) % 7)


def plan_week(dates: list[date]) -> int:
    """The week a plan is named after: the week of its first monday.

    A plan from sunday to saturday follows REMA's avis, which is named after
    the week the monday is in.
    """
    monday = next((d for d in dates if d.weekday() == 0), dates[0])
    return monday.isocalendar().week


def plan_title(dates: list[date]) -> str:
    """The name of a plan, e.g. 'Madplan uge 43'."""
    return f"Madplan uge {plan_week(dates)}"


def late_offers(offers: list[Offer], first_day: date) -> dict[int, date]:
    """Offers that only start after the plan's first day (e.g. thursday): index -> day."""
    late: dict[int, date] = {}
    for idx, offer in enumerate(offers):
        start = parse_time(offer.valid_from)
        if start is None:
            continue
        day = start.astimezone(DANISH_TIME).date()
        if day > first_day:
            late[idx] = day
    return late


def _alternative_from(item: dict[str, Any]) -> dict[str, Any]:
    """An alternative from a line's product dict (the one that was chosen before)."""
    return {
        key: item.get(key) for key in ("id", "name", "underline", "price", "is_organic", "image")
    }


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
    result = json.loads(text[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("The AI answer was not a JSON object")
    return result


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ prompt


def fixed_day_text(settings: dict[str, Any], day: dict[str, Any]) -> str | None:
    """What the family fixed for this weekday ("Spaghetti og kødsovs"), if it is such a day."""
    try:
        weekday = date.fromisoformat(str(day.get("date"))).weekday()
    except ValueError:
        return None
    for fixed in settings.get("fixed_days") or []:
        text = str(fixed.get("text") or "").strip()
        if text and fixed.get("weekday") == weekday and not is_rest_text(text):
            return text
    return None


def rule_lines(settings: dict[str, Any]) -> list[str]:
    """The family's standing rules ("altid frisk broccoli til laks"), for every prompt."""
    return [f"- {rule}" for rule in settings.get("rules") or []]


def nutrition_target(settings: dict[str, Any]) -> str | None:
    """The nutrition the family aims for per adult's dinner, as a prompt line."""
    if not settings.get("nutrition_enabled"):
        return None
    return (
        f"{settings['kcal_min']}-{settings['kcal_max']} kcal pr. voksenportion, og energien "
        f"fordelt så tæt som muligt på {settings['protein_pct']} % protein, "
        f"{settings['carb_pct']} % kulhydrat og {settings['fat_pct']} % fedt"
    )


NUTRITION_KEYS = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")


def clean_nutrition(raw: Any) -> dict[str, float] | None:
    """The AI's estimate of a dish's nutrition per adult portion."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, float] = {}
    for key in NUTRITION_KEYS:
        value = _num(raw.get(key))
        if value is not None and 0 <= value < 10000:
            out[key] = round(value, 1)
    return out if "kcal" in out else None


def _household_lines(settings: dict[str, Any]) -> list[str]:
    lines = []
    for member in settings["household"]:
        role = "Voksen" if member["role"] == "adult" else "Barn"
        lines.append(f"- {role}, {member['age']} år")
    return lines or ["- 2 voksne"]


def no_leftover_weekdays(settings: dict[str, Any]) -> set[int]:
    """The weekdays (0 = monday) the family never wants leftovers on."""
    return {int(w) for w in settings.get("no_leftover_weekdays") or []}


# Offers that are never dinner: the avis's household goods, sweets and drinks.
_NOT_DINNER = re.compile(
    r"\b(vaske|opvask|toilet|køkkenrulle|shampoo|tandpasta|tandbørst|bleer|deo|barber|servietter|"
    r"skraldepos|bagepapir|alufolie|rengøring|wc|skyllemiddel|stearinlys|batteri|hundemad|kattemad|"
    r"foder|blomster|planter|slik|chokolade|lakrids|vingummi|chips|snacks|sodavand|cola|øl|vin\b|"
    r"spiritus|cigaret|tobak|is\b|flødeis|kage|kiks|småkager|kaffe|te\b|juice|saft|energidrik|"
    r"vitamin|kosttilskud|legetøj|tøj|sokker|strømper|undertøj|pande\b|gryde|knive|glas\b|krus|"
    r"tallerken|lyskæde|julepynt|påskepynt)",
    re.IGNORECASE,
)


def dinner_offer(heading: str, description: str | None, settings: dict[str, Any]) -> bool:
    """Is an avis offer worth showing the AI: food for dinner, and nothing the
    family can't eat (a pork offer is no use to a family that avoids pork)."""
    text = f"{heading} {(description or '').split(chr(10))[0]}"
    if _NOT_DINNER.search(heading):
        return False
    return not food_conflicts([text], settings)


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
    skipped: list[date] | None = None,
    note: str | None = None,
    late: dict[int, date] | None = None,
    mealie: list[dict[str, Any]] | None = None,
    own: list[dict[str, Any]] | None = None,
    disliked: list[str] | None = None,
    surprise: bool = False,
    favorite_recipes: dict[str, dict[str, Any]] | None = None,
    wishes: dict[str, str] | None = None,
    web: list[dict[str, Any]] | None = None,
    shop: str = "REMA 1000",
    prices: bool = True,
    chain_offers: list[tuple[str, str, dict[str, Any]]] | None = None,
) -> str:
    """Build the instructions for the AI (shop: where the family shops; prices: whether
    every item has a price there, or only the offers; chain_offers: other chains' offers
    the plan may be built on too, as (id, dealer id, offer))."""
    s = settings
    day_list = ", ".join(f"{WEEKDAYS_DA[d.weekday()]} {d.isoformat()}" for d in dates)
    portions = f"{household_portions(s):g}".replace(".", ",")
    out: list[str] = [
        f"Du er en erfaren dansk madplanlægger. Familien handler i {shop} i Danmark.",
        f"Lav en madplan med aftensmad for {len(dates)} dage: {day_list}.",
        "",
        "HUSSTAND (beregn mængder til hele husstanden; børn spiser mindre end voksne):",
        *_household_lines(s),
        f"- Regn med ca. {portions} voksenportioner pr. aftensmad (det dobbelte på dage, der "
        "laver rester til dagen efter).",
        "",
        "KRAV – SKAL OVERHOLDES:",
    ]
    if s.get("rules"):
        out.append(
            "- FAMILIENS FASTE REGLER – gælder forud for alt andet i denne besked, også for "
            "indkøbslisten og retternes ingredienser. Gå dem igennem én for én til sidst, og "
            "skriv hver regel som sit eget punkt i checklist med ok: true/false:"
        )
        out += [f"  {line}" for line in rule_lines(s)]
    if s.get("portion_percent", 100) != 100:
        out.append(
            "- Beregn shopping og ingredienser til husstandens normale standardportioner. "
            "Systemet skalerer bagefter mængderne til familiens valgte portionsstørrelse; "
            "du skal ikke selv lægge ekstra til."
        )
    if skipped:
        out.append(
            "- Disse dage springes over (ingen aftensmad og intet på indkøbslisten): "
            + ", ".join(f"{WEEKDAYS_DA[d.weekday()]} {d.isoformat()}" for d in skipped)
            + ". Rester spises dagen efter den ret, de kommer fra, i listen ovenfor."
        )
    allergies = [ALLERGY_DA[a] for a in s["allergies"]]
    if s["allergies_other"].strip():
        allergies.append(s["allergies_other"].strip())
    if allergies:
        out.append(f"- Allergier – må ALDRIG indgå, heller ikke som spor: {', '.join(allergies)}.")
    avoid = [AVOID_DA[a] for a in s["avoid"]]
    if s["avoid_other"].strip():
        avoid.append(s["avoid_other"].strip())
    if avoid:
        out.append(
            f"- Undgå helt: {', '.join(avoid)} – hverken i retterne, som tilbehør eller på "
            "indkøbslisten."
        )
    if "animal_products" in s["avoid"]:
        out.append(
            "- Alle retter er veganske: intet kød, fisk, skaldyr, æg, mejeri (mælk, fløde, smør, "
            "ost) eller honning. Brug plantebaserede varer i stedet."
        )
    elif "meat" in s["avoid"]:
        out.append(
            "- Alle retter er vegetariske (fisk er heller ikke kød, så fisk kun hvis det ikke "
            "undgås): ingen kødvarer på indkøbslisten."
        )
    out.append(
        f"- Vegetarretter: mindst {s['min_vegetarian']} og højst {s['max_vegetarian']} i perioden."
    )
    # A fixed leftovers day ("torsdag: rester") is one of the leftover days.
    rest_fixed = fixed_rest_dates(s, dates)
    total = max(s["leftover_days"], len(rest_fixed))
    if total:
        line = f"- Præcis {total} {'dag er restedag' if total == 1 else 'dage er restedage'} i alt"
        if rest_fixed:
            named = ", ".join(f"{WEEKDAYS_DA[d.weekday()]} {d.isoformat()}" for d in rest_fixed)
            more = total - len(rest_fixed)
            line += f" – den faste restedag ({named}) tæller med, så der skal " + (
                f"være {more} restedag{'e' if more > 1 else ''} mere" if more else "ikke være andre"
            )
        out.append(
            line + ". Til en restedag laves retten dagen før i dobbelt portion, og dagen efter "
            'spises resten (type "rester", angiv uses_leftovers_from, ingen nye ingredienser). '
            "Rester må ikke ligge på første dag."
        )
        if total > len(rest_fixed) and (banned := no_leftover_weekdays(s)):
            out.append(
                "- Rester må ALDRIG ligge på: "
                + ", ".join(WEEKDAYS_DA[w] for w in sorted(banned))
                + " – de dage laves der altid en ny ret."
            )
    else:
        out.append("- Ingen restedage; hver dag er en ny ret.")
    for fixed in s["fixed_days"]:
        matching = [d for d in dates if d.weekday() == fixed["weekday"]]
        for day in matching:
            if is_rest_text(fixed["text"]):
                out.append(
                    f"- {WEEKDAYS_DA[day.weekday()]} {day.isoformat()}: {fixed['text']} "
                    '(fast restedag, type "rester": resten af en ret fra en dag før, der laves i '
                    'dobbelt portion – angiv uses_leftovers_from – eller "Rester fra ugen")'
                )
            else:
                out.append(
                    f"- {WEEKDAYS_DA[day.weekday()]} {day.isoformat()}: {fixed['text']} "
                    '(fast dag – tæller ikke som restedag, type "fast"). Lav den PRÆCIS som '
                    "familien beskriver den, ikke finere: kun de varer, beskrivelsen nævner "
                    "(plus basisvarer), færdige produkter som de er."
                )
    out.append(
        f"- Mandag til fredag højst {s['max_cook_minutes_weekday']} minutters aktiv tilberedning."
    )
    dislikes = list(
        dict.fromkeys(d.strip() for d in [*s["disliked_dishes"], *(disliked or [])] if d.strip())
    )
    if dislikes:
        out.append(
            "- Familien kan ikke lide disse retter – brug dem ALDRIG, heller ikke varianter af dem: "
            + "; ".join(dislikes)
            + "."
        )
    if recent_dishes:
        out.append(
            "- Disse retter fra de seneste uger må IKKE gentages – heller ikke som variant med "
            "andet tilbehør (laks er laks, frikadeller er frikadeller): "
            + "; ".join(recent_dishes)
            + "."
        )
    if target := nutrition_target(s):
        out.append(f"- Næring: {target}.")
    if s["budget"] and not prices:
        out.append(
            f"- Hold indkøbslisten inden for ca. {s['budget']} kr. (et skøn: kun tilbudsvarerne "
            "har en kendt pris – brug gerne mange af dem)."
        )
    elif s["budget"]:
        out.append(
            f"- Hele indkøbslisten skal koste under {s['budget']} kr. med {shop}-priser"
            + (
                " (det, der er tilbage af ugens madbudget – hold dig gerne et stykke under)."
                if s.get("monthly_budget")
                else "."
            )
        )
    organic = {
        "only": f"Brug udelukkende økologiske varer, hvor {shop} har dem.",
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
    if note:
        out.append(
            "- Familiens ønsker til netop denne madplan – SKAL følges (fx varer de allerede har, "
            "der skal bruges før en bestemt dato, eller en bestemt ret på en bestemt dag). Varer, "
            f"familien allerede har, skal IKKE på indkøbslisten: {note}"
        )
    if wishes:
        out.append(
            "- Disse dage har familien selv bestemt retten – brug PRÆCIS den ret den dag (som "
            "dish), læg dens varer på indkøbslisten, og brug den ikke andre dage: "
            + "; ".join(
                f"{WEEKDAYS_DA[date.fromisoformat(day).weekday()]} {day}: {dish}"
                for day, dish in sorted(wishes.items())
            )
        )
    out += ["", "ØNSKER:"]
    if surprise:
        out.append(
            "- OVERRASK FAMILIEN: lav en uge med retter, de aldrig har fået – fra andre køkkener "
            "(fx koreansk, peruviansk, etiopisk, georgisk, libanesisk, vietnamesisk), med "
            "spændende smage, teknikker og overraskende kombinationer. Hver dag skal være "
            "forskellig og føles som en lille opdagelse, men stadig til at lave på en hverdag, "
            "børnevenlig og inden for alle krav ovenfor. Brug ikke familiens kendte retter."
        )
    if s["wishes"].strip():
        out.append(f"- {s['wishes'].strip()}")
    out.append(
        "- Byg retterne op omkring ugens tilbud nedenfor, og marker tilbudsvarer på "
        "indkøbslisten med tilbuddets id."
    )
    links = favorite_recipes or {}

    def favorite_line(fav: dict[str, Any]) -> str:
        line = f"  [{fav['id']}] {fav['text']}"
        if fav.get("frequency") == "on_offer":
            line += " (kun på tilbud)"
        if recipe := links.get(fav["id"]):
            line += (
                f" – familiens egen opskrift {recipe['id']} (skriv den i recipe_id, og følg dens "
                f"ingredienser præcis): {', '.join(ingredient_texts(recipe))[:300]}"
            )
        return line

    if favorites_due and not surprise:
        out.append("- Disse familiefavoritter SKAL med i perioden (angiv favorite_id på dagen):")
        out += [favorite_line(f) for f in favorites_due]
    if favorites_optional and not surprise:
        out.append(
            '- Familiefavoritter til inspiration (ikke krav). Dem markeret "kun på tilbud" '
            "bruges kun, hvis hovedingrediensen er på tilbud. Bruger du én, så lav den præcis "
            "som beskrevet (samme tilbehør) og angiv favorite_id:"
        )
        out += [favorite_line(f) for f in favorites_optional]
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

    if mealie:
        out += [
            "",
            "FAMILIENS OPSKRIFTER I MEALIE – tag udgangspunkt i dem: brug en af dem, når den "
            "passer til ugens tilbud og kravene (skriv dens id i mealie på dagen, og brug "
            "opskriftens navn som dish; indkøbslisten følger opskriftens ingredienser). Er "
            "der ikke en passende, så find selv på en ret (mealie: null). "
            "id | ret | ingredienser:",
        ]
        out += [f"{r['slug']} | {r['name']} | {', '.join(r['ingredients'])[:300]}" for r in mealie]
    if web and not surprise:
        out += [
            "",
            "OPSKRIFTER FRA FAMILIENS MADSIDER – brug gerne et par af dem, når de passer til "
            "ugens tilbud og kravene: skriv dens id i recipe_id på dagen og opskriftens navn som "
            "dish; indkøbslisten følger opskriftens ingredienser. id | ret | side | ingredienser:",
        ]
        out += [
            f"{r['id']} | {r['name']} | {r.get('site') or ''} | "
            f"{', '.join(ingredient_texts(r))[:300]}"
            for r in web
        ]
    if own and not surprise:
        out += [
            "",
            "FAMILIENS OPSKRIFTSSAMLING – retter de synes om (❤️ = favorit, brug dem gerne "
            "ofte). Brug en af dem, når den passer til ugens tilbud og kravene: skriv dens id i "
            "recipe_id på dagen og opskriftens navn som dish; indkøbslisten følger opskriftens "
            "ingredienser. Ellers recipe_id: null. id | ret | ingredienser:",
        ]
        out += [
            f"{r['id']} | {'❤️ ' if r['favorite'] else ''}{r['name']} | "
            f"{', '.join(ingredient_texts(r))[:300]}"
            for r in own
        ]
    if offers:
        label = catalog.label if catalog and catalog.label else "Ugens tilbud"
        late = late or {}
        out += ["", f"UGENS TILBUD I {shop.upper()} ({label}) – id | vare | pris | mængde:"]
        if late and s["shop_late_week"]:
            out.append(
                'Tilbud markeret "gælder først fra" må KUN bruges i retter på eller efter den dag '
                "(familien køber dem den dag)."
            )
        for idx, offer in enumerate(offers):
            starts = late.get(idx)
            if starts and not s["shop_late_week"]:
                continue  # the family shops once, before this offer starts
            if not dinner_offer(offer.heading, offer.description, s):
                continue  # not food for dinner, or something the family can't eat
            price = f"{offer.price:g} kr." if offer.price is not None else "?"
            if offer.pre_price:
                price += f" (før {offer.pre_price:g})"
            desc = (offer.description or "").split("\n")[0][:60]
            qty = offer.quantity or ""
            line = f"o{idx} | {offer.heading} | {price} | {qty} {desc}".rstrip()
            if starts:
                line += f" | gælder først fra {WEEKDAYS_DA[starts.weekday()]} {starts.isoformat()}"
            out.append(line)

    if chain_offers:
        by_chain: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for key, dealer_id, entry in chain_offers:
            by_chain.setdefault(dealer_id, []).append((key, entry))
        names = ", ".join(CHAINS.get(d, d) for d in by_chain)
        out += [
            "",
            f"FAMILIEN HANDLER OGSÅ I {names.upper()}. Byg retterne på disse butikkers tilbud "
            f"på lige fod med {genitive(shop)}: vælg ugens bedste tilbud på tværs af butikkerne. "
            "En vare fra en anden butik markeres med dens tilbuds-id (fx k12) og kommer på den "
            "butiks egen indkøbsliste – så samme vare købes ét sted. Hold antallet af butikker "
            "pr. uge rimeligt (helst højst 2-3 ud over " + shop + ").",
        ]
        for dealer_id, entries in by_chain.items():
            out.append(
                f"TILBUD I {CHAINS.get(dealer_id, dealer_id).upper()} – id | vare | pris | mængde:"
            )
            for key, entry in entries:
                if not dinner_offer(str(entry.get("heading") or ""), entry.get("description"), s):
                    continue
                cost = entry.get("price")
                text = f"{cost:g} kr." if isinstance(cost, (int, float)) else "?"
                if entry.get("pre_price"):
                    text += f" (før {entry['pre_price']:g})"
                desc = str(entry.get("description") or "").split("\n")[0][:60]
                qty = str(entry.get("quantity") or "")
                out.append(f"{key} | {entry.get('heading')} | {text} | {qty} {desc}".rstrip())
    out += [
        "",
        "Lav KUN overblikket nu – opskrifterne skrives bagefter. Hold svaret kort og præcist; "
        "summary højst én sætning.",
        "Retternes navne skal passe til ingredienserne (kyllingefrikadeller kræver hakket "
        "kylling). Indkøbslisten skal indeholde ALLE ingredienser til alle retter, og mængderne "
        "skal dække dobbelte portioner på dage, der laver rester.",
        "Brug de varer, en dansk familie normalt bruger til retten, og som er nemmest: hakkede "
        "tomater på dåse til kødsovs, lasagne og bolognese (ikke friske tomater, der skal "
        "hakkes), frossen spinat, revet ost. Samme slags vare til forskellige formål står hver "
        "for sig (friske tomater til gnavegrønt OG hakkede tomater på dåse til sovsen).",
        "Retterne skal smage af noget – som en god hjemmelavet version, ikke en nødløsning. Tag "
        "de varer med, der giver smagen: løg og hvidløg, krydderier og friske eller tørrede "
        "krydderurter, bouillon, tomatpuré, citron, fløde eller ost, hvor retten normalt har det "
        "(fx lasagne: hakket oksekød, løg, hvidløg, gulerod, hakkede tomater, tomatpuré, "
        "oregano/basilikum, bouillon, lasagneplader, mælk, smør, mel og revet ost).",
        "Brug den kødtype, retten traditionelt laves af – også når en anden er på tilbud: "
        "hakkebøffer, burgere, bøf bearnaise og chili con carne af hakket oksekød; frikadeller "
        "af hakket svine- og kalvekød; kyllingeretter af kylling. Et tilbud på en anden kødtype "
        "er en grund til at vælge en anden ret, ikke til at lave retten om.",
        "Angiv for hver dag i uses navnene på de varer fra indkøbslisten, retten bruger "
        "(præcis som de står på listen; ikke basisvarer). Restedage har en tom liste.",
        "",
        "INDKØBSLISTE: Saml alle ingredienser på tværs af dagene. Angiv for hver vare: navn, "
        "mængde som tal, enhed (g, kg, ml eller l når muligt; pk for pakker, dåser og poser, fx "
        "3 pk hakkede tomater; stk kun for løse enkeltvarer, fx 10 stk æg eller 2 stk "
        f"peberfrugt), et søgeord til {genitive(shop)} varesøgning "
        '(1-3 ord, fx "hakket oksekød", "laks", "broccoli"), kategori (Frugt & grønt, Kød, '
        "Fisk, Mejeri, Brød, Kolonial, Frost eller Andet), evt. tilbuddets id"
        + (" (også en anden butiks, fx k12)" if chain_offers else "")
        + " og varenøglen (key): den af varenøglerne herunder, varen ER – ikke en, der ligner "
        "(kaffirblade er ikke laurbærblade) – ellers null. Udelad basisvarer.",
        "Varenøgler: " + ", ".join(sorted(CATALOG)) + ".",
        "",
        (
            "checklist: kun familiens faste regler, én pr. punkt, ærligt. De øvrige krav "
            "kontrolleres automatisk. Skriv afvigelser i deviations."
            if s.get("rules")
            else "checklist kan være tom – kravene kontrolleres automatisk. Skriv afvigelser i "
            "deviations."
        ),
        "",
        *([f"RETTELSER FRA SIDSTE FORSØG – det vigtigste: {feedback}", ""] if feedback else []),
        "SVARFORMAT: Svar KUN med gyldig JSON uden markdown og uden forklaring, præcis sådan:",
        json.dumps(
            {
                "title": plan_title(dates),
                "summary": "Kort beskrivelse af ugen",
                "days": [
                    {
                        "date": dates[0].isoformat(),
                        "dish": "Ovnbagt laks med spinatpasta, pesto og broccoli",
                        "type": "normal",
                        "favorite_id": None,
                        "uses_leftovers_from": None,
                        "makes_leftovers": False,
                        "servings": 4,
                        "active_minutes": 20,
                        "total_minutes": 35,
                        "uses": ["Laksefilet", "Spinatpasta", "Pesto", "Broccoli"],
                        "mealie": None,
                        "recipe_id": None,
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
                        "key": "laks",
                    }
                ],
                "checklist": [{"requirement": "Fredag er altid pizzadag", "ok": True}],
                "deviations": "",
            },
            ensure_ascii=False,
        ),
        "type er normal, vegetar, rester eller fast. "
        f"days skal have præcis {len(dates)} elementer i datoorden.",
    ]
    return "\n".join(out)


def build_recipe_prompt(
    *, settings: dict[str, Any], day: dict[str, Any], plan: dict[str, Any]
) -> str:
    """Instructions for the recipe of one dinner."""
    s = {**settings, "portion_percent": plan.get("portion_percent", 100)}
    current = date.fromisoformat(day["date"])
    out = [
        "Du er en erfaren dansk kok, der skriver opskrifter til en børnefamilie.",
        f"Skriv opskriften på aftensmaden {WEEKDAYS_DA[current.weekday()]} {day['date']}: "
        f"{day['dish']}.",
        "",
        "HUSSTAND (mængderne skal passe til alle; børn spiser mindre):",
        *_household_lines(s),
    ]
    if s.get("portion_percent", 100) != 100:
        out.append(
            f"Familiens portionsstørrelse er {s['portion_percent']} % af standard. "
            "Indkøbslisten er allerede skaleret. Opskriften skal bruge de viste mængder "
            "og må ikke skalere dem igen."
        )
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
    if s.get("rules"):
        out += [
            "FAMILIENS FASTE REGLER – gælder forud for alt andet i denne besked:",
            *rule_lines(s),
        ]
    fixed = fixed_day_text(s, day)
    if fixed:
        out.append(
            f'FAST DAG: familien har selv bestemt denne dag: "{fixed}". Lav den PRÆCIS så '
            "enkelt, som det står – ingen ingredienser ud over dem, beskrivelsen nævner (og "
            "basisvarer), ingen ekstra krydderier, urter eller bouillon. Færdige produkter "
            "(fx pastasovs på glas) bruges, som de er. Få korte trin."
        )
    if target := nutrition_target(s):
        out.append(f"Næring: {target}. Juster mængderne, så retten rammer det.")
    if plan.get("note"):
        out.append(
            f"Familiens ønsker til ugen (brug varer, de allerede har, hvor det passer): {plan['note']}"
        )

    def describe(line: dict[str, Any]) -> str:
        product = line.get("product") or {}
        bought = (product or line.get("avis_item") or {}).get("name")
        text = str(line["name"])
        size = package_size(product.get("underline")) if product else None
        if line.get("amount") and line.get("unit") and line["unit"] != "pk":
            text += f" ({line['amount']:g} {line['unit']})"
        elif size and size[0] in ("g", "ml") and line.get("packages"):
            # "2 x 400 g": what is actually bought, so the recipe fits it.
            text += f" ({line['packages']} × {size[1]:g} {size[0]})"
        if bought and bought.lower() != line["name"].lower():
            text += f" [købes som {bought}]"
        return text

    lines = plan.get("shopping", [])
    uses = {name.lower() for name in day.get("uses") or []}
    mine = [line for line in lines if line["name"].lower() in uses]
    if mine:
        # Only this dish's items: the fresh tomatoes for snacks on another day
        # are not the lasagne's tomatoes.
        out.append(
            "Rettens varer fra indkøbslisten (brug dem, som de købes – fx hakkede tomater på "
            "dåse hældes i, de skal ikke hakkes; tilføj ikke nye dyre varer, men gerne billige "
            "smagsgivere som krydderier, krydderurter, hvidløg, bouillon og tomatpuré – de "
            "kommer på indkøbslisten): " + ", ".join(describe(line) for line in mine) + "."
        )
    else:
        out.append(
            "Ugens indkøb (brug disse varer og basisvarerne; tilføj ikke nye dyre varer, men "
            "gerne billige smagsgivere som krydderier, krydderurter, hvidløg, bouillon og "
            "tomatpuré – de kommer på indkøbslisten): "
            + ", ".join(describe(line) for line in lines)
            + "."
        )
    out += [
        f"Basisvarer: {s['pantry'].strip() or 'salt og peber'}.",
        "",
        "Lav retten, som en dansk familie normalt laver den, med de nemmeste varer: hakkede "
        "tomater på dåse i kødsovs og lasagne, ikke friske tomater, der skal hakkes.",
        *(
            []
            if fixed
            else [
                "Den skal smage godt: krydr ordentligt (salt og peber er ikke nok), byg smag "
                "med løg, hvidløg, krydderurter, bouillon eller tomatpuré, og giv sovsen tid "
                "til at simre. Brug den kødtype, retten traditionelt laves af (hakkebøffer af "
                "oksekød).",
            ]
        ),
        "Skriv til en uerfaren kok: præcise mængder, højst 10 korte trin med minutter, og ét "
        "kort tip, der gør det nemt for børnefamilien.",
        "Krav til opskriften:",
        "- Hvert krydderi står for sig med sin egen mængde (fx 2 tsk karrypulver, 1 tsk "
        'spidskommen) – aldrig bare "krydderier" eller "grøntsager". Et færdigt krydderi '
        "eller en karrypasta må gerne bruges, men så med sit navn.",
        "- Retten er det, navnet siger: kødboller formes af det rå fars og brunes, før de "
        "kommer i sovsen; en korma har en cremet sovs (fløde, yoghurt eller kokosmælk).",
        "- Trinnene står i den rækkefølge, man laver dem, og modsiger ikke hinanden (farsen "
        "steges ikke løs, hvis den skal formes til boller bagefter).",
        "- Alle ingredienser bruges i trinnene, og alt i trinnene står i ingredienslisten – "
        "også tilbehøret (ris, kartofler, brød), hvis retten serveres med det.",
        "",
        "SVARFORMAT: Svar KUN med gyldig JSON uden markdown og uden forklaring, præcis sådan:",
        json.dumps(
            {
                "ingredients": [{"name": "laksefilet", "amount": "600 g"}],
                "steps": [{"text": "Tænd ovnen på 200 grader.", "minutes": 1}],
                "tip": "Kort tip",
                "active_minutes": 20,
                "total_minutes": 35,
                "nutrition": {
                    "kcal": 750,
                    "protein_g": 50,
                    "carbs_g": 80,
                    "fat_g": 22,
                    "fiber_g": 9,
                },
            },
            ensure_ascii=False,
        ),
        "nutrition er dit bedste skøn over næringen i én voksenportion.",
    ]
    return "\n".join(out)


# ------------------------------------------------------------------ planner


_VAGUE_INGREDIENTS = {
    "krydderier",
    "krydderi",
    "krydderiblanding",
    "grøntsager",
    "grønt",
    "sovs",
    "sauce",
    "tilbehør",
    "diverse",
}


def recipe_problems(raw: Any, settings: dict[str, Any] | None = None) -> list[str]:
    """What is wrong with an AI recipe, in words the AI can act on (empty: nothing)."""
    if not isinstance(raw, dict):
        return ["Svaret var ikke en opskrift."]
    problems: list[str] = []
    if settings:
        names = [
            str(i.get("name") or "") for i in raw.get("ingredients") or [] if isinstance(i, dict)
        ]
        for ingredient, rule in food_conflicts(names, settings):
            problems.append(
                f"Opskriften bruger {ingredient}, men familien har {rule}: lav den uden, "
                "med noget andet i stedet."
            )
    vague = [
        str(i.get("name"))
        for i in raw.get("ingredients") or []
        if isinstance(i, dict) and str(i.get("name") or "").strip().lower() in _VAGUE_INGREDIENTS
    ]
    if vague:
        problems.append(
            f"Ingrediensen {', '.join(vague)} er for upræcis: skriv hvert krydderi eller "
            "hver grøntsag for sig med mængde."
        )
    steps = [
        {"text": s} if isinstance(s, str) else s
        for s in raw.get("steps") or []
        if (isinstance(s, str) and s.strip()) or (isinstance(s, dict) and s.get("text"))
    ]
    if len(steps) < 2:
        problems.append("Der er for få trin: skriv hele fremgangsmåden.")
    sentences = [
        part
        for step in steps
        for part in re.split(r"[.!;]", str(step["text"]).lower())
        if part.strip()
    ]
    fried = next(
        (
            i
            for i, part in enumerate(sentences)
            if re.search(r"\b(steg|brun)", part)
            and re.search(r"fars|kød|kylling", part)
            and not re.search(r"bolle|frikadelle", part)
        ),
        None,
    )
    formed = next((i for i, part in enumerate(sentences) if re.search(r"\bform", part)), None)
    if fried is not None and formed is not None and fried < formed:
        problems.append(
            "Farsen steges, før bollerne formes: form bollerne af den rå fars, og brun dem bagefter."
        )
    return problems


def link_favorites(
    plan: dict[str, Any],
    favorites: list[dict[str, Any]],
    links: dict[str, dict[str, Any]],
    store: RemaPlanStore,
) -> None:
    """Tie the plan's dinners to the favourites and own recipes they are.

    The AI forgets to say favorite_id for a favourite it used, and it likes to
    make its own version of a dish the family has a recipe for. So: a dinner that
    is one of the favourites gets its favorite_id; a favourite's own recipe is
    used; and so is a ❤️ recipe in the collection for the same dish.
    """
    for day in plan["days"]:
        if not is_cooked(day):
            continue
        if not day.get("favorite_id"):
            fav = next((f for f in favorites if same_dish(day["dish"], f["text"])), None)
            if fav is not None:
                day["favorite_id"] = fav["id"]
        if day.get("recipe_id"):
            continue
        # Only a recipe that really is this dish: its ingredients replace the AI's.
        recipe = links.get(day.get("favorite_id") or "")
        if recipe is None or not same_dish(recipe["name"], day["dish"], strict=True):
            recipe = next(
                (
                    r
                    for r in store.recipes
                    if r.get("favorite")
                    and r.get("rating") != "dislike"
                    and (r["ingredients"] or r["steps"])
                    and same_dish(r["name"], day["dish"], strict=True)
                ),
                None,
            )
        if recipe is not None:
            day["recipe_id"] = recipe["id"]


def recipe_factor(settings: dict[str, Any], recipe: dict[str, Any], day: dict[str, Any]) -> float:
    """How much of a recipe the household needs: twice when it makes leftovers."""
    portions = (
        household_portions(settings)
        * settings.get("portion_percent", 100)
        / 100
        * (2 if day.get("makes_leftovers") else 1)
    )
    servings = recipe.get("servings") or 4
    if servings < 2:
        servings = 4  # "1 tærte" is not one serving: unknown, so a normal recipe's four
    # At most 4 times the recipe (more with bigger portions), so a misread serving
    # count can't multiply the shopping; freezer plans scale on their own.
    limit = 4.0 * max(1.0, settings.get("portion_percent", 100) / 100)
    return float(max(0.25, min(limit, portions / servings)))


def recipe_line(ingredient: dict[str, Any], factor: float = 1.0) -> dict[str, Any] | None:
    """A shopping line for a recipe's ingredient ("600 g laksefilet"), scaled.

    Grams and millilitres are scaled and rounded up to tens; pieces and packages
    rounded up to whole ones. A spoonful or a clove is one package, whatever the
    scale. Without an amount it is one package. None for what is not bought: a
    heading in the recipe ("Dej:"), its equipment, water.
    """
    raw = str(ingredient.get("name") or "")
    name = ingredient_name(raw)
    amount: float | None = None
    unit: str | None = None
    if parsed := parse_amount(str(ingredient.get("amount") or "")):
        number, raw_unit = parsed
        base = to_base(number, raw_unit)
        if base is not None and base[0] in ("g", "ml"):
            amount, unit = base[1] * factor, base[0]
            amount = math.ceil(amount / 10) * 10 if amount > 10 else round(amount, 1)
        elif base is not None:
            amount, unit = math.ceil(number * factor), ("stk" if base[0] == "stk" else "pk")
        elif raw_unit in ("", "styk", "stks", "x"):
            amount, unit = math.ceil(number * factor), "stk"
        elif raw_unit in ("ps", "bundt", "bdt", "bk", "bæger", "bægre", "rulle", "ruller"):
            amount, unit = math.ceil(number * factor), "pk"
    if amount is None:
        amount, unit = 1, "pk"
    product = ingredient.get("product") or {}
    line = {
        "id": uuid.uuid4().hex[:8],
        "name": name[:1].upper() + name[1:],
        "amount": amount,
        "unit": unit,
        "search": ingredient_name(str(product.get("name") or name))[:80],
        "category": line_category(name),
        "offer": None,
        "must_have": False,
        "product_id": product.get("id") or None,
        "recipe": True,
    }
    if "rummo" in _tokens(f"{ingredient.get('name') or ''} {product.get('name') or ''}"):
        line["product_id"] = None
    if query := stock_cubes(name):
        line.update(
            name=query[:1].upper() + query[1:], search=query, amount=1, unit="pk", stock_cubes=True
        )
    if not apply_spec(line, spec_for(raw, str(line["search"]), str(line["category"]))):
        return None
    return line


_CATEGORY_WORDS = {
    "Kød": ("kød", "kylling", "okse", "svin", "gris", "bacon", "pølse", "frikadell", "kebab", "lam", "kalkun"),
    "Fisk": ("laks", "torsk", "fisk", "rejer", "tun", "sej", "rødspætte", "kulmule", "muslinger"),
    "Mejeri": ("mælk", "fløde", "ost", "smør", "yoghurt", "skyr", "creme", "parmesan", "feta", "æg"),
    "Brød": ("brød", "boller", "pita", "tortilla", "wrap"),
    "Frost": ("frossen", "frosne", "frost"),
    "Frugt & grønt": (
        "løg", "kartof", "gulerod", "gulerødder", "broccoli", "spinat", "tomat", "agurk", "salat",
        "peber", "squash", "champignon", "citron", "lime", "æble", "banan", "porre", "hvidløg",
        "ingefær", "chili", "persille", "basilikum", "koriander", "avocado", "majs", "ærter",
        "bønner", "kål", "selleri", "aubergine", "græskar", "hokkaido", "svampe", "pære", "appelsin",
    ),
}  # fmt: skip


def line_category(name: str) -> str:
    """A shopping category for an ingredient's name, as the panel groups them."""
    if canned_tomatoes(name):
        return "Kolonial"  # chopped/peeled tomatoes are canned, not fresh produce
    words = _tokens(name)
    for category, hints in _CATEGORY_WORDS.items():
        if any(w == h or w.startswith(h) or w.endswith(h) for w in words for h in hints):
            return category
    return "Kolonial"


def _names_match(line: dict[str, Any], ingredient: dict[str, Any]) -> bool:
    """Is a shopping line this ingredient: every word of the ingredient in its name.

    A compound counts ("laksefilet" is laks), unless its first part makes it
    another thing: hvidløg is not løg, havremælk is not mælk.
    """
    wanted = _name_words(ingredient_name(ingredient.get("name") or ""))
    if not wanted:
        return False
    # The same thing by the catalogue ("stort løg", "løg, i både" and "strimlet løg").
    if line.get("key") and line["key"] == spec_for(str(ingredient.get("name") or "")).key:
        return True
    product = line.get("product") or {}
    have = (
        _name_words(ingredient_name(line["name"]))
        | _name_words(ingredient_name(line.get("search") or ""))
        | _name_words(product.get("name") or "")
    )

    def found(word: str) -> bool:
        if word in have:
            return True
        for h in have:
            if len(h) <= 3 or len(h) <= len(word):
                continue
            if h.endswith(word):
                rest = h[: -len(word)]
            elif h.startswith(word) and len(word) > 3:
                rest = h[len(word) :]
            else:
                continue
            if {rest, rest.strip("es")} & (_DIFFERENT_PREFIXES | _DIFFERENT_WORDS):
                continue
            return True
        return False

    return all(found(w) for w in wanted)


def fit_amounts(plan: dict[str, Any]) -> list[str]:
    """Buy as much as the recipes use: a line's packages grow when the dishes need more.

    The overview's amounts are the AI's first guess; the recipes are written
    afterwards, for the household, and two dishes may share a line. Only lines
    with a REMA product of a known size (or in grams/millilitres) are raised,
    never more than fourfold, and never lowered. Returns the lines changed.
    """
    changed: list[str] = []
    for line in plan.get("shopping") or []:
        if line.get("must_have") or line.get("added") or line.get("sent"):
            continue
        needs: dict[str, float] = {}
        for day in plan.get("days") or []:
            if not is_cooked(day):
                continue
            for ingredient in day.get("ingredients") or []:
                if not _names_match(line, ingredient):
                    continue
                parsed = parse_amount(str(ingredient.get("amount") or ""))
                base = to_base(parsed[0], parsed[1]) if parsed else None
                if base is None and parsed and not parsed[1]:
                    base = ("stk", parsed[0])
                if base is not None:
                    needs[base[0]] = needs.get(base[0], 0) + base[1]
        if not needs:
            continue
        product = line.get("product") or {}
        size = package_size(product.get("underline")) if product else None
        packages = int(line.get("packages") or 1)
        per_package = pieces_per_package(size, line_spec(line).piece_g)
        if "stk" in needs and per_package and size:
            # "2 løg" from a bag sold by weight: a bag holds eight, so one bag.
            needs["g"] = needs.get("g", 0) + needs.pop("stk") / per_package * size[1]
        if size and size[0] in needs and size[1] > 0:
            wanted = math.ceil(needs[size[0]] / size[1] - 0.05)
        elif product and "stk" in needs and (size is None or size[1] >= 300):
            # "2 stk" of something sold by weight (a whole chicken): two of them.
            wanted = math.ceil(needs["stk"])
        elif not product and line.get("unit") in ("g", "ml", "kg", "l") and line.get("amount"):
            base = to_base(float(line["amount"]), line["unit"])
            if base and base[0] in needs and needs[base[0]] > base[1] * 1.05:
                line["amount"] = round(needs[base[0]] / (base[1] / float(line["amount"])), 1)
                changed.append(line["name"])
            continue
        else:
            continue
        wanted = min(wanted, packages * 4)
        if wanted > packages:
            line["packages"] = wanted
            if line.get("buy_at") and line.get("chain_price") is not None:
                line["cost"] = round(wanted * float(line["chain_price"]), 2)
            elif product.get("price"):
                line["cost"] = round(wanted * float(product["price"]), 2)
            changed.append(line["name"])
    if changed:
        plan["total"] = plan_total(plan["shopping"])
    return changed


def own_shopping(plan: dict[str, Any], day: dict[str, Any]) -> list[dict[str, Any]]:
    """The shopping lines only this dish uses (named in its uses, in no other's)."""
    others = {
        name.lower()
        for other in plan["days"]
        if other is not day and is_cooked(other)
        for name in other.get("uses") or []
    }
    mine = {name.lower() for name in day.get("uses") or []} - others
    return [
        line
        for line in plan["shopping"]
        if line["name"].lower() in mine and not line.get("must_have") and not line.get("added")
    ]


class AddItems(Protocol):
    """Puts items ({product_id|name, amount}) on the REMA list, telling about each."""

    async def __call__(
        self,
        items: list[dict[str, Any]],
        on_added: Callable[[dict[str, Any]], None] | None = None,
    ) -> None: ...


class MealPlanner(ProductMatcher):
    """Create meal plans with AI and send them to the REMA shopping list."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        client: RemaClient,
        store: RemaPlanStore,
        get_catalogs: Callable[[], tuple[Catalog | None, Catalog | None]],
        add_items: AddItems,
    ) -> None:
        """Initialize the planner."""
        self.hass = hass
        self.entry_id = entry_id
        self.client = client
        self.store = store
        self._get_catalogs = get_catalogs
        self._add_items = add_items
        self._send_lock = asyncio.Lock()
        self.status: dict[str, Any] = {"state": "idle", "message": None, "started": None}
        self._task: asyncio.Task[None] | None = None
        self._auto_attempted: set[str] = set()
        self.mealie = MealieLink(hass)
        self.chains = ChainOffers(hass)
        self.rema_recipes = RemaRecipes(self)
        self.sites = RecipeSites(hass)
        # Bilka ToGo's prices (the shop's own search when the family shops in Bilka).
        self.bilka: BilkaSearch = getattr(client, "bilka", None) or BilkaSearch(hass)
        # Automatic sends waiting for REMA's prices: (plan id, key) -> cancel.
        self._sends: dict[tuple[str, str], Callable[[], None]] = {}
        # While a plan is made: what REMA answered, so the rounds don't search twice.
        self._search_cache: dict[tuple[str, str], list[Product]] | None = None

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
        """The start date of the next plan.

        The family's first weekday, but today while next week's avis isn't out:
        a plan for next week can't be priced yet, the rest of this week can.
        """
        today = dt_util.now().date()
        start = next_start(today, self.store.settings["start_weekday"])
        try:
            self.avis_end(start)
        except ServiceValidationError:
            return today
        return start

    def avis_end(self, start: date) -> date | None:
        """The last day a plan from start can be priced, or None for no limit.

        Raises if start is after every avis that is out: the prices aren't known yet.
        Without any avis known (REMA can't be reached), anything goes, as before.
        """
        known = [
            (c, _local_day(c.valid_from), _local_day(c.valid_to))
            for c in self._get_catalogs()
            if c and c.valid_from and c.valid_to
        ]
        if not known:
            return None
        covering = next((k for k in known if k[1] <= start <= k[2]), None)
        if covering is None:
            last = max(k[2] for k in known)
            if start > last:
                raise _invalid(
                    "avis_not_out",
                    date=f"{start.day}/{start.month}",
                    last=f"{last.day}/{last.month}",
                )
            return None
        end = covering[2]
        # A later avis takes over the day after: the plan can go on into it.
        if any(k[1] <= end + timedelta(days=1) <= k[2] for k in known if k is not covering):
            return None
        return end

    @callback
    def async_start_generation(
        self,
        start: date | None = None,
        send: bool = False,
        skip: set[date] | None = None,
        surprise: bool = False,
        picks: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Start making a plan in the background. Days in skip get no dinner.

        surprise: dishes the family has never had (Overrask os).
        picks: {date: dish} the family chose themselves (from the collection, REMA or Mealie).
        """
        if self.generating:
            raise _invalid("already_generating")
        start = start or self.default_start()
        self.avis_end(start)
        if skip and not plan_dates(start, self.store.settings["days"], skip):
            raise _invalid("all_days_skipped")
        if not self.ai_available():
            self._async_create_ai_issue()
            raise _invalid("no_ai_task")
        self._set_status("generating", "Laver madplan …")
        self._task = self.hass.async_create_background_task(
            self._async_run(start, send, skip or set(), surprise, picks or {}),
            name=f"{DOMAIN} meal plan",
        )

    @callback
    def async_start_update(self, plan_id: str) -> None:
        """Update a plan to the settings as they are now, in the background.

        It starts from the plan the family has: the same first day and skipped
        days, and as many of its dishes as the new settings allow. The plan is
        replaced by the updated one. Not once its shopping has been sent (that
        would buy it twice): then a new plan is made instead.
        """
        if self.generating:
            raise _invalid("already_generating")
        plan = self.store.get_plan(plan_id)
        if plan is None or plan.get("kind") == "freezer":
            raise _invalid("plan_not_found")
        if plan.get("sent_at") or any(line.get("sent") for line in plan.get("shopping") or []):
            raise _invalid("plan_already_sent")
        if not self.ai_available():
            self._async_create_ai_issue()
            raise _invalid("no_ai_task")
        start = date.fromisoformat(plan["start_date"])
        skip = {d for d in (parse_date(v) for v in plan.get("skipped") or []) if d}
        self._set_status("generating", "Opdaterer madplanen …")
        self._task = self.hass.async_create_background_task(
            self._async_run(start, False, skip, bool(plan.get("surprise")), {}, plan_id),
            name=f"{DOMAIN} meal plan update",
        )

    async def _async_run(
        self,
        start: date,
        send: bool,
        skip: set[date],
        surprise: bool = False,
        picks: dict[str, dict[str, Any]] | None = None,
        base_id: str | None = None,
    ) -> None:
        try:
            plan = await self.async_generate(
                start, skip, surprise=surprise, picks=picks, base_id=base_id
            )
            if send:
                await self._async_send_when_ready(plan)
        except Exception as err:
            if getattr(err, "translation_key", "") in ("ai_no_credit", "ai_busy", "ai_key_failed"):
                # Nothing wrong here: the AI service said no (credit, too busy, its key).
                _LOGGER.warning("Could not make a meal plan: %s", err.__cause__ or err)
            else:
                _LOGGER.exception("Could not make a meal plan")
            self._set_status("error", await async_danish(self.hass, err) or err.__class__.__name__)
        else:
            self._set_status("idle")

    def _ai_name(self, entity_id: str | None) -> str | None:
        """The AI's name in Home Assistant (for an error about it)."""
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.name if state is not None else None

    def _ai_entity(self) -> str | None:
        """The AI Task entity to use; None means Home Assistant's preferred one."""
        entity: str | None = self.store.settings.get("ai_task_entity")
        if entity and self.hass.states.get(entity) is not None:
            return entity
        # None lets Home Assistant use its preferred AI task entity; fall back to
        # the first one if no preference is set.
        prefs = self.hass.data.get("ai_task_preferences")
        if prefs is not None and getattr(prefs, "gen_data_entity_id", None):
            return None
        ids = self.hass.states.async_entity_ids("ai_task")
        return ids[0] if ids else entity

    def ai_available(self) -> bool:
        """True if there is an AI Task entity (or a chosen conversation agent) to make plans with."""
        chosen = str(self.store.settings.get("ai_task_entity") or "")
        if chosen.startswith(f"{AGENT_DOMAIN}.") and self.hass.states.get(chosen) is not None:
            return True
        prefs = self.hass.data.get("ai_task_preferences")
        if prefs is not None and getattr(prefs, "gen_data_entity_id", None):
            return True
        return bool(self.hass.states.async_entity_ids("ai_task"))

    @callback
    def _async_create_ai_issue(self) -> None:
        """Tell the user in Repairs that an AI Task is needed."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_NO_AI_TASK,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NO_AI_TASK,
            learn_more_url=AI_TASK_DOCS_URL,
        )

    async def _async_chain_offers(self, dates: list[date]) -> list[tuple[str, str, dict[str, Any]]]:
        """The family's other chains' offers that run during the plan, as (id, chain, offer).

        At most CHAIN_OFFERS_IN_PROMPT in all, shared between the chains, so the
        instructions stay readable.
        """
        chosen = [d for d in self.store.settings["chains"] if d in CHAINS]
        if not chosen:
            return []
        self._set_status("generating", "Henter de andre butikkers tilbud …")
        per_chain = max(20, CHAIN_OFFERS_IN_PROMPT // len(chosen))
        result: list[tuple[str, str, dict[str, Any]]] = []
        for dealer_id in chosen:
            try:
                offers = await self.chains.async_offers(dealer_id)
            except ChainError as err:
                _LOGGER.warning("Could not read %s's offers: %s", CHAINS[dealer_id], err)
                continue
            running = [o for o in offers if any(runs_on(o, d) for d in dates)][:per_chain]
            result += [(f"k{len(result) + i}", dealer_id, o) for i, o in enumerate(running)]
        return result

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

    def ai_task_available(self) -> bool:
        """True if an AI Task (not a conversation agent) is chosen or preferred: it can read photos."""
        chosen = str(self.store.settings.get("ai_task_entity") or "")
        if chosen.startswith(f"{AGENT_DOMAIN}."):
            return False
        prefs = self.hass.data.get("ai_task_preferences")
        if prefs is not None and getattr(prefs, "gen_data_entity_id", None):
            return True
        return bool(self.hass.states.async_entity_ids("ai_task"))

    async def _async_ask_ai(
        self,
        prompt: str,
        task_name: str,
        attachments: list[dict[str, Any]] | None = None,
        structure: Any | None = None,
    ) -> dict[str, Any]:
        """Ask the AI and get its answer as JSON (``structure``: the shape the answer
        must have, when the AI Task entity can be told; a conversation agent can't)."""
        from homeassistant.components.ai_task import async_generate_data  # noqa: PLC0415

        entity_id = self._ai_entity()

        async def ask(instructions: str) -> Any:
            if entity_id and entity_id.startswith(f"{AGENT_DOMAIN}."):
                return await self._async_ask_agent(entity_id, instructions)
            shapes: list[Any] = [structure, None] if structure is not None else [None]
            for shape in shapes:
                try:
                    result = await async_generate_data(
                        self.hass,
                        task_name=task_name,
                        entity_id=entity_id,
                        instructions=instructions,
                        attachments=attachments,
                        structure=shape,
                    )
                except HomeAssistantError as err:
                    if shape is not None and re.search(
                        r"schema|structure|response_format|json_schema", str(err), re.IGNORECASE
                    ):
                        _LOGGER.debug(
                            "%s can't take a structure (%s); asking freely", entity_id, err
                        )
                        continue  # once more without the shape
                    if "MAX_TOKENS" in str(err).upper():
                        raise _failed("ai_answer_too_long", error=str(err)) from err
                    if (problem := ai_problem(err, self._ai_name(entity_id))) is not None:
                        raise problem from err
                    raise
                return result.data
            raise AssertionError("unreachable")  # pragma: no cover

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
            raise _failed("ai_invalid_json", error=str(err)) from err

    async def _async_ask_agent(self, agent_id: str, instructions: str) -> str:
        """Ask a conversation agent instead of an AI Task: its answer is the reply's text."""
        from homeassistant.components import conversation  # noqa: PLC0415
        from homeassistant.helpers import intent  # noqa: PLC0415

        try:
            result = await conversation.async_converse(
                self.hass,
                instructions,
                None,  # a new conversation each time
                Context(),
                language="da",
                agent_id=agent_id,
            )
        except ValueError as err:  # the agent is gone
            raise HomeAssistantError(str(err)) from err
        response = result.response
        speech = str(response.speech.get("plain", {}).get("speech") or "")
        if response.response_type == intent.IntentResponseType.ERROR:
            error = HomeAssistantError(speech or f"{agent_id} could not answer")
            raise ai_problem(error, self._ai_name(agent_id)) or error
        return speech

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
        if day.get("mealie") and await self._async_mealie_recipe(day):
            return
        own = find_recipe(self.store, day.get("recipe_id"))
        if own and (own["ingredients"] or own["steps"]):
            recipe_to_day(
                own,
                day,
                recipe_factor(
                    {**self.store.settings, "portion_percent": plan.get("portion_percent", 100)},
                    own,
                    day,
                ),
            )
            return
        prompt = build_recipe_prompt(settings=self.store.settings, day=day, plan=plan)
        task = f"REMA 1000 opskrift {day['date']}"
        shape = recipe_structure(schema_library())
        try:
            raw = await self._async_ask_ai(prompt, task, structure=shape)
        except HomeAssistantError as err:
            _LOGGER.warning("Could not write the recipe for %s: %s", day["date"], err)
            day["recipe_error"] = str(err)
            return
        if problems := recipe_problems(raw, self.store.settings):
            # Once more with what was wrong; the better of the two is kept.
            fix = "\n".join(f"- {p}" for p in problems)
            try:
                again = await self._async_ask_ai(
                    f"{prompt}\n\nDin første opskrift havde fejl – ret dem:\n{fix}",
                    task,
                    structure=shape,
                )
            except HomeAssistantError as err:
                _LOGGER.debug("Could not have the recipe for %s put right: %s", day["date"], err)
            else:
                if len(recipe_problems(again, self.store.settings)) < len(problems):
                    raw = again
        cleaned = self._clean_days(
            [{**raw, "date": day["date"]}], [date.fromisoformat(day["date"])]
        )[0]
        day["ingredients"] = cleaned["ingredients"]
        day["steps"] = cleaned["steps"]
        day["tip"] = cleaned["tip"]
        day["nutrition"] = clean_nutrition(raw.get("nutrition"))
        if cleaned["active_minutes"]:
            day["active_minutes"] = cleaned["active_minutes"]
        if cleaned["total_minutes"]:
            day["total_minutes"] = cleaned["total_minutes"]

    async def _async_mealie_recipe(self, day: dict[str, Any]) -> bool:
        """The family's own recipe from Mealie for a day built on it."""
        try:
            recipe = await self.mealie.async_recipe(str(day["mealie"]))
        except MealieError as err:
            _LOGGER.warning("Could not read %s from Mealie: %s", day["mealie"], err)
            return False
        if not recipe["ingredients"] and not recipe["steps"]:
            return False
        day["ingredients"] = [{"name": text, "amount": ""} for text in recipe["ingredients"]]
        day["steps"] = [{"text": text, "minutes": 0} for text in recipe["steps"]]
        day["tip"] = recipe["description"]
        day["nutrition"] = None
        day["active_minutes"] = recipe["active_minutes"] or day.get("active_minutes", 0)
        day["total_minutes"] = recipe["total_minutes"] or day.get("total_minutes", 0)
        return True

    async def async_mealie_sync(self, plan: dict[str, Any], force: bool = False) -> int:
        """Put a plan's dinners in Mealie's calendar (when switched on, or asked)."""
        if not force and not (self.store.settings["mealie_calendar"] and self.mealie.available):
            return 0
        try:
            count = await self.mealie.async_sync_calendar(plan)
        except MealieError as err:
            if force:
                raise
            _LOGGER.warning("Could not fill Mealie's calendar: %s", err)
            return 0
        finally:
            await self.store.async_save()
        return count

    async def _async_align_recipes(
        self,
        plan: dict[str, Any],
        offers: list[Offer],
        at: datetime | None,
        late: dict[int, date] | None,
    ) -> None:
        """The shopping list follows the family's own recipes the plan is built on.

        For a day with one of the collection's recipes, every ingredient of the
        recipe (not the basic items) is on the list, and the AI's own idea of the
        dish's items leaves it, in amounts for this household, with the REMA
        product the recipe names when it does. An item two recipes share is
        bought for both.
        """
        settings = {**self.store.settings, "portion_percent": plan.get("portion_percent", 100)}
        pantry = pantry_words(settings["pantry"])
        new_lines: list[dict[str, Any]] = []
        own_all: set[int] = set()  # the AI's lines of the recipe days
        kept_all: set[int] = set()  # ... that a recipe uses after all
        for day in plan["days"]:
            recipe = find_recipe(self.store, day.get("recipe_id")) if is_cooked(day) else None
            if recipe is None or not recipe["ingredients"]:
                continue
            factor = recipe_factor(settings, recipe, day)
            own = own_shopping(plan, day)
            own_all |= {id(line) for line in own}
            uses: list[str] = []
            for ingredient in recipe["ingredients"]:
                if is_tap_water(ingredient["name"]):
                    continue
                if ingredient.get("basic") or any(
                    _uses_item(item, ingredient["name"]) for item in pantry
                ):
                    continue
                # The dish's own line first, then any line on the list.
                line = next(
                    (
                        existing
                        for existing in [*own, *plan["shopping"]]
                        if not existing.get("must_have") and _names_match(existing, ingredient)
                    ),
                    None,
                )
                if line is None:
                    line = recipe_line(ingredient, factor)
                    if line is None:
                        continue  # a heading, equipment or water: nothing to buy
                    plan["shopping"].append(line)
                    new_lines.append(line)
                elif line.get("recipe") and line["name"] not in uses:
                    # Another recipe day made this line: this day needs its share too.
                    more = recipe_line(ingredient, factor)
                    if more is None:
                        continue
                    if more.get("stock_cubes") and line.get("stock_cubes"):
                        line["amount"] = max(line.get("amount") or 1, more["amount"])
                    elif more["unit"] == line["unit"]:
                        line["amount"] = (line.get("amount") or 0) + more["amount"]
                    else:
                        line = more
                        plan["shopping"].append(line)
                        new_lines.append(line)
                kept_all.add(id(line))
                if line["name"] not in uses:
                    uses.append(line["name"])
            day["uses"] = uses
        drop = own_all - kept_all
        if drop:
            plan["shopping"] = [
                line
                for line in plan["shopping"]
                if id(line) not in drop or line.get("must_have") or line.get("added")
            ]
        if new_lines:
            await self._async_price_lines(new_lines, offers, at, late)
        plan["total"] = plan_total(plan["shopping"])

    async def _async_recipe_extras(
        self,
        plan: dict[str, Any],
        offers: list[Offer],
        at: datetime | None,
        late: dict[int, date] | None,
    ) -> None:
        """What an AI recipe uses that isn't on the list (the herbs, a spice) goes on it.

        A few items a day at most; basic items and what the list has under another
        name ("hakkede tomater på dåse" is the line "Hakkede tomater") are left out.
        """
        pantry = pantry_words(self.store.settings["pantry"])
        new_lines: list[dict[str, Any]] = []
        for day in plan["days"]:
            if (
                not is_cooked(day)
                or day.get("recipe_id")
                or day.get("mealie")
                or day.get("recipe_error")
                or fixed_day_text(self.store.settings, day)  # the family's own simple dish
            ):
                continue
            added = 0
            for ingredient in day.get("ingredients") or []:
                name = str(ingredient.get("name") or "").strip()
                if is_tap_water(name):
                    continue
                head = head_word(name)
                if not head or added >= RECIPE_EXTRAS_PER_DAY:
                    continue
                if food_conflicts([name], self.store.settings):
                    continue  # the AI slipped: not bought for the family
                if any(_uses_item(item, name) or _uses_item(item, head) for item in pantry):
                    continue
                if any(
                    _names_match(line, {"name": head}) or _names_match(line, ingredient)
                    for line in plan["shopping"]
                ):
                    continue
                line = recipe_line(ingredient)
                if line is None:
                    continue
                plan["shopping"].append(line)
                new_lines.append(line)
                day.setdefault("uses", []).append(line["name"])
                added += 1
        if new_lines:
            await self._async_price_lines(new_lines, offers, at, late)
            plan["total"] = plan_total(plan["shopping"])

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
        day: dict[str, Any] | None = (
            next((d for d in plan["days"] if d["date"] == day_date), None) if plan else None
        )
        if plan is None or day is None:
            raise _invalid("day_not_found")
        await self._async_recipe(day, plan)
        fit_amounts(plan)
        await self.store.async_save()
        self._notify()
        if day.get("recipe_error"):
            raise _failed("recipe_failed", error=str(day["recipe_error"]))
        return day

    async def async_generate(
        self,
        start: date,
        skip: set[date] | None = None,
        *,
        surprise: bool = False,
        picks: dict[str, dict[str, Any]] | None = None,
        base_id: str | None = None,
    ) -> dict[str, Any]:
        """Make, price and store a plan. Returns the plan.

        picks: dishes the family chose for a day themselves - the AI plans around
        them, and their own recipe is put on the day afterwards.
        base_id: update this plan to the settings now instead (it is replaced).
        """
        base = self.store.get_plan(base_id) if base_id else None
        settings = self.store.settings
        dates = plan_dates(start, settings["days"], skip)
        # Not past the last avis that is out: those days' prices aren't known yet.
        end = self.avis_end(start)
        if end is not None:
            dates = [d for d in dates if d <= end]
        if not dates:
            raise _invalid("all_days_skipped")
        skipped = sorted(
            d for d in (skip or set()) if start <= d < start + timedelta(settings["days"])
        )
        # Fewer days to cook: no more leftover or vegetarian days than there is room for.
        settings = {
            **settings,
            "leftover_days": min(
                settings["leftover_days"],
                (len(dates) - 1) // 2,
                sum(1 for d in dates[1:] if d.weekday() not in no_leftover_weekdays(settings)),
            ),
            "min_vegetarian": min(settings["min_vegetarian"], len(dates)),
            "max_vegetarian": min(settings["max_vegetarian"], len(dates)),
        }
        # With a monthly food budget, the plan may cost what is left of its week.
        if (left := plan_budget(self.store, dates[0])) is not None:
            settings["budget"] = left
        self._set_status("generating", "Henter ugens tilbud …")
        catalog, offers = await self._async_offers(start)
        late = late_offers(offers, dates[0])
        chain_offers = await self._async_chain_offers(dates) if settings["plan_all_chains"] else []
        recent = self.store.recent_dishes(start, settings["no_repeat_weeks"])
        due, optional = self.store.favorites_due(start, recent)
        # An update keeps the wishes the plan was made with.
        note = str(base.get("note") or "").strip() if base else self.store.note.strip()
        own = [] if surprise else prompt_recipes(self.store, recent)
        # The family's own recipe for a favourite: the plan uses it is.
        links = {
            fav["id"]: recipe
            for fav in [*due, *optional]
            if (recipe := favorite_recipe(self.store, fav["text"])) is not None
        }
        disliked = disliked_names(self.store)
        web = (
            []
            if surprise or not settings["recipe_sites_in_plan"]
            else await self._async_site_recipes(settings["recipe_sites"], offers)
        )
        iso = [d.isoformat() for d in dates]
        picks = {
            day: pick for day, pick in (picks or {}).items() if day in iso and pick.get("dish")
        }
        # The dishes asked for on a day: in the wishes ("frikadeller onsdag"), or chosen.
        wishes = {**day_wishes(note, iso), **{day: p["dish"] for day, p in picks.items()}}
        mealie: list[dict[str, Any]] = []
        if settings["mealie_recipes"] and self.mealie.available and not surprise:
            self._set_status("generating", "Henter jeres opskrifter fra Mealie …")
            try:
                mealie = await self.mealie.async_prompt_recipes(recent)
            except MealieError as err:
                _LOGGER.warning("Could not read the recipes in Mealie: %s", err)

        feedback: str | None = None
        if base is not None:
            feedback = update_feedback(
                base,
                iso,
                check_plan(
                    {**base, "days": [d for d in base.get("days", []) if d["date"] in iso]},
                    settings,
                    recent=recent,
                    due_ids=set() if surprise else {f["id"] for f in due},
                    note=note,
                    disliked=disliked,
                    wishes=wishes,
                ),
            )
        self._search_cache = {}
        try:
            best = await self._async_generate_rounds(
                settings=settings, dates=dates, catalog=catalog, offers=offers, due=due,
                optional=optional, recent=recent, feedback=feedback, skipped=skipped, note=note,
                late=late, mealie=mealie, own=own, disliked=disliked, surprise=surprise,
                links=links, wishes=wishes, web=web, chain_offers=chain_offers, start=start,
            )  # fmt: skip
        finally:
            self._search_cache = None
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_NO_AI_TASK)
        # A recipe from the sites that the AI chose goes in the collection, as the family's.
        # One the family already has (and may have changed) is used as it is.
        chosen: dict[str, Any] = {r["id"]: r for r in web}
        for day in best["days"]:
            web_id = day.get("recipe_id")
            if (recipe := chosen.get(web_id)) is None:
                continue
            saved = next(
                (r for r in self.store.recipes if r.get("url") and r["url"] == recipe.get("url")),
                None,
            ) or await async_save_recipe(self.store, {**recipe, "id": None})
            chosen[web_id] = saved
            day["recipe_id"] = saved["id"]
        problems = best.pop("problems")
        best["checklist"] += [{"requirement": p, "ok": False} for p in problems]
        if problems:
            _LOGGER.info("The plan still breaks %d rule(s): %s", len(problems), "; ".join(problems))
        best["budget"] = settings["budget"]
        best["skipped"] = [d.isoformat() for d in skipped]
        best["note"] = note
        best["surprise"] = surprise
        await self._async_align_recipes(best, offers, self.price_time(start), late)
        best["over_budget"] = bool(settings["budget"]) and best["total"] > settings["budget"]
        await self._async_add_recipes(best)
        await self._async_recipe_extras(best, offers, self.price_time(start), late)
        fit_amounts(best)
        await self._async_ai_choices(best)
        await self._async_next_shops(best)
        best["over_budget"] = bool(settings["budget"]) and best["total"] > settings["budget"]
        mark_planned(self.store, best)
        if base is not None:
            # The updated plan takes the old one's place (it was never sent).
            best["updated_from"] = base["id"]
            await self.store.async_delete_plan(base["id"])
        await self.store.async_add_plan(best)
        self._schedule_refreshes(best)
        await self.async_mealie_sync(best)
        if note and self.store.note.strip() == note:
            # The wishes are for this plan only (unless changed meanwhile).
            await self.store.async_set_note("")
        if picks:
            best = await self._async_put_picks(best, picks)
        self._notify()
        return best

    async def _async_generate_rounds(
        self,
        *,
        settings: dict[str, Any],
        dates: list[date],
        catalog: Catalog | None,
        offers: list[Offer],
        due: list[dict[str, Any]],
        optional: list[dict[str, Any]],
        recent: list[str],
        feedback: str | None,
        skipped: list[date],
        note: str,
        late: dict[int, date],
        mealie: list[dict[str, Any]],
        own: list[dict[str, Any]],
        disliked: list[str],
        surprise: bool,
        links: dict[str, dict[str, Any]],
        wishes: dict[str, str],
        web: list[dict[str, Any]],
        chain_offers: list[tuple[str, str, dict[str, Any]]],
        start: date,
    ) -> dict[str, Any]:
        """Ask the AI for a plan, check it, and ask again with what was wrong, up to
        MAX_AI_ROUNDS times. The best try is returned (fewest broken rules, then
        least over budget, then cheapest).

        The rules are checked before the list is priced, so a try that breaks
        more rules than the best so far costs no searches; and if the AI fails
        on a later round, the best so far stands.
        """
        best: dict[str, Any] | None = None
        for attempt in range(MAX_AI_ROUNDS):
            self._set_status(
                "generating",
                "AI'en laver madplanen …"
                if attempt == 0
                else f"Planen brød et krav – AI'en retter den ({attempt + 1}/{MAX_AI_ROUNDS}) …",
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
                skipped=skipped,
                note=note or None,
                late=late,
                mealie=mealie,
                own=own,
                disliked=disliked,
                surprise=surprise,
                favorite_recipes=links,
                wishes=wishes,
                web=web,
                shop=self.shop,
                prices=self.prices,
                chain_offers=chain_offers,
            )
            try:
                raw = await self._async_ask_ai(
                    prompt, "REMA 1000 madplan", structure=plan_structure(schema_library())
                )
            except HomeAssistantError as err:
                if best is None:
                    raise
                _LOGGER.warning(
                    "The AI could not put the plan right (%s); keeping the best try", err
                )
                break
            plan = await self._async_build_plan(
                raw, dates, catalog, offers, self.price_time(start), late, chain_offers, price=False
            )
            known = {r["slug"] for r in mealie}
            ours = (
                {r["id"] for r in own} | {r["id"] for r in links.values()} | {r["id"] for r in web}
            )
            for day in plan["days"]:
                if day.get("mealie") not in known:
                    day["mealie"] = None  # not one of the family's recipes
                if day.get("recipe_id") not in ours:
                    day["recipe_id"] = None
            if not surprise:  # a surprise is not one of the family's own dishes
                link_favorites(plan, [*due, *optional], links, self.store)
            # The AI is not trusted to keep the rules: the plan is checked, and the
            # AI is told what to put right. The best of the tries is kept.
            problems = check_plan(
                plan,
                settings,
                recent=recent,
                due_ids=set() if surprise else {f["id"] for f in due},
                note=note,
                disliked=disliked,
                wishes=wishes,
            )
            plan["problems"] = problems
            if best is not None and len(problems) > len(best["problems"]):
                # Worse than what we have: not worth pricing, just tell the AI.
                over = 0.0
            else:
                self._set_status(
                    "generating",
                    f"Finder varer og priser i {self.shop} …"
                    if self.prices
                    else "Laver indkøbslisten med ugens tilbud …",
                )
                await self._async_price_plan(
                    plan, offers, self.price_time(start), late, chain_offers
                )
                # Without prices (another shop than REMA) the total is only the offers.
                budget = settings["budget"] if self.prices else 0
                over = max(0.0, plan["total"] - budget) if budget else 0.0
                if best is None or (len(problems), over, plan["total"]) < (
                    len(best["problems"]),
                    max(0.0, best["total"] - budget) if budget else 0.0,
                    best["total"],
                ):
                    best = plan
                if not problems and not over:
                    break
            lines = [f"- {p}" for p in problems]
            if over:
                expensive = sorted(
                    (line for line in plan["shopping"] if line.get("cost")),
                    key=lambda line: line["cost"],
                    reverse=True,
                )[:6]
                fixed_cost = sum(
                    float(line.get("cost") or 0)
                    for line in plan["shopping"]
                    if line.get("must_have")
                )
                lines.append(
                    f"- Indkøbslisten kostede {plan['total']:.0f} kr., men budgettet er "
                    f"{settings['budget']} kr."
                    + (
                        f" Heraf er {fixed_cost:.0f} kr. faste ugevarer, som du ikke kan ændre, "
                        f"så retternes varer må højst koste {settings['budget'] - fixed_cost:.0f} kr."
                        if fixed_cost
                        else ""
                    )
                    + " Dyreste varer: "
                    + ", ".join(
                        f"{line['name']} ({line['cost']:.0f} kr.)"
                        for line in expensive
                        if not line.get("must_have")
                    )
                    + ". Vælg billigere retter og flere tilbudsvarer."
                )
            previous = "; ".join(
                f"{d['weekday']} {d['date']}: {d['dish']}"
                + (" (rester)" if d.get("uses_leftovers_from") else "")
                for d in plan["days"]
            )
            feedback = (
                f"Dit forrige forslag var: {previous}. Det brød disse krav – lav KUN de dage om, "
                "der nævnes her, og behold de øvrige dage og deres varer uændret:\n"
                + "\n".join(lines)
            )
        assert best is not None
        return best

    async def _async_ai_choices(self, plan: dict[str, Any]) -> None:
        """One question to the AI about the lines the matcher is not sure of: which
        of the products found is the ingredient, or none of them. Its pick is a
        better first choice for the family's check; the line stays marked for it.
        """
        unsure = [
            line
            for line in plan["shopping"]
            if needs_review(line) and line.get("alternatives") and not line.get("product_id")
        ]
        if not unsure or not self.ai_available():
            return
        options: dict[str, dict[int, dict[str, Any]]] = {}
        rows: list[str] = []
        for line in unsure:
            found = [line["product"]] if line.get("product") else []
            found += [a for a in line["alternatives"] if a["id"] not in {p["id"] for p in found}]
            options[line["id"]] = {int(p["id"]): p for p in found[:6]}
            need = (
                f" ({line['amount']:g} {line['unit']})"
                if line.get("amount") and line.get("unit") and line["unit"] != "pk"
                else ""
            )
            rows.append(
                f"{line['id']} | {line['name']}{need} | "
                + "; ".join(
                    f"{pid}: {p['name']}"
                    + (
                        f" ({str(p['underline']).split('/')[0].strip()})"
                        if p.get("underline")
                        else ""
                    )
                    for pid, p in options[line["id"]].items()
                )
            )
        prompt = "\n".join(
            [
                "Du hjælper en dansk familie med indkøb i REMA 1000. For hver ingrediens fra deres "
                "madplan står de varer, butikkens søgning fandt. Vælg den vare, der ER ingrediensen "
                "til en ret: den rigtige slags (fersk kød, ikke pålæg; frisk peberfrugt, ikke "
                "strimler på dåse; nudler, ikke cupnudler; almindelig størrelse), ikke en "
                "færdigret, en sauce eller noget med smag af ingrediensen. Er ingen af varerne "
                "ingrediensen, så svar null for den. Svar for alle linjer.",
                "",
                "linje-id | ingrediens | varer (vare-id: navn (størrelse)):",
                *rows,
                "",
                "SVARFORMAT: kun gyldig JSON, præcis sådan:",
                json.dumps(
                    {"choices": [{"line": unsure[0]["id"], "product": None}]}, ensure_ascii=False
                ),
            ]
        )
        try:
            raw = await self._async_ask_ai(
                prompt, "REMA 1000 varevalg", structure=choices_structure(schema_library())
            )
        except HomeAssistantError as err:
            _LOGGER.debug("The AI could not help choose products: %s", err)
            return
        picks = {
            str(c.get("line")): c.get("product")
            for c in raw.get("choices") or []
            if isinstance(c, dict)
        }
        by_id = {line["id"]: line for line in unsure}
        for line_id, pick in picks.items():
            line = by_id.get(line_id)
            if line is None:
                continue
            current = (line.get("product") or {}).get("id")
            if pick is None or not isinstance(pick, int):
                if current is not None:
                    line["confidence"] = "low"
                    line["note"] = "AI'en mener ikke, nogen af varerne passer – tjek den"
                continue
            if pick not in options[line_id] or pick == current:
                if pick == current and line.get("confidence") == "low":
                    line["confidence"] = "medium"
                continue
            try:
                products = await self.client.async_get_products([pick])
            except RemaError:
                continue
            product = next((p for p in products if p.id == pick and p.price), None)
            if product is None:
                continue
            spec = line_spec(line)
            self._apply(
                line,
                product,
                line_packages(line, product, spec.piece_g),
            )
            line["confidence"] = "medium"
            line["note"] = "AI'en valgte denne blandt mulighederne – tjek den"
            line["alternatives"] = [a for a in line["alternatives"] if a["id"] != pick] + (
                [_alternative_from(options[line_id][current])]
                if current in options[line_id]
                else []
            )
        plan["total"] = plan_total(plan["shopping"])

    async def _async_site_recipes(
        self, site_ids: list[str], offers: list[Offer]
    ) -> list[dict[str, Any]]:
        """Recipes from the family's sites for the week's main offers, for the AI to use."""
        if not site_ids:
            return []
        words: list[str] = []
        for offer in offers:
            heading = offer.heading.lower()
            for word in SITE_WORDS:
                if word in heading and word not in words:
                    words.append(word)
        self._set_status("generating", "Finder opskrifter på jeres madsider …")
        try:
            recipes = await self.sites.async_candidates(site_ids, words[:5] or ["aftensmad"])
        except Exception as err:
            _LOGGER.warning("Could not read the recipe sites: %s", err)
            return []
        return [{**r, "id": f"web{i}"} for i, r in enumerate(recipes, 1)]

    async def _async_put_picks(
        self, plan: dict[str, Any], picks: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Put the dishes the family chose on their days, with their own recipes."""
        from .planedit import async_swap_dish  # noqa: PLC0415 - planedit imports this module

        for day, pick in sorted(picks.items()):
            self._set_status("generating", f"Sætter {pick['dish']} på madplanen …")
            option: dict[str, Any] = {"dish": pick["dish"], "type": pick.get("type") or "normal"}
            try:
                if pick.get("source") == "rema" and pick.get("slug"):
                    saved = await async_save_recipe(
                        self.store, await self.rema_recipes.async_get(str(pick["slug"]))
                    )
                    option.update(dish=saved["name"], type=saved["type"], recipe_id=saved["id"])
                elif pick.get("source") == "web" and pick.get("url"):
                    recipe = await self.sites.async_recipe(
                        str(pick["url"]), lambda page: async_extract(self, page)
                    )
                    if recipe is None:
                        raise _invalid("recipe_not_on_page")
                    saved = await async_save_recipe(self.store, recipe)
                    option.update(dish=saved["name"], type=saved["type"], recipe_id=saved["id"])
                elif pick.get("source") == "mealie" and pick.get("slug"):
                    option["mealie"] = str(pick["slug"])
                elif pick.get("recipe_id"):
                    option["recipe_id"] = str(pick["recipe_id"])
                plan = await async_swap_dish(self, plan["id"], day, option)
            except (HomeAssistantError, RemaError) as err:
                _LOGGER.warning("Could not put %s on %s: %s", pick["dish"], day, err)
        return plan

    async def _async_build_plan(
        self,
        raw: dict[str, Any],
        dates: list[date],
        catalog: Catalog | None,
        offers: list[Offer],
        at: datetime | None = None,
        late: dict[int, date] | None = None,
        chain_offers: list[tuple[str, str, dict[str, Any]]] | None = None,
        price: bool = True,
    ) -> dict[str, Any]:
        """The plan from the AI's answer: its days and shopping lines, cleaned,
        merged and (unless ``price`` is False, for a plan that is checked first)
        with REMA's products and prices on the lines."""
        settings = self.store.settings
        days = self._clean_days(raw.get("days") or [], dates)
        cleaned = [(item, self._clean_line(item)) for item in raw.get("shopping") or []]
        shopping = merge_lines(
            [line for _item, line in cleaned if line],
            days,
            {
                str(item.get("name") or "").strip().lower(): line["name"]
                for item, line in cleaned
                if line and isinstance(item, dict)
            },
        )
        factor = settings.get("portion_percent", 100) / 100
        if factor != 1:
            for line in shopping:
                if line.get("amount") and not line.get("stock_cubes"):
                    line["amount"] = round(line["amount"] * factor, 2)
            for day in days:
                day["servings"] = math.ceil(day["servings"] * factor)
                day["ingredients"] = [
                    {**item, "amount": scale_amount(item.get("amount") or "", factor)}
                    for item in day["ingredients"]
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
        plan = {
            "id": uuid.uuid4().hex[:12],
            "created": dt_util.now().isoformat(),
            "start_date": dates[0].isoformat(),
            "end_date": dates[-1].isoformat(),
            "week": plan_week(dates),
            "status": "draft",
            "sent_at": None,
            "title": plan_title(dates),
            "summary": str(raw.get("summary") or "")[:2000],
            "days": days,
            "shopping": shopping,
            "portion_percent": settings.get("portion_percent", 100),
            "checklist": [
                {"requirement": str(c.get("requirement") or "")[:300], "ok": bool(c.get("ok"))}
                for c in raw.get("checklist") or []
                if isinstance(c, dict)
            ],
            "deviations": str(raw.get("deviations") or "")[:2000],
            "total": 0.0,
            "budget": settings["budget"],
            "catalog": {"id": catalog.id, "label": catalog.label} if catalog else None,
            "ai_entity": self._ai_entity(),
        }
        if price:
            await self._async_price_plan(plan, offers, at, late, chain_offers)
        return plan

    async def _async_price_plan(
        self,
        plan: dict[str, Any],
        offers: list[Offer],
        at: datetime | None,
        late: dict[int, date] | None,
        chain_offers: list[tuple[str, str, dict[str, Any]]] | None,
    ) -> None:
        """Put REMA's products and prices on a plan's lines, and the other chains' offers."""
        await self._async_price_lines(plan["shopping"], offers, at, late)
        apply_chain_offers(plan["shopping"], chain_offers or [])
        plan["total"] = plan_total(plan["shopping"])

    async def _async_price_lines(
        self,
        shopping: list[dict[str, Any]],
        offers: list[Offer],
        at: datetime | None = None,
        late: dict[int, date] | None = None,
    ) -> None:
        """Find and price REMA products for shopping lines (offers as "o<index>")."""
        settings = self.store.settings
        offer_names = {f"o{i}": offer.heading for i, offer in enumerate(offers)}
        by_id = {f"o{i}": offer for i, offer in enumerate(offers)}
        late_days = {f"o{i}": day for i, day in (late or {}).items()}
        for line in shopping:
            offer_id = str(line.get("offer") or "")
            line["offer_name"] = offer_names.get(offer_id)
            # A thursday offer is bought (and priced) on its first day.
            day = late_days.get(offer_id) if settings["shop_late_week"] else None
            line["buy_from"] = day.isoformat() if day else None

        # Which of REMA's products the offers the dishes are built on are for.
        used = {str(line.get("offer") or "") for line in shopping} & by_id.keys()
        try:
            looked_up = await self.client.async_get_offer_products([by_id[o] for o in used])
        except RemaError as err:
            _LOGGER.debug("Could not look up the offers' products: %s", err)
        else:
            by_id |= {
                key: offer for key in used for offer in looked_up if offer.id == by_id[key].id
            }

        semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY)

        async def match(line: dict[str, Any]) -> None:
            offer = by_id.get(str(line.get("offer") or ""))
            async with semaphore:
                await self._async_match_on_day(line, at, offer)

        await asyncio.gather(*(match(line) for line in shopping))

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
                    "mealie": str(day["mealie"])[:200] if day.get("mealie") else None,
                    "recipe_id": str(day["recipe_id"])[:40] if day.get("recipe_id") else None,
                    # The shopping list's items for this dish (from the overview).
                    "uses": [
                        str(name).strip()[:200]
                        for name in (day.get("uses") or [])[:30]
                        if isinstance(name, str) and name.strip()
                    ]
                    if isinstance(day.get("uses"), list)
                    else [],
                }
            )
        return days

    @staticmethod
    def _clean_line(item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict) or not item.get("name"):
            return None
        raw = str(item["name"]).strip()[:200]
        if is_tap_water(raw):
            return None
        name = ingredient_name(raw)
        if not name:
            return None
        line = {
            "name": name,
            "amount": _num(item.get("amount")),
            "unit": str(item.get("unit") or "").strip().lower()[:10] or None,
            "search": ingredient_name(str(item.get("search") or name))[:80] or name[:80],
            "category": str(item.get("category") or "Andet")[:40],
            "offer": item.get("offer") or None,
            "must_have": False,
            "product_id": None,
        }
        if query := stock_cubes(name):
            line.update(
                name=query[:1].upper() + query[1:],
                search=query,
                amount=1,
                unit="pk",
                stock_cubes=True,
            )
        spec = spec_for(raw, str(line["search"]), str(line["category"]), item.get("key"))
        if not apply_spec(line, spec):
            return None
        if spec.entry is not None and spec.entry is catalogue_entry(item.get("key")):
            # The AI's catalogue key, kept for matching the line again; and whether
            # only the AI says so (the search term is the key's from now on).
            line["catalog"] = spec.entry.key
            if spec.guessed:
                line["guessed"] = True
        return line

    # ------------------------------------------------------------- sending

    async def async_quick_add(self, text: str) -> dict[str, Any]:
        """Add something typed by a person: a matching REMA product, else free text."""
        amount, name = parse_quick_add(text)
        if not name:
            raise _invalid("empty_quick_add")
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

    async def async_send(
        self,
        plan_id: str | None = None,
        part: str = "main",
        line_id: str | None = None,
        strict: bool = True,
    ) -> dict[str, Any]:
        """Put a plan's shopping list on the primary REMA list.

        part: "main" (bought on the shopping day), "late" (the items for later
        in the week, e.g. thursday offers) or "all". line_id: just that line.
        strict: with the setting "review", refuse while uncertain lines wait
        to be looked at (a send nobody is watching goes without them instead).

        One send at a time. Each line is marked sent the moment its item is on
        the REMA list, so if REMA fails halfway, the next send only sends the rest.
        """
        async with self._send_lock:
            return await self._async_send(plan_id, part, line_id, strict)

    async def _async_send(
        self, plan_id: str | None, part: str, line_id: str | None = None, strict: bool = True
    ) -> dict[str, Any]:
        plan = self.store.get_plan(plan_id) if plan_id else self.store.latest_plan
        if plan is None:
            raise _invalid("no_plan" if not plan_id else "plan_not_found")
        if plan.get("kind") == "freezer":
            plan["portions_locked"] = True
            await self.store.async_save()
        lines = [
            line
            for line in plan["shopping"]
            if (
                line.get("id") == line_id
                if line_id
                else part == "all" or bool(line.get("buy_from")) == (part == "late")
            )
            and not line.get("buy_at")  # bought in another shop
            and not line.get("sent")  # already in the REMA app
        ]
        if line_id and not lines:
            raise _invalid("line_not_found")
        lines = [line for line in lines if not line.get("skipped") or line_id]
        if not line_id:
            # The lines the family should look at first: by their setting, the
            # send waits for that, or goes without them.
            unsure = [line for line in lines if needs_review(line)]
            mode = self.store.settings["uncertain_items"]
            if unsure and mode == "review" and strict:
                count = f"{len(unsure)} vare" if len(unsure) == 1 else f"{len(unsure)} varer"
                raise _invalid("review_needed", count=count)
            if unsure and mode in ("review", "skip"):
                lines = [line for line in lines if line not in unsure]
        cart = getattr(self.client, "cart", None)
        if cart is not None and plan.get("bilka_rematch"):
            for line in lines:
                if line.get("bilka_price_store") == cart.store_id:
                    continue
                product = line.get("product") or {}
                # A product explicitly chosen in the current store is already valid.
                if not product or not self.bilka.known([product["id"]]):
                    for key in ("product_id", "offer", "offer_name", "price_source"):
                        line.pop(key, None)
                    await self._async_match(line)
                line["bilka_price_store"] = cart.store_id
            await self.store.async_save()
        # The offers' products and prices as REMA has them now (once they run).
        try:
            await self._async_refresh_lines(plan, lines)
        except RemaError as err:
            _LOGGER.debug("Could not look at the offers again before sending: %s", err)
        await asyncio.gather(*(self._async_resolve_avis_item(line) for line in lines))
        plan["total"] = plan_total(plan["shopping"])
        missing: list[dict[str, Any]] = []
        if cart is not None:
            missing = [
                {
                    "id": line["id"],
                    "name": line["name"],
                    "amount": line.get("amount"),
                    "unit": line.get("unit"),
                }
                for line in lines
                if not line.get("product")
            ]
            # A skipped ingredient stays unsent and editable in Middagsro.
            lines = [line for line in lines if line.get("product")]
            plan["missing_products"] = missing
        pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for line in lines:
            line.pop("on_list", None)
            line.setdefault("id", uuid.uuid4().hex[:8])
            if line.get("product"):
                item = {"product_id": line["product"]["id"], "amount": line["packages"]}
            elif line.get("avis_item"):
                # Only in the shops: the avis's name, as the webshop puts it on.
                item = {"name": line["avis_item"]["name"], "amount": line["packages"]}
            else:
                amount = line.get("amount")
                label = line["name"]
                if amount and line.get("unit") and line["unit"] != "pk":
                    label += f" ({amount:g} {line['unit']})"
                item = {"name": label, "amount": int(line.get("packages") or 1)}
            if getattr(self.client, "cart", None) is not None:
                item["transfer_id"] = (
                    f"{plan['id']}:{line['id']}:{plan.get('transfer_revision', 0)}"
                )
            pairs.append((line, item))
        if self.store.settings["must_haves_once"] and not line_id:
            pairs = await self._async_skip_listed(pairs)
        stamp = dt_util.now().isoformat()
        by_item = {id(item): line for line, item in pairs}
        sent: list[str] = []

        def on_added(item: dict[str, Any]) -> None:
            line = by_item[id(item)]
            line["sent"] = stamp
            sent.append(line["id"])

        try:
            if pairs:
                await self._add_items([item for _, item in pairs], on_added)
        except RemaError:
            if sent:  # what got there stays sent; the rest is sent next time
                plan["last_sent"] = {"at": stamp, "ids": sent}
                await self.store.async_save()
                self._notify()
            raise
        # Sent: the lines leave the family's list in the panel (the basket is empty),
        # and the next send only has what was added since. They can be put back.
        if lines:
            for line in lines:
                line["sent"] = stamp
            plan["last_sent"] = {"at": stamp, "ids": [line["id"] for line in lines]}
        if line_id:
            # One item now: the rest of the list is sent as before.
            await self.store.async_save()
            self._notify()
            return plan
        for key in {"main": ("send_at",), "late": ("late_send_at",)}.get(
            part, ("send_at", "late_send_at")
        ):
            plan.pop(key, None)  # sent: nothing left to send automatically
            self._cancel_send(plan["id"], key)
        if missing:
            plan["status"] = "draft"
            await self.store.async_save()
        else:
            await self.store.async_mark_sent(plan["id"], part)
        self._notify()
        return plan

    async def _async_skip_listed(
        self, pairs: list[tuple[dict[str, Any], dict[str, Any]]]
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """Leave out the must-haves that are on the REMA list already (and not bought).

        They count as sent, so they leave the basket here; line["on_list"] says why.
        """
        if not any(line.get("must_have") for line, _ in pairs):
            return pairs
        try:
            shopping_list = await self.client.async_get_primary_list()
        except RemaError as err:
            _LOGGER.debug("The REMA list was not read, every item is sent: %s", err)
            return pairs
        keep = []
        for line, item in pairs:
            existing = (
                shopping_list.find(product_id=item.get("product_id"), name=item.get("name"))
                if line.get("must_have")
                else None
            )
            if existing is not None and not existing.bought:
                line["on_list"] = True
            else:
                keep.append((line, item))
        return keep

    async def async_restore_sent(self, plan_id: str | None = None) -> dict[str, Any]:
        """Put the lines sent last back on the family's list (e.g. the REMA list was lost)."""
        plan = self.store.get_plan(plan_id) if plan_id else self.store.latest_plan
        if plan is None:
            raise _invalid("no_plan" if not plan_id else "plan_not_found")
        last = plan.pop("last_sent", None) or {}
        ids = set(last.get("ids") or [])
        if not ids:
            raise _invalid("nothing_to_restore")
        plan["transfer_revision"] = int(plan.get("transfer_revision", 0)) + 1
        for line in plan["shopping"]:
            if line.get("id") in ids:
                line.pop("sent", None)
                line.pop("on_list", None)
        await self.store.async_save()
        self._notify()
        return plan

    async def _async_resolve_avis_item(self, line: dict[str, Any]) -> None:
        """An avis item REMA didn't have when the plan was made: REMA's product now.

        From 02:00 on an offer's first day REMA has its products (unless it is
        a partivare, only sold in the shops); then the line gets the real
        product, at REMA's price. Otherwise it stays free text.
        """
        item = line.get("avis_item")
        if line.get("product") or not item or not item.get("product_ids"):
            return
        try:
            products = await self.client.async_get_products(list(item["product_ids"]))
        except RemaError as err:
            _LOGGER.debug("Could not look up %s: %s", item["name"], err)
            return
        candidates: list[Product] = []
        for text in (line["search"], line["name"], item["name"]):
            candidates, _penalty = self._candidates(line, products, text, limit=len(products))
            if candidates:
                break
        if not candidates:
            return

        def cost(product: Product) -> float:
            return packages_needed(line.get("amount"), line.get("unit"), product) * (
                product.price or 0
            )

        chosen = min(candidates, key=cost)
        self._apply(line, chosen, packages_needed(line.get("amount"), line.get("unit"), chosen))
        line["note"] = None
        line.pop("price_source", None)  # REMA's own price now

    async def async_refresh_offers(self, plan_id: str, part: str = "all") -> dict[str, Any]:
        """Match a plan's offer items again, now REMA has the offers' products and prices.

        A plan is made from the avis days before it starts; REMA gets the
        offers' products and prices at 02:00 on their first day (a new product
        like the 600 g salmon fillet only appears then). Items whose offer has
        not started yet are left as they are.
        """
        plan = self.store.get_plan(plan_id)
        if plan is None:
            raise _invalid("plan_not_found")
        lines = [
            line
            for line in plan["shopping"]
            if part == "all" or bool(line.get("buy_from")) == (part == "late")
        ]
        await self._async_refresh_lines(plan, lines)
        await self.store.async_save()
        self._notify()
        return plan

    async def async_rematch_missing(self, plan_id: str) -> dict[str, Any]:
        """Retry only unresolved, unsent recipe lines; preserve transfer identities."""
        async with self._send_lock:
            plan = self.store.get_plan(plan_id)
            if plan is None:
                raise _invalid("plan_not_found")
            for line in plan["shopping"]:
                if any(
                    line.get(key)
                    for key in ("product", "sent", "product_id", "added", "buy_at", "skipped")
                ):
                    continue
                candidate = dict(line)
                candidate["name"] = ingredient_name(line["name"])
                candidate["search"] = ingredient_name(line["search"])
                await self._async_match(candidate)
                line.update(candidate)
            plan["total"] = plan_total(plan["shopping"])
            missing = {
                line["id"]
                for line in plan["shopping"]
                if not line.get("product") and not line.get("sent")
            }
            if "missing_products" in plan:
                plan["missing_products"] = [
                    item for item in plan["missing_products"] if item["id"] in missing
                ]
            await self.store.async_save()
            self._notify()
            return plan

    async def _async_refresh_lines(self, plan: dict[str, Any], lines: list[dict[str, Any]]) -> None:
        now = dt_util.utcnow()
        due = [
            line
            for line in lines
            if line.get("offer_name")
            and not line.get("must_have")
            and not line.get("added")
            and not line.get("product_id")
            and not line.get("buy_at")
            and prices_from(date.fromisoformat(line.get("buy_from") or plan["start_date"])) <= now
        ]
        catalog_id = (plan.get("catalog") or {}).get("id")
        if not due or not catalog_id:
            return
        offers = await self.client.async_get_offers(catalog_id)
        by_heading = {
            offer.heading: offer
            for offer in await self.client.async_get_offer_products(
                [o for o in offers if o.heading in {line["offer_name"] for line in due}]
            )
        }
        semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY)

        async def refresh(line: dict[str, Any]) -> None:
            offer = by_heading.get(line["offer_name"])
            if offer is None:
                return  # not in the avis any more: leave it
            async with semaphore:
                await self._async_match(line, None, offer)
            self._avis_price(line, offer)

        await asyncio.gather(*(refresh(line) for line in due))
        plan["total"] = plan_total(plan["shopping"])
        plan["refreshed_at"] = now.isoformat()

    @callback
    def _schedule_refreshes(self, plan: dict[str, Any]) -> None:
        """Look at the plan's offers again at 02:00 on the shopping day (and thursday)."""
        now = dt_util.utcnow()
        main_at = prices_from(date.fromisoformat(plan["start_date"]))
        if main_at > now:
            plan["refresh_at"] = main_at.isoformat()
            self._schedule_send(plan, "refresh_at")
        late = sorted(line["buy_from"] for line in plan["shopping"] if line.get("buy_from"))
        if late and prices_from(date.fromisoformat(late[0])) > now:
            plan["late_refresh_at"] = prices_from(date.fromisoformat(late[0])).isoformat()
            self._schedule_send(plan, "late_refresh_at")

    @callback
    def async_restore_sends(self) -> None:
        """Schedule the automatic sends and refreshes that were waiting (after a restart)."""
        for plan in self.store.plans:
            if plan.get("send_at") and plan.get("status") != "sent":
                self._schedule_send(plan, "send_at")
            if plan.get("late_send_at") and not plan.get("late_sent_at"):
                self._schedule_send(plan, "late_send_at")
            for key in ("refresh_at", "late_refresh_at"):
                if plan.get(key):
                    self._schedule_send(plan, key)

    async def _async_send_when_ready(self, plan: dict[str, Any]) -> None:
        """Send a plan automatically once REMA has its products and prices.

        The avis is out days before it starts, but REMA's products and prices
        for it (and new products on offer) come at 02:00 on the shopping day;
        thursday's offers at 02:00 that thursday.
        """
        now = dt_util.utcnow()
        main_at = prices_from(date.fromisoformat(plan["start_date"]))
        if main_at <= now:
            await self.async_send(plan["id"], "main", strict=False)
        else:
            plan["send_at"] = main_at.isoformat()
            self._schedule_send(plan, "send_at")
        late = sorted(line["buy_from"] for line in plan["shopping"] if line.get("buy_from"))
        if late:
            plan["late_send_at"] = prices_from(date.fromisoformat(late[0])).isoformat()
            self._schedule_send(plan, "late_send_at")
        await self.store.async_save()
        self._notify()

    @callback
    def _schedule_send(self, plan: dict[str, Any], key: str) -> None:
        when = parse_time(plan.get(key))
        if when is None:
            return
        self._cancel_send(plan["id"], key)
        if date.fromisoformat(plan["end_date"]) < dt_util.now().date():
            plan.pop(key, None)  # the week is over; nothing to buy any more
            return
        part = "late" if key.startswith("late_") else "main"
        plan_id = plan["id"]
        work = self._async_refresh_due if key.endswith("refresh_at") else self._async_send_due

        @callback
        def _due(_now: datetime) -> None:
            self._sends.pop((plan_id, key), None)
            self.hass.async_create_task(work(plan_id, part), name=f"{DOMAIN} {key}")

        # A time that has passed (HA was off at 02:00) fires right away.
        self._sends[(plan_id, key)] = async_track_point_in_utc_time(
            self.hass, _due, max(when, dt_util.utcnow())
        )

    @callback
    def _cancel_send(self, plan_id: str, key: str) -> None:
        if unsub := self._sends.pop((plan_id, key), None):
            unsub()

    async def _async_refresh_due(self, plan_id: str, part: str) -> None:
        plan = self.store.get_plan(plan_id)
        if plan is None:
            return
        plan.pop("late_refresh_at" if part == "late" else "refresh_at", None)
        if plan.get("late_send_at" if part == "late" else "send_at"):
            await self.store.async_save()
            return  # sent automatically now, which looks at the offers again first
        try:
            await self.async_refresh_offers(plan_id, part)
        except (HomeAssistantError, RemaError) as err:
            _LOGGER.warning("Could not look at the meal plan's offers again: %s", err)
            await self.store.async_save()

    async def _async_send_due(self, plan_id: str, part: str) -> None:
        if self.store.get_plan(plan_id) is None:
            return
        try:
            await self.async_send(plan_id, part, strict=False)
        except (HomeAssistantError, RemaError) as err:
            _LOGGER.warning("Could not send the meal plan to REMA automatically: %s", err)

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
        try:
            self.async_start_generation(start, send=settings["auto_send"])
        except HomeAssistantError as err:
            _LOGGER.warning("Could not make the meal plan for %s automatically: %s", key, err)

    @callback
    def async_cancel(self) -> None:
        """Stop a running generation and the waiting sends (on unload)."""
        if self._task and not self._task.done():
            self._task.cancel()
        for unsub in self._sends.values():
            unsub()
        self._sends.clear()


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
    if glued := re.match(r"^\s*(\d+)\s*[x×*](\S.*)$", text):  # '3xæg'
        return max(1, int(glued.group(1))), glued.group(2).strip()
    return 1, text


def apply_chain_offers(
    shopping: list[dict[str, Any]], chain_offers: list[tuple[str, str, dict[str, Any]]]
) -> None:
    """A line built on another chain's offer goes on that shop's list, at the offer's price.

    The REMA product found for it (if any) stays, so it can be moved back.
    """
    by_key = {key: (dealer_id, offer) for key, dealer_id, offer in chain_offers}
    for line in shopping:
        entry = by_key.get(str(line.get("offer") or ""))
        if entry is None:
            continue
        dealer_id, offer = entry
        price = offer.get("price")
        price = float(price) if isinstance(price, (int, float)) else None
        packages = int(line.get("packages") or 1)
        line.update(
            buy_at=dealer_id,
            chain_price=price,
            chain_heading=str(offer.get("heading") or "")[:200],
            chain_planned=True,  # chosen by the plan, not moved there by the family
            bought=False,
            offer_name=str(offer.get("heading") or "")[:200],
            packages=packages,
        )
        if price is not None:
            line["cost"] = round(price * packages, 2)


def update_feedback(base: dict[str, Any], iso: list[str], problems: list[str]) -> str:
    """What the AI is told when it updates a plan to changed settings."""
    kept = [d for d in base.get("days", []) if d["date"] in iso]
    current = "; ".join(
        f"{d['weekday']} {d['date']}: {d['dish']}"
        + (" (rester)" if d.get("uses_leftovers_from") or d.get("type") == "rester" else "")
        for d in kept
    )
    new_days = [d for d in iso if d not in {k["date"] for k in kept}]
    lines = [
        f"Familien har allerede denne madplan: {current or 'ingen dage'}. De har ændret "
        "indstillingerne siden. Ret planen til, så den overholder kravene ovenfor: behold så "
        "mange af retterne som muligt på deres dage, og lav kun de dage om, der skal ændres."
    ]
    if new_days:
        lines.append("Disse dage er nye og skal have en ret: " + ", ".join(new_days) + ".")
    if problems:
        lines.append("Det bryder den nuværende plan med de nye indstillinger:")
        lines.extend(f"- {p}" for p in problems)
    return "\n".join(lines)


def plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    """The fields of a plan needed for lists."""
    return {
        key: plan.get(key)
        for key in ("id", "title", "start_date", "end_date", "week", "status", "total", "budget")
    } | {"dishes": [day["dish"] for day in plan.get("days", [])]}


def _local_day(moment: datetime) -> date:
    """The local day of a moment (an avis from 22:00 UTC starts the next day here)."""
    return dt_util.as_local(moment).date()


def plan_dates(start: date, days: int, skip: set[date] | None = None) -> list[date]:
    """The days of a plan that get a dinner."""
    return [d for d in (start + timedelta(days=i) for i in range(days)) if d not in (skip or set())]


def parse_date(value: str | None) -> date | None:
    """Parse an ISO date from the panel."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as err:
        raise _invalid("invalid_date", value=value) from err

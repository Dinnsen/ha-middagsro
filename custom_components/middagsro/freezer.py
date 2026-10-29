"""Separate batch-cooking plans with explicit, per-dish portions."""

from __future__ import annotations

import copy
from datetime import timedelta
import json
from typing import Any
import uuid

from homeassistant.util import dt as dt_util

from .mealplan import MealPlanner, recipe_line
from .recipes import scale_amount
from .words import is_tap_water, pantry_words


def build_prompt(settings: dict[str, Any], count: int, note: str) -> str:
    """Request complete base recipes, never household or percentage scaling."""
    return (
        f"Lav en fryserplan med præcis {count} forskellige retter til én fælles maddag. "
        "Hver opskrift skal være til præcis 4 portioner. Brug IKKE husstandens størrelse "
        "eller portionsprocent. Brugeren vælger bagefter portioner pr. ret. "
        "Vælg retter hvor sovsen/gryderetten kan fryses for sig og serveres med friskkogt "
        "pasta, ris eller andet tilbehør. Medtag KUN selve fryserrettens ingredienser og "
        "fremgangsmåde, IKKE ris/pasta eller andet separat tilbehør i ingredienslisten. "
        "Skriv forslag til tilbehør i tip. Væsken må gerne omfatte vand. "
        "Angiv alle mængder i ingredients.amount (fx '400 g', '2 stk', '1 dl'). "
        "Alle mængder i instruktionerne skal henvise til ingredienslisten; skriv ikke "
        "faste gram/antal/portioner i steps eller tip, da opskriften senere skaleres. "
        "Giv komplette trin til madlavningen på dansk. "
        f"Allergier: {json.dumps(settings.get('allergies', []), ensure_ascii=False)}. "
        f"Andre allergier: {settings.get('allergies_other', '')}. "
        f"Undgå: {json.dumps(settings.get('avoid', []), ensure_ascii=False)}. "
        f"Andet I undgår: {settings.get('avoid_other', '')}. "
        f"Ønsker til maden: {settings.get('wishes', '')}. "
        f"Familiens faste ønsker: {json.dumps(settings.get('rules', []), ensure_ascii=False)}. "
        f"Ønsker til fryserplanen: {note[:2000]}. "
        'Svar KUN JSON: {"days":[{"dish":"Kødsovs","servings":4,'
        '"ingredients":[{"name":"Hakket oksekød","amount":"400 g"}],'
        '"steps":[{"text":"Brun kødet.","minutes":5}],'
        '"active_minutes":20,"total_minutes":60,"tip":"Server med friskkogt pasta."}]}.'
    )


def _shopping(plan: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild from all dishes; combine shared ingredients before package matching."""
    pantry = pantry_words(settings["pantry"])
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for day in plan["days"]:
        for ingredient in day["ingredients"]:
            if is_tap_water(ingredient["name"]):
                continue
            line = recipe_line(ingredient)
            if line["search"].lower() in pantry:
                continue
            key = (line["search"].lower(), line["unit"])
            if key in merged:
                old = merged[key]
                old["amount"] = (
                    max(old["amount"], line["amount"])
                    if line.get("stock_cubes")
                    else old["amount"] + line["amount"]
                )
            else:
                merged[key] = line
    return list(merged.values())


async def _price(planner: MealPlanner, plan: dict[str, Any]) -> None:
    lines = _shopping(plan, planner.store.settings)
    await planner._async_price_lines(lines, [])
    plan["shopping"] = lines
    plan["total"] = round(sum(line.get("cost") or 0 for line in lines), 2)
    plan.pop("missing_products", None)


async def async_generate(
    planner: MealPlanner, count: int, note: str | None = None
) -> dict[str, Any]:
    """Create a batch plan independently of the weekly calendar and household settings.

    The wishes are the freezer plan's own (``note``, kept for next time), never the
    weekly plan's.
    """
    if count not in (4, 5):
        raise ValueError("Vælg 4 eller 5 fryserretter.")
    if note is not None:
        planner.store.freezer_note = " ".join(note.split())[:2000]
        await planner.store.async_save()
    raw = await planner._async_ask_ai(
        build_prompt(planner.store.settings, count, planner.store.freezer_note), "Fryserplan"
    )
    raw_days = raw.get("days")
    if not isinstance(raw_days, list) or len(raw_days) != count:
        raise ValueError("AI'en gav ikke det valgte antal fryserretter. Prøv igen.")
    today = dt_util.now().date()
    days = planner._clean_days(raw_days, [today + timedelta(days=i) for i in range(count)])
    for raw_day, day in zip(raw_days, days, strict=True):
        if (
            not isinstance(raw_day, dict)
            or raw_day.get("servings") != 4
            or not raw_day.get("dish")
            or not day["ingredients"]
            or not day["steps"]
            or any(not i["amount"] for i in day["ingredients"])
        ):
            raise ValueError("En fryserret mangler en komplet opskrift til 4 portioner. Prøv igen.")
        day.update(servings=4, makes_leftovers=False, uses_leftovers_from=None, type="normal")
        day["base_ingredients"] = copy.deepcopy(day["ingredients"])
        day["uses"] = [i["name"] for i in day["ingredients"] if not is_tap_water(i["name"])]
    plan = {
        "id": uuid.uuid4().hex[:12],
        "kind": "freezer",
        "created": dt_util.now().isoformat(),
        "title": f"Fryserplan · {today.strftime('%d/%m/%Y')}",
        "start_date": today.isoformat(),
        "end_date": today.isoformat(),
        "week": today.isocalendar().week,
        "status": "draft",
        "sent_at": None,
        "portion_percent": 100,
        "budget": 0,
        "catalog": None,
        "summary": "Ret portioner pr. ret før indkøb. Tilbehør købes til spisedagen.",
        "days": days,
        "shopping": [],
        "checklist": [],
    }
    await _price(planner, plan)
    await planner.store.async_add_plan(plan)
    planner._notify()
    return plan


async def async_portions(
    planner: MealPlanner, plan_id: str, day_date: str, portions: int
) -> dict[str, Any]:
    """Serialize edits with cart transfers and other portion changes."""
    async with planner._send_lock:
        return await _async_portions(planner, plan_id, day_date, portions)


async def _async_portions(
    planner: MealPlanner, plan_id: str, day_date: str, portions: int
) -> dict[str, Any]:
    """Absolute scaling from the original four portions; failed pricing is atomic."""
    plan = planner.store.get_plan(plan_id)
    if not plan or plan.get("kind") != "freezer":
        raise ValueError("Fryserplanen findes ikke.")
    if not 1 <= portions <= 100:
        raise ValueError("Vælg mellem 1 og 100 portioner.")
    # Once a transfer has started, changing totals could duplicate or underbuy products.
    if (
        plan.get("portions_locked")
        or plan.get("sent_at")
        or any(line.get("sent") for line in plan["shopping"])
    ):
        raise ValueError("Ret portioner før varer sendes til kurven. Lav en ny fryserplan.")
    candidate = copy.deepcopy(plan)
    day = next((d for d in candidate["days"] if d["date"] == day_date), None)
    if day is None:
        raise ValueError("Retten findes ikke i fryserplanen.")
    day["ingredients"] = [
        {**i, "amount": scale_amount(i["amount"], portions / 4)} for i in day["base_ingredients"]
    ]
    day["servings"] = portions
    await _price(planner, candidate)
    plan.clear()
    plan.update(candidate)
    await planner.store.async_save()
    planner._notify()
    return plan

"""Health and nutrition of a meal plan.

- Nutrition per adult portion of each dinner, as the AI estimates it with the
  recipe and as REMA's own product data adds up (nutrition per 100 g, as in
  the REMA app), against the family's targets (kcal and protein/carbs/fat).
- The official Danish dietary advice (De officielle kostråd, Fødevarestyrelsen)
  for what the shopping list holds: vegetables, fish, red meat and legumes.
  Only the dinners are counted, so the numbers say how much of the advice the
  dinners cover.
- Labels on the products: the Keyhole (Nøglehullet), organic, ASC/MSC.
"""

from __future__ import annotations

from typing import Any

from .mealplan import NUTRITION_KEYS, _tokens, package_size
from .planedit import _ingredient_lines, _is_cooked

# De officielle kostråd (Fødevarestyrelsen).
VEGETABLES_PER_DAY = 600  # g fruit and vegetables a day, most of it vegetables
FISH_PER_WEEK = 350  # g a week, of which 200 g fatty fish
FATTY_FISH_PER_WEEK = 200
RED_MEAT_PER_WEEK = 350  # at most, cooked weight
LEGUMES_PER_DAY = 100  # g soaked/cooked legumes
COOKED_SHARE = 0.7  # raw meat loses about 30 % when cooked

_VEG = {
    "broccoli", "blomkål", "gulerod", "gulerødder", "løg", "porre", "spinat", "salat", "agurk",
    "tomat", "tomater", "peberfrugt", "squash", "aubergine", "kål", "spidskål", "hvidkål",
    "rødkål", "grønkål", "rosenkål", "ærter", "majs", "bønner", "champignon", "svampe",
    "selleri", "pastinak", "rødbede", "rødbeder", "grøntsager", "grøntsagsblanding", "asparges",
    "radiser", "rucola", "feldsalat", "hjertesalat", "icebergsalat", "græskar", "fennikel",
}  # fmt: skip
_NOT_VEG = {"kartofler", "kartoffel", "chips", "pommes", "frites"}
_FISH = {
    "laks", "torsk", "sej", "rødspætte", "makrel", "sild", "tun", "ørred", "rejer", "fisk",
    "kuller", "pangasius", "hellefisk", "rødfisk", "fiskefrikadeller", "fiskefilet", "sejfilet",
}  # fmt: skip
_FATTY_FISH = {"laks", "makrel", "sild", "ørred", "hellefisk"}
_RED_MEAT = {
    "okse", "oksekød", "kalv", "kalvekød", "gris", "grise", "grisekød", "svin", "svinekød",
    "lam", "lammekød", "flæsk", "bacon", "skinke", "pølse", "pølser", "medister", "leverpostej",
    "frikadeller", "hakkebøf", "kotelet", "koteletter", "nakkefilet", "mørbrad", "spareribs",
    "salami", "kødpølse", "hamburgerryg", "ungkvæg", "entrecote", "culotte", "bøf", "gyros",
}  # fmt: skip
_POULTRY = {"kylling", "kyllinge", "kalkun", "and", "høne"}
_LEGUMES = {"linser", "kikærter", "bønner", "kidneybønner", "hummus", "edamame", "falafel"}


def _words(line: dict[str, Any]) -> set[str]:
    product = line.get("product") or {}
    text = f"{line.get('name') or ''} {product.get('name') or ''}"
    words = set(_tokens(text))
    # Compound words: "laksefilet" is laks, "hk. oksekød" is oksekød.
    parts = set()
    for word in words:
        for group in (_VEG, _FISH, _RED_MEAT, _POULTRY, _LEGUMES):
            parts |= {g for g in group if len(g) > 3 and word.startswith(g)}
    return words | parts


def line_grams(line: dict[str, Any]) -> float | None:
    """How many grams (or ml) a shopping line buys, if its package says."""
    product = line.get("product") or line.get("avis_item") or {}
    size = package_size(product.get("underline"))
    packages = line.get("packages") or 1
    if size and size[0] in ("g", "ml"):
        return size[1] * packages
    unit = str(line.get("unit") or "").lower()
    amount = line.get("amount")
    if amount and unit in ("g", "kg", "ml", "l"):
        return float(amount) * (1000 if unit in ("kg", "l") else 1)
    return None


def food_group(line: dict[str, Any]) -> str | None:
    """vegetables, fish, red_meat, legumes or None, by the line's names and department."""
    words = _words(line)
    product = line.get("product") or {}
    where = " ".join(
        str(text or "").lower()
        for text in (product.get("department"), product.get("category"), line.get("category"))
    )
    # In order: the first rule that fits decides (chicken is not red meat,
    # potatoes are not vegetables in the dietary advice).
    rules: list[tuple[bool, str | None]] = [
        (bool(words & _LEGUMES), "legumes"),
        (bool(words & _FISH) or "fisk" in where, "fish"),
        (bool(words & _POULTRY), None),
        (
            bool(words & _RED_MEAT) or any(w in where for w in ("oksekød", "gris", "lam", "kalv")),
            "red_meat",
        ),
        (bool(words & _NOT_VEG), None),
        (bool(words & _VEG) or "frugt" in where or "grønt" in where, "vegetables"),
    ]
    return next((group for fits, group in rules if fits), None)


def _people(settings: dict[str, Any]) -> float:
    """Portions: an adult is one, a child less (as the AI is told)."""
    total = 0.0
    for member in settings.get("household") or []:
        if member.get("role") == "child":
            age = member.get("age") or 8
            total += 0.4 if age < 4 else 0.6 if age < 10 else 0.8
        else:
            total += 1
    return max(total, 1.0)


def _percent(nutrition: dict[str, float]) -> dict[str, float] | None:
    energy = (
        nutrition.get("protein_g", 0) * 4
        + nutrition.get("carbs_g", 0) * 4
        + nutrition.get("fat_g", 0) * 9
    )
    if energy <= 0:
        return None
    return {
        "protein": round(nutrition.get("protein_g", 0) * 4 / energy * 100),
        "carbs": round(nutrition.get("carbs_g", 0) * 4 / energy * 100),
        "fat": round(nutrition.get("fat_g", 0) * 9 / energy * 100),
    }


def _used_grams(line: dict[str, Any]) -> float | None:
    """How much of a line the recipes use: what was asked for, else what is bought."""
    unit = str(line.get("unit") or "").lower()
    amount = line.get("amount")
    if amount and unit in ("g", "kg", "ml", "l", "dl"):
        return float(amount) * {"kg": 1000, "l": 1000, "dl": 100}.get(unit, 1)
    return line_grams(line)


def rema_nutrition(
    plan: dict[str, Any], day: dict[str, Any], people: float, table: dict[int, dict[str, float]]
) -> dict[str, float] | None:
    """A dish's nutrition per adult portion from REMA's own product data.

    The dish's items (shared items split between the dishes using them), by
    weight, times REMA's nutrition per 100 g, over the portions it makes
    (twice as many when it makes leftovers). Basic items are not counted.
    """
    mine = _ingredient_lines(plan, day)
    if not mine:
        return None
    sharing: dict[str, int] = {}
    for other in plan.get("days") or []:
        if _is_cooked(other):
            for line_id in _ingredient_lines(plan, other):
                sharing[line_id] = sharing.get(line_id, 0) + 1
    totals = dict.fromkeys(NUTRITION_KEYS, 0.0)
    counted = 0
    for line in plan["shopping"]:
        if line.get("id") not in mine:
            continue
        product_id = (line.get("product") or {}).get("id")
        per100 = table.get(product_id) if product_id else None
        grams = _used_grams(line)
        if not per100 or grams is None:
            continue
        counted += 1
        share = grams / 100 / max(sharing.get(line["id"], 1), 1)
        for key in NUTRITION_KEYS:
            totals[key] += per100.get(key, 0) * share
    if not counted:
        return None
    portions = people * (2 if day.get("makes_leftovers") else 1)
    out = {key: round(value / portions, 1) for key, value in totals.items()}
    out["coverage"] = round(counted / len(mine) * 100)
    return out


def _average(items: list[dict[str, float]]) -> dict[str, float] | None:
    if not items:
        return None
    return {key: round(sum(n.get(key, 0) for n in items) / len(items), 1) for key in NUTRITION_KEYS}


def plan_health(
    plan: dict[str, Any],
    settings: dict[str, Any],
    table: dict[int, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Nutrition, dietary advice and labels for a plan.

    table: REMA's nutrition per 100 g for the plan's products (by product id).
    """
    people = _people(settings)
    days = [d for d in plan.get("days") or [] if d.get("dish")]
    by_date = {d["date"]: d for d in days}
    dinners = []
    for day in days:
        source = by_date.get(day.get("uses_leftovers_from") or "", day)
        nutrition = source.get("nutrition") or None
        rema = rema_nutrition(plan, source, people, table) if table else None
        dinners.append(
            {
                "date": day["date"],
                "dish": day["dish"],
                "leftovers": source is not day,
                "nutrition": nutrition,
                "percent": _percent(nutrition) if nutrition else None,
                "rema": rema,
                "rema_percent": _percent(rema) if rema else None,
            }
        )
    average = _average([d["nutrition"] for d in dinners if d["nutrition"]])
    rema_average = _average([d["rema"] for d in dinners if d["rema"]])

    count = max(len(days), 1)
    grams: dict[str, float] = {
        "vegetables": 0,
        "fish": 0,
        "fatty_fish": 0,
        "red_meat": 0,
        "legumes": 0,
    }
    unknown: list[str] = []
    for line in plan.get("shopping") or []:
        group = food_group(line)
        if group is None:
            continue
        amount = line_grams(line)
        if amount is None:
            unknown.append(str(line.get("name") or ""))
            continue
        grams[group] += amount
        if group == "fish" and _words(line) & _FATTY_FISH:
            grams["fatty_fish"] += amount
    week = 7 / count  # the plan's days scaled to a week
    advice = [
        {
            "key": "vegetables",
            "label": "Frugt og grønt",
            "value": round(grams["vegetables"] / people / count),
            "goal": VEGETABLES_PER_DAY,
            "unit": "g pr. person pr. dag",
            "kind": "min",
            "note": "Kostrådet er 600 g om dagen i alt – aftensmaden kan give en god del.",
        },
        {
            "key": "fish",
            "label": "Fisk",
            "value": round(grams["fish"] / people * week),
            "goal": FISH_PER_WEEK,
            "unit": "g pr. person pr. uge",
            "kind": "min",
            "note": f"Heraf fed fisk: {round(grams['fatty_fish'] / people * week)} g (mindst 200 g).",
        },
        {
            "key": "red_meat",
            "label": "Rødt kød",
            "value": round(grams["red_meat"] * COOKED_SHARE / people * week),
            "goal": RED_MEAT_PER_WEEK,
            "unit": "g tilberedt pr. person pr. uge",
            "kind": "max",
            "note": "Højst 350 g tilberedt kød om ugen (okse, kalv, gris og lam, også pålæg).",
        },
        {
            "key": "legumes",
            "label": "Bælgfrugter",
            "value": round(grams["legumes"] / people / count),
            "goal": LEGUMES_PER_DAY,
            "unit": "g pr. person pr. dag",
            "kind": "min",
            "note": "Linser, bønner og kikærter – gerne 100 g om dagen.",
        },
    ]

    priced = [
        line for line in plan.get("shopping") or [] if line.get("product") and line.get("cost")
    ]
    total = sum(line["cost"] for line in priced) or 0

    def share(test: Any) -> int | None:
        if not total:
            return None
        return round(sum(line["cost"] for line in priced if test(line["product"])) / total * 100)

    labels = {
        "keyhole": share(lambda p: "Nøglehul" in (p.get("labels") or [])),
        "organic": share(lambda p: bool(p.get("is_organic"))),
        "asc_msc": share(lambda p: bool({"ASC", "MSC"} & set(p.get("labels") or []))),
        "known": any("labels" in line["product"] for line in priced),
    }
    targets = (
        {
            "kcal_min": settings["kcal_min"],
            "kcal_max": settings["kcal_max"],
            "protein": settings["protein_pct"],
            "carbs": settings["carb_pct"],
            "fat": settings["fat_pct"],
        }
        if settings.get("nutrition_enabled")
        else None
    )
    return {
        "plan_id": plan.get("id"),
        "title": plan.get("title"),
        "people": round(people, 1),
        "days": count,
        "targets": targets,
        "dinners": dinners,
        "average": average,
        "average_percent": _percent(average) if average else None,
        "rema_average": rema_average,
        "rema_average_percent": _percent(rema_average) if rema_average else None,
        "advice": advice,
        "unknown": unknown,
        "labels": labels,
    }

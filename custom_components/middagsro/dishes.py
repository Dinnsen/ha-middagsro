"""What makes two dinners the same dish, and whether a plan keeps the family's rules.

The AI is asked to keep the rules, but it is not trusted to: a plan is checked
here afterwards, by the same measure a family uses ("laks again?" is about the
main dish, not the side), and the AI is asked again about what it got wrong.
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from .words import _NEUTRAL_WORDS, _stem, _tokens

# "Ovnbagt laks med ...": what comes before these is the dish, after them the sides.
_SIDES = re.compile(r"\s(?:med|m\.|og|i|på|til|a la|à la|–|-)\s|,|\(", re.IGNORECASE)
_LEFTOVERS = re.compile(r"^\s*rest(?:er|erne)?\s+(?:af|fra)\s+", re.IGNORECASE)
# How it is made says nothing about what it is.
_HOW = {
    "ovnbagt", "ovnbagte", "bagt", "bagte", "stegt", "stegte", "kogt", "kogte", "grillet",
    "grillede", "hjemmelavet", "hjemmelavede", "sprød", "sprøde", "nem", "nemme", "nemt",
    "hurtig", "hurtige", "hurtigt", "klassisk", "klassiske", "lækker", "lækre", "cremet",
    "cremede", "italiensk", "italienske", "mexicansk", "mexicanske", "asiatisk", "asiatiske",
    "indisk", "indiske", "græsk", "græske", "thai", "varm", "varme", "kold", "kolde", "lun",
    "lune", "fyldt", "fyldte", "frisk", "friske", "stor", "store", "lille", "små", "mini",
    "pandestegt", "pandestegte", "langtidsstegt", "braiseret", "dampet", "dampede", "sund",
    "sunde", "børnevenlig", "børnevenlige", "familiens", "mormors", "farmors", "dag", "eller",
    "samt", "evt", "fx",
}  # fmt: skip
# A compound that ends in one of these is that kind of dish (minipizza is pizza).
_KINDS = (
    "pizza", "suppe", "burger", "frikadeller", "frikadelle", "lasagne", "risotto", "tærte",
    "wok", "gryde", "pandekager", "bolognese", "carbonara", "curry", "tacos", "wraps", "wrap",
    "gratin", "pie", "boller", "bøffer", "bøf", "kebab", "pølser", "pølse", "omelet",
    "sandwich", "toast",
)  # fmt: skip


_NO_DISH = ("ikke hjemme", "spiser ude", "fri aften", "ude at spise", "ingen aftensmad")


def dish_key(name: str, kinds: bool = True) -> frozenset[str]:
    """The words that say which dish it is: "Ovnbagt laks med pasta" -> {laks}.

    The sides ("med ...") don't count, nor how it is made. A kind of dish is
    added for compounds ("minipizza" is a pizza), so variants are the same dish;
    not when ``kinds`` is off. An evening out is no dish at all (empty).
    """
    if any(phrase in (name or "").lower() for phrase in _NO_DISH):
        return frozenset()
    head = _LEFTOVERS.sub("", name or "")
    head = _SIDES.split(head, maxsplit=1)[0]
    words = [w for w in _tokens(head) if len(w) > 1 and w not in _NEUTRAL_WORDS and w not in _HOW]
    if not words:
        words = [w for w in _tokens(name or "") if len(w) > 2 and w not in _NEUTRAL_WORDS]
    key: set[str] = set()
    for word in words:
        key.add(_stem(word))
        for kind in _KINDS if kinds else ():
            if word != kind and word.endswith(kind) and len(word) > len(kind) + 2:
                key.add(_stem(kind))
    return frozenset(key)


def same_dish(a: str, b: str, strict: bool = False) -> bool:
    """Are two dinners the same dish ("Laks med pasta" and "Ovnbagt laks med ris")?

    Strict: kyllingefrikadeller are not fiskefrikadeller (no kinds of dish), for
    the dishes the family dislikes and for putting their own recipe on a day.
    """
    key_a, key_b = dish_key(a, not strict), dish_key(b, not strict)
    if not key_a or not key_b:
        return False
    return any(
        x == y or (len(x) > 3 and len(y) > 3 and (x.endswith(y) or y.endswith(x)))
        for x in key_a
        for y in key_b
    )


def matches_any(name: str, names: list[str], strict: bool = False) -> str | None:
    """The first of the names that is the same dish, if any."""
    return next((other for other in names if same_dish(name, other, strict)), None)


def in_text(name: str, text: str) -> bool:
    """Does a note ("onsdag: laks") name this dish?"""
    if not text:
        return False
    words = {_stem(w) for w in _tokens(text) if len(w) > 2}
    return any(
        k in words or any(len(k) > 3 and (w.endswith(k) or k.endswith(w)) for w in words)
        for k in dish_key(name)
    )


# ------------------------------------------------------------------ portions


def household_portions(settings: dict[str, Any]) -> float:
    """How many adult portions a dinner is: children eat less (a 1-year-old a quarter)."""
    total = 0.0
    for member in settings.get("household") or []:
        age = int(member.get("age") or 30)
        if member.get("role") == "child" and age < 12:
            total += 0.3 if age <= 5 else 0.6
        else:
            total += 1.0
    return round(total, 1) or 2.0


# ------------------------------------------------------------------ checking a plan


def is_cooked(day: dict[str, Any]) -> bool:
    """A day a dinner is made on (not leftovers, not emptied)."""
    return (
        not day.get("uses_leftovers_from")
        and day.get("type") not in ("rester", "tom")
        and bool(day.get("dish"))
    )


def check_plan(
    plan: dict[str, Any],
    settings: dict[str, Any],
    *,
    recent: list[str],
    due_ids: set[str],
    note: str = "",
    disliked: list[str] | None = None,
) -> list[str]:
    """What a plan gets wrong, each as a line the AI (and the family) understands.

    Repeats of the last weeks' dishes count by their main dish; a favourite that is
    due, or a dish the family asked for in the note, may of course repeat.
    """
    problems: list[str] = []
    days = plan.get("days") or []
    cooked = [d for d in days if is_cooked(d)]
    for day in cooked:
        dish = day["dish"]
        if day.get("favorite_id") in due_ids or in_text(dish, note):
            continue
        if (earlier := matches_any(dish, recent)) is not None:
            problems.append(
                f'{day["weekday"]} {day["date"]}: "{dish}" gentager "{earlier}" fra de '
                "seneste uger – vælg en helt anden hovedret"
            )
    for day in cooked:
        if (bad := matches_any(day["dish"], disliked or [], strict=True)) is not None:
            problems.append(
                f'{day["weekday"]} {day["date"]}: "{day["dish"]}" er en variant af "{bad}", '
                "som familien ikke kan lide"
            )
    seen: list[dict[str, Any]] = []
    for day in cooked:
        if (twice := matches_any(day["dish"], [d["dish"] for d in seen])) is not None:
            problems.append(
                f'{day["weekday"]} {day["date"]}: "{day["dish"]}" er samme ret som '
                f'"{twice}" tidligere på ugen'
            )
        seen.append(day)
    # A fixed day is the family's own rule: leftovers on thursdays, or a dish.
    rest_days: set[str] = set()
    for fixed in settings.get("fixed_days") or []:
        text = str(fixed.get("text") or "")
        for day in days:
            if date.fromisoformat(day["date"]).weekday() != fixed.get("weekday"):
                continue
            if "rest" in text.lower():
                rest_days.add(day["date"])
                if not (day.get("uses_leftovers_from") or _LEFTOVERS.match(day["dish"])):
                    problems.append(
                        f"{day['weekday']} {day['date']}: skal være rester ({text}), ikke "
                        f'"{day["dish"]}"'
                    )
            elif dish_key(text) and not same_dish(day["dish"], text):
                problems.append(
                    f'{day["weekday"]} {day["date"]}: skal være "{text}" (fast dag), ikke '
                    f'"{day["dish"]}"'
                )
    leftovers = [
        d
        for d in days
        if (d.get("uses_leftovers_from") or d.get("type") == "rester")
        and d.get("type") != "fast"
        and d["date"] not in rest_days
    ]
    wanted = settings.get("leftover_days") or 0
    if len(days) > 1 and len(leftovers) != wanted:
        problems.append(
            f"Der er {len(leftovers)} restedage, men der skal være præcis {wanted}"
            + (' (type "rester" med uses_leftovers_from)' if wanted else "")
        )
    for day in leftovers:
        source = day.get("uses_leftovers_from")
        before = next((d for d in days if d["date"] == source), None)
        if source and (before is None or not before.get("makes_leftovers")):
            problems.append(
                f"{day['weekday']} {day['date']}: rester af {source}, men den dag laver ikke "
                "dobbelt portion (makes_leftovers)"
            )
    vegetarian = sum(1 for d in cooked if d.get("type") == "vegetar")
    low, high = settings.get("min_vegetarian") or 0, settings.get("max_vegetarian") or 0
    if vegetarian < low:
        problems.append(f"Kun {vegetarian} vegetarretter; der skal være mindst {low}")
    elif vegetarian > high:
        problems.append(f"{vegetarian} vegetarretter; der må højst være {high}")
    limit = settings.get("max_cook_minutes_weekday") or 0
    for day in cooked:
        when = date.fromisoformat(day["date"])
        if limit and when.weekday() < 5 and (day.get("active_minutes") or 0) > limit:
            problems.append(
                f'{day["weekday"]} {day["date"]}: "{day["dish"]}" tager {day["active_minutes"]} '
                f"minutters aktiv tilberedning; højst {limit} på hverdage"
            )
    return problems

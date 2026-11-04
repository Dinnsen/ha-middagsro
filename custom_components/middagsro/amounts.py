"""Amounts and packages: base units, package sizes and how many to buy."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from .api import Product

_LOGGER = logging.getLogger(__name__)


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


def to_base(amount: float, unit: str | None) -> tuple[str, float] | None:
    """Convert an amount to grams, millilitres or pieces."""
    if not unit:
        return None
    base = _UNIT_BASE.get(unit.strip().lower().rstrip("."))
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


def packages_needed(
    amount: float | None,
    unit: str | None,
    product: Product,
    piece_g: int | None = None,
    need: dict[str, float] | None = None,
) -> int:
    """How many packages of a product cover an amount.

    ``piece_g``: what one piece of the thing weighs, so "4 løg" of a 750 g bag is
    one bag, "2 stk" of something sold loose is two, and 600 g of a squash sold
    per piece is two. ``need``: the line's needs in each base unit, when its
    recipes wrote it in more than one ("300 g" and "1 pk"); each is counted in
    packages and they are added up, so nothing a recipe asked for is lost.
    """
    parts = dict(need or {})
    if not parts:
        base = to_base(amount, unit) if amount and amount > 0 else None
        if base is None:
            return 1
        parts = {base[0]: base[1]}
    size = package_size(product.underline)
    count = 0.0
    # Sizes are rounded: 1.02 kilo of a kilo bag is one bag; and a piece weighs about
    # what the catalogue says: 500 g broccoli is one head of 400 g.
    slack = 0.0
    known = False
    for part, quantity in parts.items():
        if quantity <= 0:
            continue
        if part == "pack":  # cans, packs, bags: one package each
            count += quantity
        elif size and part == size[0] and size[1] > 0:
            count, slack = count + quantity / size[1], max(slack, 0.05)
        elif part == "stk" and (per_package := pieces_per_package(size, piece_g)):
            count, slack = count + quantity / per_package, max(slack, 0.05)
        elif part == "stk" and size is None:
            count += quantity  # loose items sold per piece
        elif part == "g" and piece_g and size and size[0] == "stk" and size[1] > 0:
            count, slack = count + quantity / piece_g / size[1], 0.3
        else:
            continue  # e.g. 8 pitabrød from one 375 g bag
        known = True
    if not known:
        return 1
    return max(1, min(20, math.ceil(count - slack)))


def line_packages(line: dict[str, Any], product: Product, piece_g: int | None = None) -> int:
    """How many packages of a product a shopping line needs (its ``need`` too)."""
    return packages_needed(
        line.get("amount"), line.get("unit"), product, piece_g, line.get("need") or None
    )


def base_need(line: dict[str, Any]) -> dict[str, float]:
    """A line's needs in base units: {"g": 300, "pack": 1}; empty without an amount."""
    if line.get("need"):
        return {str(k): float(v) for k, v in line["need"].items()}
    base = to_base(float(line["amount"]), line.get("unit")) if line.get("amount") else None
    return {base[0]: base[1]} if base else {}


def pieces_per_package(size: tuple[str, float] | None, piece_g: int | None) -> float | None:
    """How many of a thing a package holds, from its weight and what one weighs:
    eight onions in a kilo bag, one chicken in a 1.1 kg chicken (a little lighter
    or heavier than the catalogue's guess is still one), a sixth of a lettuce in
    a 50 g box of shoots. None when either weight is unknown."""
    if not size or size[0] != "g" or size[1] <= 0 or not piece_g:
        return None
    ratio = size[1] / piece_g
    return ratio if ratio < 0.5 else max(1, int(ratio + 0.25))


_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}


_AMOUNT_FORMS = (
    re.compile(r"^(\d+)?\s*([½¼¾⅓⅔])\s*"),  # 1½
    re.compile(r"^(\d+)\s+(\d+)\s*/\s*(\d+)\s*"),  # 1 1/2
    re.compile(r"^(\d+)\s*/\s*(\d+)\s*"),  # 1/2
    re.compile(r"^(\d+(?:[.,]\d+)?)\s*"),  # 2,5
)


def parse_amount(text: str) -> tuple[float, str] | None:
    """'1½ dl' -> (1.5, 'dl'), '2 x 400 g' -> (800, 'g'), '2-3 stk' -> (2, 'stk'); None without a number."""
    rest = re.sub(r"^(?:ca\.?|cirka)\s*", "", text.strip().lower())
    number: float | None = None
    for form in _AMOUNT_FORMS:
        if not (match := form.match(rest)):
            continue
        groups = match.groups()
        if form is _AMOUNT_FORMS[0]:
            number = float(groups[0] or 0) + _FRACTIONS[groups[1]]
        elif form is _AMOUNT_FORMS[1]:
            number = float(groups[0]) + float(groups[1]) / float(groups[2])
        elif form is _AMOUNT_FORMS[2]:
            number = float(groups[0]) / float(groups[1])
        else:
            number = float(groups[0].replace(",", "."))
        rest = rest[match.end() :]
        break
    if number is None:
        return None
    rest = re.sub(r"^-\s*\d+(?:[.,]\d+)?\s*", "", rest)  # "2-3": the smaller
    if times := re.match(r"^x\s*(\d+(?:[.,]\d+)?)\s*", rest):  # "2 x 400 g"
        number *= float(times.group(1).replace(",", "."))
        rest = rest[times.end() :]
    unit = re.match(r"^([a-zæøå.]*)", rest)
    return number, (unit.group(1) if unit else "").rstrip(".")


def add_amounts(line: dict[str, Any], other: dict[str, Any], piece_g: int | None = None) -> None:
    """Add another line's amount to a line: grams to grams, pieces to pieces, and
    pieces to grams when the catalogue knows what one weighs. Unlike units: the
    weight stands, or the bigger count."""
    needs = base_need(line)
    for part, quantity in base_need(other).items():
        needs[part] = needs.get(part, 0) + quantity
    if piece_g and {"g", "stk"} <= needs.keys():
        needs["g"] += needs.pop("stk") * piece_g
    # Written in more than one unit: every need is kept for counting packages.
    if len(needs) > 1:
        line["need"] = {part: round(quantity, 2) for part, quantity in needs.items()}
    mine = to_base(float(line["amount"]), line.get("unit")) if line.get("amount") else None
    theirs = to_base(float(other["amount"]), other.get("unit")) if other.get("amount") else None
    if mine is None or theirs is None:
        line["amount"] = max(float(line.get("amount") or 1), float(other.get("amount") or 1))
        return
    units = {"g": "g", "ml": "ml", "stk": "stk", "pack": "pk"}
    if mine[0] == theirs[0]:
        line["amount"], line["unit"] = mine[1] + theirs[1], units[mine[0]]
    elif piece_g and {mine[0], theirs[0]} == {"g", "stk"}:
        grams = (mine[1] if mine[0] == "g" else mine[1] * piece_g) + (
            theirs[1] if theirs[0] == "g" else theirs[1] * piece_g
        )
        line["amount"], line["unit"] = grams, "g"
    elif theirs[0] in ("g", "ml") and mine[0] not in ("g", "ml"):
        line["amount"], line["unit"] = theirs[1], units[theirs[0]]
    elif mine[0] not in ("g", "ml"):
        line["amount"] = max(mine[1], theirs[1])
    if line.get("unit") in ("g", "ml") and float(line["amount"]) > 10:
        line["amount"] = math.ceil(float(line["amount"]) / 10) * 10
    if line.get("unit") in ("stk", "pk"):
        line["amount"] = math.ceil(float(line["amount"]))

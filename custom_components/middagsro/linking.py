"""A recipe's ingredients linked to the shop's products, once, when it is added.

Every ingredient that is bought gets a product (REMA's own recipes come with
them). An ingredient has a *kind* ("pasta", "hakket oksekød"): by default
another product of the same kind may take its place, for one on offer; an
ingredient marked *exact* ("fettuccine spinat") is always its own product.
Salt, oil and the other things in the family's pantry, and items marked as
always in the house (``basic``), aren't bought and need no product.

A recipe is *ready* when every ingredient that is bought has a product: then a
plan can use it without anyone checking its items.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from .api import RemaError
from .ingredients import spec_for
from .words import _uses_item, is_tap_water, pantry_words

if TYPE_CHECKING:
    from .mealplan import MealPlanner

MAX_SUGGEST = 40  # ingredients looked up at a time
PARALLEL = 4


def kind_of(name: str) -> str | None:
    """The kind of thing an ingredient is ("2 fed hvidløg, pressede": hvidløg); None
    for a heading, equipment or tap water (nothing to buy)."""
    if is_tap_water(name):
        return None
    spec = spec_for(name)
    return None if spec.skip else spec.key or None


def is_bought(ingredient: dict[str, Any], pantry: list[str]) -> bool:
    """Is an ingredient bought for the recipe (not in the house, not a heading)?"""
    name = str(ingredient.get("name") or "").strip()
    if not name or ingredient.get("basic"):
        return False
    if any(_uses_item(item, name) for item in pantry):
        return False
    return kind_of(name) is not None


def links(recipe: dict[str, Any], pantry_text: str) -> dict[str, Any]:
    """Each ingredient's kind and whether it is bought and linked, and the
    recipe's status: {ready, missing, ingredients: [{kind, bought, linked}]}."""
    pantry = pantry_words(pantry_text)
    rows = []
    for ingredient in recipe.get("ingredients") or []:
        bought = is_bought(ingredient, pantry)
        rows.append(
            {
                "kind": kind_of(str(ingredient.get("name") or "")),
                "bought": bought,
                "linked": bool(ingredient.get("product")),
            }
        )
    missing = sum(1 for row in rows if row["bought"] and not row["linked"])
    return {
        "ready": bool(rows) and not missing,
        "missing": missing,
        "ingredients": rows,
    }


async def async_suggest(planner: MealPlanner, recipe: dict[str, Any]) -> dict[str, Any]:
    """Products for the ingredients that are bought and have none: the matcher's
    pick (the family's earlier choices and the shared table first, then a search)
    with how sure it is and what else there is. Nothing is saved."""
    from .mealplan import recipe_line  # noqa: PLC0415

    status = links(recipe, str(planner.store.settings.get("pantry") or ""))
    if not planner.prices:
        return {**status, "available": False, "suggestions": []}
    todo = [
        (index, ingredient)
        for index, (ingredient, row) in enumerate(
            zip(recipe.get("ingredients") or [], status["ingredients"], strict=False)
        )
        if row["bought"] and not row["linked"]
    ][:MAX_SUGGEST]
    gate = asyncio.Semaphore(PARALLEL)
    own_cache = planner._search_cache is None
    if own_cache:
        planner._search_cache = {}

    async def one(index: int, ingredient: dict[str, Any]) -> dict[str, Any] | None:
        line = recipe_line({"name": ingredient["name"], "amount": ingredient.get("amount")}, 1.0)
        if line is None:
            return None
        async with gate:
            try:
                await planner._async_match(line)
            except RemaError:
                return None
        product = line.get("product")
        return {
            "index": index,
            "product": {k: product.get(k) for k in ("id", "name", "underline", "price", "image")}
            if product
            else None,
            "confidence": line.get("confidence") if product else None,
            "alternatives": line.get("alternatives") or [],
        }

    try:
        found = await asyncio.gather(*(one(i, ing) for i, ing in todo))
    finally:
        if own_cache:
            planner._search_cache = None
    return {**status, "available": True, "suggestions": [f for f in found if f is not None]}

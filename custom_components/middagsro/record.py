"""Save a plan as test cases: the family's answers, and what REMA said that day.

"Gem som testsag" in the panel downloads a file for ``tests/corpus/cases/``:
each line the family kept or chose by hand is a case with that product as the
answer (a line they left out says which product it was not), and every search
and product the matcher looked at is in it, so the test replays the day exactly
(tests/test_corpus.py). Ingredient names and product numbers only; nothing about
the family.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .api import Product, RemaError

if TYPE_CHECKING:
    from .mealplan import MealPlanner

# A line's own words, as the AI or a recipe wrote them.
_LINE_FIELDS = ("name", "amount", "unit", "search", "category")


def product_raw(product: Product) -> dict[str, Any]:
    """A product as the corpus keeps it."""
    return {
        "id": product.id,
        "name": product.name,
        "underline": product.underline,
        "department": product.department,
        "category": product.category,
        "price": product.price,
        "compare_unit": product.compare_unit,
        "compare_unit_price": product.compare_unit_price,
        "is_organic": product.is_organic,
        "labels": list(product.labels),
    }


class _Recording:
    """The shop's client, writing down what it answers."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.searches: dict[str, list[dict[str, Any]]] = {}
        self.products: dict[int, dict[str, Any]] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def async_search_products(self, query: str, limit: int = 15, **kwargs: Any) -> Any:
        found = await self._client.async_search_products(query, limit, **kwargs)
        self.searches[query.lower()] = [product_raw(p) for p in found]
        return found

    async def async_get_products(self, ids: list[int], at: Any = None) -> Any:
        found = await self._client.async_get_products(ids, at)
        for product in found:
            self.products[product.id] = product_raw(product)
        return found


def answered(line: dict[str, Any]) -> list[int] | str | None:
    """What the family said a line is: the product they kept or chose, "unknown"
    for one they left out (it was not that), None when they said nothing."""
    product = line.get("product") or {}
    if line.get("added") or line.get("must_have") or line.get("buy_at") or line.get("chain_only"):
        return None
    if line.get("skipped"):
        # Left out as the wrong product: it was not that. In the house: says nothing.
        return "unknown" if product.get("id") and not line.get("have") else None
    if product.get("id") and (line.get("reviewed") or line.get("remembered")):
        return [int(product["id"])]
    return None


async def async_record_plan(planner: MealPlanner, plan: dict[str, Any]) -> dict[str, Any]:
    """The plan's answered lines as test cases, matched again now by name alone
    (not by the family's choice), with everything REMA answered."""
    recorder = copy.copy(planner)
    recording = _Recording(planner.client)
    recorder.client = recording  # type: ignore[assignment]
    recorder._search_cache = None

    async def by_name_only(line: dict[str, Any], at: Any) -> bool:
        return False

    # Matched as the test will: not by the family's choice nor the shared table.
    recorder._async_match_remembered = by_name_only  # type: ignore[method-assign]
    recorder._async_match_linked = by_name_only  # type: ignore[method-assign]
    cases: list[dict[str, Any]] = []
    for line in plan.get("shopping") or []:
        expect = answered(line)
        if expect is None:
            continue
        case: dict[str, Any] = {k: line.get(k) for k in _LINE_FIELDS}
        again = recorder._clean_line(dict(case))
        if again is None:
            continue
        case["expect"] = expect
        product = line.get("product") or {}
        if expect == "unknown":
            case["not"] = [int(product["id"])]
        else:
            case["packages"] = None  # the family may buy more than it needs
        cases.append(case)
        try:
            await recorder._async_match(again)
            # The answer itself, also when the search didn't find it.
            await recording.async_get_products([int(product["id"])])
        except RemaError:
            continue
    return {
        "version": 1,
        "shop": planner.shop,
        "recorded": dt_util.now().date().isoformat(),
        "plan": plan.get("week") or plan.get("start_date"),
        "searches": recording.searches,
        "products": list(recording.products.values()),
        "cases": cases,
    }

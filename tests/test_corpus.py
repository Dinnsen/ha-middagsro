"""The matcher against REMA's real search results.

``tests/corpus/rema_search.json`` holds what REMA's search returned for 130
queries one day in October 2026 (name, underline, department, category and
price of each product); ``expected.json`` what the family's list must get for
164 lines written the way the AI and web recipes write them: the product (one
of a few, where only the organic choice differs), nothing at all when REMA
has no such thing (cupnudler are not "oksekød i strimler"), or no line (a
recipe's heading, its tin, a remark).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro.api import Product
from custom_components.middagsro.ingredients import NEVER_KINDS, product_kinds
from custom_components.middagsro.mealplan import line_spec
from homeassistant.core import HomeAssistant

CORPUS_DIR = pathlib.Path(__file__).parent / "corpus"
CORPUS: dict[str, list[dict[str, Any]]] = json.loads(
    (CORPUS_DIR / "rema_search.json").read_text(encoding="utf-8")
)
CASES: list[dict[str, Any]] = json.loads((CORPUS_DIR / "expected.json").read_text(encoding="utf-8"))
BY_ID = {p["id"]: p for products in CORPUS.values() for p in products}


def corpus_product(raw: dict[str, Any]) -> Product:
    return Product(
        id=raw["id"],
        name=raw["name"],
        underline=raw["underline"],
        department=raw["department"],
        category=raw["category"],
        price=raw["price"],
        normal_price=raw["price"],
        compare_unit=raw["compare_unit"],
        compare_unit_price=raw["compare_unit_price"],
        is_advertised=False,
        is_campaign=False,
        price_valid_to=None,
        upcoming_price=None,
        upcoming_is_advertised=False,
        upcoming_from=None,
        is_organic=bool(raw["is_organic"]),
        labels=raw["labels"],
        image=None,
    )


async def corpus_search(query: str, limit: int = 15) -> list[Product]:
    """What REMA answered, with its fuzziness: a query not captured returns the
    results of the longest captured query it contains."""
    key = query.lower()
    if key not in CORPUS:
        found = [k for k in CORPUS if k in key or any(w.endswith(k) for w in key.split())]
        key = max(found, key=len) if found else key
    return [corpus_product(p) for p in CORPUS.get(key, [])][:limit]


async def corpus_products(ids: list[int], at: Any = None) -> list[Product]:
    return [corpus_product(BY_ID[i]) for i in ids if i in BY_ID]


@pytest.mark.parametrize("organic", ["none", "prefer"])
async def test_corpus_lines_get_the_right_product(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, organic: str
) -> None:
    """Every line of the corpus gets what the family expects, whatever the organic rule."""
    mock_client.async_search_products.side_effect = corpus_search
    mock_client.async_get_products.side_effect = corpus_products
    planner = init_integration.runtime_data.planner
    await init_integration.runtime_data.store.async_set_settings({"organic": organic})
    wrong: list[str] = []
    for case in CASES:
        line = planner._clean_line(case)
        label = f"{case['name']} ({case.get('amount')} {case.get('unit')})"
        if case["expect"] == "skip":
            if line is not None:
                wrong.append(f"{label}: on the list as {line['name']!r}, should be left out")
            continue
        assert line is not None, label
        await planner._async_match(line)
        product = line.get("product")
        if case["expect"] == "none":
            if product is not None:
                wrong.append(f"{label}: got {product['name']!r}, REMA has no such thing")
            elif line["confidence"] != "low":
                wrong.append(f"{label}: nothing found but confidence {line['confidence']}")
            continue
        if product is None:
            wrong.append(f"{label}: nothing found, wanted {case['expect']}")
        elif product["id"] not in case["expect"]:
            wrong.append(
                f"{label}: got {product['id']} {product['name']!r}, wanted {case['expect']}"
            )
        elif line["packages"] != case["packages"]:
            wrong.append(
                f"{label}: {line['packages']} × {product['name']!r}, wanted {case['packages']}"
            )
    assert not wrong, "\n".join(wrong)


async def test_corpus_never_buys_what_is_not_food(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """No ingredient line ever gets a ready meal, a snack, a drink or household goods."""
    mock_client.async_search_products.side_effect = corpus_search
    mock_client.async_get_products.side_effect = corpus_products
    planner = init_integration.runtime_data.planner
    for case in CASES:
        line = planner._clean_line(case)
        if line is None:
            continue
        await planner._async_match(line)
        product = line.get("product")
        if product is None:
            continue
        raw = BY_ID[product["id"]]
        kinds = product_kinds(raw["department"], raw["category"], raw["name"], raw["underline"])
        # Unless the line asks for that kind itself (a pizza, ice cream, peanuts).
        uncalled_for = (kinds or frozenset()) & NEVER_KINDS - line_spec(line).kinds
        assert not uncalled_for, f"{case['name']}: {raw['name']} is {sorted(uncalled_for)}"


def test_corpus_products_are_real() -> None:
    """Every expected product is in the captured results, with REMA's fields."""
    for case in CASES:
        if isinstance(case["expect"], list):
            for product_id in case["expect"]:
                assert product_id in BY_ID, f"{case['name']}: {product_id} not in the corpus"
    for products in CORPUS.values():
        for raw in products:
            assert {"id", "name", "underline", "department", "category", "price"} <= raw.keys()

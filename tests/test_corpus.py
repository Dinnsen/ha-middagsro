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

from collections.abc import Awaitable, Callable
import json
import os
import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import links as links_module
from custom_components.middagsro.api import Product
from custom_components.middagsro.ingredients import NEVER_KINDS, product_kinds
from custom_components.middagsro.links import link_name
from custom_components.middagsro.mealplan import line_spec
from homeassistant.core import HomeAssistant

CORPUS_DIR = pathlib.Path(__file__).parent / "corpus"
CORPUS: dict[str, list[dict[str, Any]]] = json.loads(
    (CORPUS_DIR / "rema_search.json").read_text(encoding="utf-8")
)
CASES: list[dict[str, Any]] = json.loads((CORPUS_DIR / "expected.json").read_text(encoding="utf-8"))
BY_ID = {p["id"]: p for products in CORPUS.values() for p in products}
# Plans a family saved as test cases ("Gem som testsag"): what REMA answered that
# day, and the products the family kept or chose (record.py).
RECORDED = sorted((CORPUS_DIR / "cases").glob("*.json"))


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


def searcher(
    searches: dict[str, list[dict[str, Any]]], by_id: dict[int, dict[str, Any]]
) -> tuple[Callable[..., Awaitable[list[Product]]], Callable[..., Awaitable[list[Product]]]]:
    """REMA as it answered, with its fuzziness: a query not captured returns the
    results of the longest captured query it contains."""

    async def search(query: str, limit: int = 15, at: Any = None) -> list[Product]:
        key = query.lower()
        if key not in searches:
            found = [k for k in searches if k in key or any(w.endswith(k) for w in key.split())]
            key = max(found, key=len) if found else key
        return [corpus_product(p) for p in searches.get(key, [])][:limit]

    async def products(ids: list[int], at: Any = None) -> list[Product]:
        return [corpus_product(by_id[i]) for i in ids if i in by_id]

    return search, products


corpus_search, corpus_products = searcher(CORPUS, BY_ID)


def recorded(path: pathlib.Path) -> tuple[list[dict[str, Any]], Any, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for products in data["searches"].values() for p in products}
    by_id.update({p["id"]: p for p in data.get("products") or []})
    return data["cases"], *searcher(data["searches"], by_id)


async def score(planner: Any, cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    """How each line does: right, wrong but sure (bought without asking: the worst),
    wrong and unsure (the family is asked), nothing found, the wrong count; and the
    lines the family is asked about at all."""
    result: dict[str, list[str]] = {
        k: [] for k in ("right", "sure_wrong", "unsure_wrong", "missing", "count", "unsure")
    }
    for case in cases:
        line = planner._clean_line(case)
        label = f"{case['name']} ({case.get('amount')} {case.get('unit')})"
        if case["expect"] == "skip":
            if line is None:
                result["right"].append(label)
            else:
                result["sure_wrong"].append(f"{label}: on the list as {line['name']!r}")
            continue
        assert line is not None, label
        await planner._async_match(line)
        product = line.get("product")
        sure = line["confidence"] == "high"
        if not sure:
            result["unsure"].append(label)
        got = f"{product['id']} {product['name']!r}" if product else "nothing"
        if product is not None and product["id"] in (case.get("not") or []):
            result["sure_wrong" if sure else "unsure_wrong"].append(f"{label}: got {got}, said no")
        elif case["expect"] == "unknown":
            result["right"].append(label)
        elif case["expect"] == "none":
            if product is not None or sure:
                bucket = "sure_wrong" if sure else "unsure_wrong"
                result[bucket].append(f"{label}: got {got} ({line['confidence']}), REMA has none")
            else:
                result["right"].append(label)
        elif product is None:
            result["missing"].append(f"{label}: nothing found, wanted {case['expect']}")
        elif product["id"] not in case["expect"]:
            bucket = "sure_wrong" if sure else "unsure_wrong"
            result[bucket].append(f"{label}: got {got}, wanted {case['expect']}")
        elif case.get("packages") is not None and line["packages"] != case["packages"]:
            result["count"].append(
                f"{label}: {line['packages']} × {got}, wanted {case['packages']}"
            )
        else:
            result["right"].append(label)
    return result


def report(title: str, result: dict[str, list[str]], total: int) -> None:
    """The numbers in the test log, and on the CI run's page."""
    right = len(result["right"])
    text = (
        f"| {title} | {right}/{total} ({100 * right / max(total, 1):.1f} %) "
        f"| {len(result['sure_wrong'])} | {len(result['unsure_wrong'])} "
        f"| {len(result['missing'])} | {len(result['count'])} | {len(result['unsure'])} |\n"
    )
    print(text)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        path = pathlib.Path(summary)
        head = (
            ""
            if "| Matching |" in (path.read_text(encoding="utf-8") if path.exists() else "")
            else (
                "| Matching | Rigtig vare | Sikker men forkert | Usikker og forkert "
                "| Intet fundet | Forkert antal | Spurgt |\n|---|---|---|---|---|---|---|\n"
            )
        )
        with path.open("a", encoding="utf-8") as out:
            out.write(head + text)


@pytest.mark.parametrize("links", [True, False], ids=["with_table", "text_only"])
@pytest.mark.parametrize("organic", ["none", "prefer"])
async def test_corpus_lines_get_the_right_product(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    organic: str,
    links: bool,
) -> None:
    """Every line of the corpus gets what the family expects, whatever the organic
    rule; with the shared table and by its name alone."""
    if not links:
        monkeypatch.setattr(links_module, "LINKS", {})
    mock_client.async_search_products.side_effect = corpus_search
    mock_client.async_get_products.side_effect = corpus_products
    planner = init_integration.runtime_data.planner
    await init_integration.runtime_data.store.async_set_settings({"organic": organic})
    result = await score(planner, CASES)
    report(f"oktober {organic} {'tabel' if links else 'navn'}", result, len(CASES))
    wrong = result["sure_wrong"] + result["unsure_wrong"] + result["missing"] + result["count"]
    assert not wrong, "\n".join(wrong)


@pytest.mark.parametrize("path", RECORDED, ids=[p.stem for p in RECORDED])
async def test_recorded_plans_are_never_sure_and_wrong(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    path: pathlib.Path,
) -> None:
    """A family's own plan, by name alone: a wrong product may be asked about, never
    bought without asking."""
    monkeypatch.setattr(links_module, "LINKS", {})
    cases, search, products = recorded(path)
    mock_client.async_search_products.side_effect = search
    mock_client.async_get_products.side_effect = products
    planner = init_integration.runtime_data.planner
    result = await score(planner, cases)
    report(path.stem, result, len(cases))
    assert not result["sure_wrong"], "\n".join(result["sure_wrong"])


def test_shared_table_agrees_with_the_corpus() -> None:
    """Every name the shared table knows is what the corpus expects for it."""
    table = links_module.LINKS["rema"]
    for case in CASES:
        ids = table.get(link_name(case["name"]))
        if ids and isinstance(case["expect"], list):
            assert set(ids) <= set(case["expect"]), case["name"]
        elif ids:
            pytest.fail(f"{case['name']}: in the table, but {case['expect']}")


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

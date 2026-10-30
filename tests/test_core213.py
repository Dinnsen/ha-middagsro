"""2.13: the AI names the catalogue entry, and needs are counted in base units."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import mealplan as mp, structures
from custom_components.middagsro.ingredients import CATALOG, catalogue_entry, words_are
from custom_components.middagsro.storage import clean_settings
from homeassistant.core import HomeAssistant

from .conftest import make_product


def test_catalogue_key() -> None:
    """The AI's key is an entry of the catalogue; the words may or may not say so."""
    assert catalogue_entry("Salat") is CATALOG["salat"]
    assert catalogue_entry("noget andet") is None
    assert catalogue_entry(None) is None
    assert words_are(CATALOG["salat"], {"hjertesalat"})
    assert words_are(CATALOG["pølser"], {"grillpølser"})
    assert not words_are(CATALOG["laurbærblade"], {"kaffirblade"})
    assert not words_are(CATALOG["forårsløg"], {"vårløg"})


def test_lines_with_the_ai_key() -> None:
    """Words the catalogue doesn't know are searched as the AI's key, and asked about;
    words it knows win over the key."""
    clean = mp.MealPlanner._clean_line
    spring = clean({"name": "Vårløg", "search": "vårløg", "key": "forårsløg", "amount": 1})
    assert spring is not None
    assert spring["key"] == "forårsløg"
    assert spring["catalog"] == "forårsløg"
    assert spring["guessed"] is True
    assert mp.line_spec(spring).entry is CATALOG["forårsløg"]  # also when matched again
    plain = clean({"name": "Vårløg", "search": "vårløg", "amount": 1})
    assert plain is not None
    assert "catalog" not in plain
    assert plain["key"] != "forårsløg"
    salad = clean({"name": "Hjertesalat", "key": "salat"})
    assert salad is not None
    assert salad["catalog"] == "salat"
    assert "guessed" not in salad
    words_win = clean({"name": "Laksefilet", "key": "torsk"})
    assert words_win is not None
    assert words_win["key"] == "laks"
    assert "catalog" not in words_win
    nonsense = clean({"name": "Kaffirblade", "key": "findes ikke"})
    assert nonsense is not None
    assert "catalog" not in nonsense


async def test_a_guessed_key_is_asked_about(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    onions = make_product(306680, "FORÅRSLØG", 6.0, department="Frugt & grønt", underline="1 BDT.")

    async def search(query: str, limit: int = 15, **kwargs: Any) -> list[Any]:
        return [onions] if "løg" in query else []

    mock_client.async_search_products.side_effect = search
    planner = init_integration.runtime_data.planner
    line = planner._clean_line(
        {"name": "Vårløg", "search": "vårløg", "key": "forårsløg", "amount": 1, "unit": "bdt"}
    )
    await planner._async_match(line)
    assert line["product"]["name"] == "FORÅRSLØG"
    assert line["confidence"] == "medium"


def test_prompt_and_structure_have_the_key() -> None:
    settings = clean_settings({})
    dates = mp.plan_dates(date(2026, 11, 1), 7, set())
    prompt = mp.build_prompt(
        settings=settings,
        dates=dates,
        catalog=None,
        offers=[],
        favorites_due=[],
        favorites_optional=[],
        recent_dishes=[],
    )
    assert "Varenøgler: " in prompt
    assert "hakket oksekød" in prompt.split("Varenøgler: ")[1]
    assert '"key": "laks"' in prompt
    lib = structures.schema_library()
    plan = structures.plan_structure(lib)
    base = {"name": "Laks", "amount": 600, "unit": "g", "search": "laks", "category": "Fisk"}

    def shopping(line: dict[str, Any]) -> dict[str, Any]:
        answer = {"title": "Uge 45", "summary": "", "days": [], "shopping": [line]}
        return plan(answer)["shopping"][0]  # type: ignore[no-any-return]

    assert shopping({**base, "key": "laks"})["key"] == "laks"
    assert shopping({**base, "key": None})["key"] is None
    assert "key" not in shopping(base)


def test_needs_in_every_unit() -> None:
    """A thing written as 300 g and as 1 pk is both; each is counted in packages."""
    beef = make_product(1, "HAKKET OKSEKØD", 40, underline="500 GR.")
    line: dict[str, Any] = {"name": "Hakket oksekød", "amount": 300, "unit": "g"}
    mp.add_amounts(line, {"amount": 1, "unit": "pk"})
    assert line["amount"] == 300
    assert line["need"] == {"g": 300, "pack": 1}
    assert mp.base_need(line) == {"g": 300, "pack": 1}
    assert mp.line_packages(line, beef) == 2  # 0.6 + 1 packs
    assert mp.packages_needed(300, "g", beef) == 1

    # Pieces to grams when the catalogue knows a piece: one unit, no need kept.
    onions: dict[str, Any] = {"name": "Løg", "amount": 2, "unit": "stk"}
    mp.add_amounts(onions, {"amount": 200, "unit": "g"}, 100)
    assert onions == {"name": "Løg", "amount": 400, "unit": "g"}

    # Something counted that a bag doesn't say: the bag still covers it.
    pita: dict[str, Any] = {"name": "Pitabrød", "amount": 2, "unit": "stk"}
    mp.add_amounts(pita, {"amount": 1, "unit": "pk"})
    assert mp.line_packages(pita, make_product(2, "PITA", 15, underline="375 GR.")) == 1
    assert mp.packages_needed(None, None, beef, need={"stk": 2}) == 1
    assert mp.base_need({"name": "Salt"}) == {}
    assert mp.base_need({"name": "x", "amount": 2, "unit": "spande"}) == {}


def test_grams_of_something_sold_per_piece() -> None:
    """600 g squash is two of 300 g; 500 g broccoli is one head of about 400 g."""
    squash = make_product(3, "SQUASH", 7, underline="1 STK. / SPANIEN KL. 1")
    assert mp.packages_needed(600, "g", squash, 300) == 2
    assert mp.packages_needed(500, "g", squash, 400) == 1
    assert mp.packages_needed(600, "g", squash) == 1  # what one weighs is unknown

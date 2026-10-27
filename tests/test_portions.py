"""Larger portions change food quantities, never the family's identity."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.dishes import household_portions
from custom_components.middagsro.storage import clean_settings

HOUSEHOLD = [{"role": "adult"}, {"role": "adult"}, {"role": "child", "age": 2}]


@pytest.mark.parametrize(
    "value,expected",
    [(100, 100), (125, 125), (150, 150), (200, 200), (130, 100), ("150", 150), ("bad", 100)],
)
def test_portion_setting(value: object, expected: int) -> None:
    assert clean_settings({"portion_percent": value})["portion_percent"] == expected


def test_household_and_leftovers() -> None:
    settings = clean_settings({"household": HOUSEHOLD, "portion_percent": 150})
    assert household_portions(settings) == 2.3
    assert mp.recipe_factor(settings, {"servings": 4}, {}) == pytest.approx(2.3 * 1.5 / 4)
    assert mp.recipe_factor(settings, {"servings": 4}, {"makes_leftovers": True}) == pytest.approx(
        2.3 * 1.5 * 2 / 4
    )


async def test_portions_scale_food_once_not_fixed_items(init_integration: MockConfigEntry) -> None:
    planner = init_integration.runtime_data.planner
    planner.store.settings = clean_settings(
        {
            "household": HOUSEHOLD,
            "portion_percent": 150,
            "must_haves": [{"name": "Mælk", "amount": 2}],
        }
    )
    raw = {
        "days": [
            {
                "date": "2026-10-18",
                "dish": "Risret",
                "servings": 4,
                "ingredients": [{"name": "Ris", "amount": "200 g"}],
                "steps": [],
            }
        ],
        "shopping": [
            {"name": "Ris", "search": "ris", "amount": 200, "unit": "g"},
            {"name": "Æg", "search": "æg", "amount": 2, "unit": "stk"},
            {"name": "Bouillon", "amount": 500, "unit": "ml"},
        ],
    }
    with patch.object(planner, "_async_price_lines", AsyncMock()):
        plan = await planner._async_build_plan(raw, [date(2026, 10, 18)], None, [])
    assert [line["amount"] for line in plan["shopping"]] == [300, 3, 1, 2]
    assert plan["days"][0]["ingredients"][0]["amount"] == "300 g"
    assert plan["days"][0]["servings"] == 6
    assert plan["portion_percent"] == 150
    assert raw["shopping"][0]["amount"] == 200
    assert raw["days"][0]["ingredients"][0]["amount"] == "200 g"
    prompt = mp.build_recipe_prompt(
        settings=clean_settings({"portion_percent": 200}), day=plan["days"][0], plan=plan
    )
    assert "150 %" in prompt and "ikke skalere dem igen" in prompt

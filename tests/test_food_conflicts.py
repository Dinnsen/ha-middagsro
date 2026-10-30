"""What the family can't eat must not be in a dish, a recipe or on the list."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.dishes import check_plan, food_conflicts
from homeassistant.core import HomeAssistant

from .conftest import make_plan


def test_food_conflicts_words() -> None:
    """The words that mean an allergen or an avoided food, and the ones that don't."""
    settings = {"allergies": ["milk", "nuts", "gluten"], "avoid": ["pork", "spicy"]}

    def rules(name: str) -> list[str]:
        return [rule for _name, rule in food_conflicts([name], settings)]

    assert rules("Piskefløde") == ["mælkeallergi"]
    assert rules("Laktosefri mælk") == ["mælkeallergi"]
    assert rules("Kokosmælk") == []
    assert rules("Havremælk") == []
    assert rules("Mandler") == ["nøddeallergi"]
    assert rules("Muskatnød") == []
    assert rules("Peanuts") == []
    assert rules("Pasta") == ["allergi over for gluten"]
    assert rules("Risnudler") == []
    assert rules("Glutenfri pasta") == []
    assert rules("Bacon") == ["ikke svinekød"]
    assert rules("Svinemørbrad") == ["ikke svinekød"]
    assert rules("Hakket oksekød") == []
    assert rules("Rød chili") == ["ikke stærk mad"]
    assert rules("Sweet chili sauce") == []
    assert rules("Rød peberfrugt") == []
    # Several rules at once, each named once.
    assert food_conflicts(["Flødeost", "Flødeost"], settings) == [("Flødeost", "mælkeallergi")]
    assert food_conflicts(["Æg"], {"allergies": ["egg"], "avoid": []}) == [("Æg", "ægallergi")]
    assert food_conflicts(["Honning", "Laks"], {"allergies": [], "avoid": ["animal_products"]}) == [
        ("Honning", "vegansk mad"),
        ("Laks", "vegansk mad"),
    ]
    assert food_conflicts(["Laks"], {"allergies": ["unknown"], "avoid": []}) == []
    assert food_conflicts(["Laks"], {}) == []


def test_check_plan_sees_allergens() -> None:
    """A dish built on cream, or a shopping line with it, is a problem for a milk allergy."""
    plan = make_plan()
    plan["days"][0]["ingredients"] = [{"name": "Piskefløde", "amount": "2 dl"}]
    plan["days"][2]["uses"] = ["Hakket oksekød", "Persille"]
    plan["shopping"][1]["name"] = "Bacon i tern"
    plan["days"][2]["uses"] = ["Bacon i tern"]
    settings = {"allergies": ["milk"], "avoid": ["pork"], "fixed_days": [], "leftover_days": 1,
                "min_vegetarian": 0, "max_vegetarian": 7}  # fmt: skip
    problems = check_plan(plan, settings, recent=[], due_ids=set())
    assert [p for p in problems if "mælkeallergi" in p] == [
        'søndag 2026-10-11: "Spaghetti bolognese" bruger Piskefløde, men familien har '
        "mælkeallergi – lav retten uden, eller vælg en anden ret"
    ]
    assert [p for p in problems if "svinekød" in p] == [
        'søndag 2026-10-13: "Kyllingewok med broccoli" bruger Bacon i tern, men familien har '
        "ikke svinekød – lav retten uden, eller vælg en anden ret"
    ]
    settings["allergies"], settings["avoid"] = [], []
    assert not [p for p in check_plan(plan, settings, recent=[], due_ids=set()) if "bruger" in p]


def test_recipe_problems_see_allergens() -> None:
    """An AI recipe with an allergen is sent back once."""
    raw: dict[str, Any] = {
        "ingredients": [{"name": "Fløde", "amount": "2 dl"}, {"name": "Løg", "amount": "1"}],
        "steps": ["Hak løget.", "Kog fløden."],
    }
    assert mp.recipe_problems(raw) == []
    assert mp.recipe_problems(raw, {"allergies": ["milk"], "avoid": []}) == [
        "Opskriften bruger Fløde, men familien har mælkeallergi: lav den uden, med noget "
        "andet i stedet."
    ]


async def test_recipe_extras_leave_allergens_out(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """What an AI recipe adds that the family can't eat never reaches the list."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    await store.async_set_settings({"allergies": ["milk"], "avoid": ["pork"]})
    plan = make_plan("extras")
    plan["days"][0]["ingredients"] = [
        {"name": "Fløde", "amount": "2 dl"},
        {"name": "Bacon", "amount": "100 g"},
        {"name": "Timian", "amount": "1 tsk"},
    ]
    planner._async_price_lines = AsyncMock()  # type: ignore[method-assign]
    await planner._async_recipe_extras(plan, [], None, None)
    assert [line["name"] for line in plan["shopping"]][3:] == ["Timian"]
    assert plan["days"][0]["uses"] == ["Timian"]

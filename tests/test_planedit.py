"""Tests for changing a meal plan: swapping a dish, basic items and added products."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.rema1000 import planedit as pe
from custom_components.rema1000.api import RemaError
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import make_plan, make_product

RECIPE = {
    "ingredients": [{"name": "kyllingebryst", "amount": "600 g"}],
    "steps": [{"text": "Steg kyllingen.", "minutes": 10}],
    "tip": "",
    "active_minutes": 20,
    "total_minutes": 30,
}
OPTIONS = {
    "options": [
        {"dish": "Kyllingewok", "type": "normal", "active_minutes": "20", "total_minutes": 25,
         "why": "Kylling på tilbud"},
        {"dish": "  "},
        "ikke en dict",
        {"dish": "Linsegryde", "type": "Vegetar", "active_minutes": "x"},
        {"dish": "Frikadeller"},
        {"dish": "Lasagne"},
    ]
}  # fmt: skip


class FakeAI:
    """Answers the AI tasks for swapping and recipes."""

    def __init__(self, **answers: Any) -> None:
        self.answers = answers
        self.prompts: dict[str, list[str]] = {}

    async def __call__(self, hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        task = kwargs["task_name"]
        self.prompts.setdefault(task, []).append(kwargs["instructions"])
        key = {"REMA 1000 andre retter": "options", "REMA 1000 ny ret": "items"}.get(task, "recipe")
        return SimpleNamespace(data=self.answers.get(key, RECIPE))


def plan_with_uses() -> dict[str, Any]:
    """A plan from 0.7.0, where every dish says which items it uses."""
    plan = make_plan("p", start="2026-10-18")
    sunday, monday, tuesday = plan["days"]
    sunday["uses"] = ["Hakket oksekød", "Spaghetti"]
    monday["uses"] = []
    tuesday["uses"] = ["Persille"]
    plan["shopping"].append(
        {"name": "LETMÆLK", "amount": 1, "unit": "pk", "search": "letmælk", "category": "Faste varer",
         "must_have": True, "product": None, "packages": 1, "cost": 10.0}
    )  # fmt: skip
    return plan


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan whose dishes say which items they use."""
    return {"plans": [plan_with_uses()]}


async def test_swap_options(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """Three other dishes; for a leftovers day, for the day it is from."""
    planner = init_integration.runtime_data.planner
    ai = FakeAI(options=OPTIONS)
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        result = await pe.async_swap_options(planner, "p", "2026-10-19")
    assert result["date"] == "2026-10-18"  # monday is sunday's leftovers
    assert result["dish"] == "Spaghetti bolognese"
    assert [o["dish"] for o in result["options"]] == ["Kyllingewok", "Linsegryde", "Frikadeller"]
    assert result["options"][0]["active_minutes"] == 20
    assert result["options"][1] == {"dish": "Linsegryde", "type": "vegetar", "active_minutes": 0,
                                    "total_minutes": 0, "why": ""}  # fmt: skip
    prompt = ai.prompts["REMA 1000 andre retter"][0]
    assert "dobbelt portion" in prompt
    assert "Kyllingewok med broccoli" in prompt  # not the week's other dishes
    assert "o0 | Hakket oksekød 8-12% | 40 kr. | 500 g" in prompt

    # No suggestions: an error.
    with (
        patch("homeassistant.components.ai_task.async_generate_data", new=FakeAI(options={})),
        pytest.raises(HomeAssistantError) as err,
    ):
        await pe.async_swap_options(planner, "p", "2026-10-18")
    assert err.value.translation_key == "swap_failed"
    for plan_id, day, key in (
        ("x", "2026-10-18", "plan_not_found"),
        ("p", "2026-01-01", "day_not_found"),
    ):
        with pytest.raises(ServiceValidationError) as invalid:
            await pe.async_swap_options(planner, plan_id, day)
        assert invalid.value.translation_key == key


async def test_swap_needs_ai(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Without an AI Task entity nothing can be suggested."""
    planner = init_integration.runtime_data.planner
    for call in (
        pe.async_swap_options(planner, "p", "2026-10-18"),
        pe.async_swap_dish(planner, "p", "2026-10-18", {"dish": "Lasagne"}),
    ):
        with pytest.raises(ServiceValidationError) as err:
            await call
        assert err.value.translation_key == "no_ai_task"


async def test_swap_dish(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """The new dish replaces the old one's items, and the recipes are written again."""
    planner = init_integration.runtime_data.planner
    items = {
        "add": [
            {"name": "Kyllingebryst", "amount": 600, "unit": "g", "search": "kyllingebryst",
             "category": "Kød", "offer": "o9"},
            {"name": "Persille", "amount": 1, "unit": "bundt", "search": "persille"},
            "ikke en dict",
        ],
        "uses": ["Kyllingebryst", "Persille", 3],
    }  # fmt: skip
    ai = FakeAI(items=items)
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        plan = await pe.async_swap_dish(
            planner,
            "p",
            "2026-10-19",
            {"dish": "Kyllingewok", "type": "normal", "total_minutes": 25},
        )
    names = {line["name"]: line for line in plan["shopping"]}
    # Hakket oksekød and spaghetti were only for the old dish; persille is shared.
    assert set(names) == {"Persille", "LETMÆLK", "Kyllingebryst"}
    assert names["Persille"]["amount"] == 2
    assert names["Kyllingebryst"]["product"]["id"] == 30002
    sunday, monday, _ = plan["days"]
    assert (sunday["dish"], sunday["uses"], sunday["total_minutes"]) == (
        "Kyllingewok",
        ["Kyllingebryst", "Persille"],
        30,  # the recipe's times win over the suggestion's
    )
    assert sunday["active_minutes"] == 20
    assert sunday["ingredients"] == RECIPE["ingredients"]
    assert monday["dish"] == "Rester af kyllingewok"
    assert monday["steps"][0]["text"] == "Varm resten af Kyllingewok op, og server den."
    assert plan["total"] == pytest.approx(45 + 10)
    prompt = ai.prompts["REMA 1000 ny ret"][0]
    assert "remove:" not in prompt  # the items are known
    assert "dobbelt portion" in prompt

    with pytest.raises(ServiceValidationError) as err:
        await pe.async_swap_dish(planner, "p", "2026-10-18", {"dish": " "})
    assert err.value.translation_key == "swap_failed"


async def test_swap_dish_in_an_older_plan(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """A plan without the dishes' items: the AI says which items the old dish had."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    old = make_plan("old", start="2026-10-18")
    old["catalog"] = None
    await store.async_add_plan(old)
    items = {"add": [], "uses": [], "remove": ["spaghetti", 4]}
    ai = FakeAI(items=items, recipe={"ingredients": [], "steps": []})
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        plan = await pe.async_swap_dish(planner, "old", "2026-10-20", {"dish": "Fiskefrikadeller"})
    assert [line["name"] for line in plan["shopping"]] == ["Hakket oksekød", "Persille"]
    assert "remove:" in ai.prompts["REMA 1000 ny ret"][0]
    assert "Ugens tilbud" not in ai.prompts["REMA 1000 ny ret"][0]  # no avis
    assert (plan["days"][2]["dish"], plan["days"][2]["steps"]) == ("Fiskefrikadeller", [])


def test_cooked_day_and_total() -> None:
    """Leftovers belong to the day they are from; totals follow the list."""
    plan = make_plan("p", start="2026-10-18")
    sunday, monday, tuesday = plan["days"]
    assert pe.cooked_day(plan, monday) is sunday
    assert pe.cooked_day(plan, tuesday) is tuesday
    loose = {"date": "2026-10-21", "type": "rester", "uses_leftovers_from": None}
    assert pe.cooked_day(plan, loose) is tuesday
    lonely = {"date": "2026-10-01", "type": "rester"}
    assert pe.cooked_day(plan, lonely) is lonely
    plan["budget"] = 30
    pe.update_total(plan)
    assert (plan["total"], plan["over_budget"]) == (40, True)


async def test_offers_for_a_plan(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """The plan's avis, or nothing."""
    planner = init_integration.runtime_data.planner
    assert await pe._async_offers(planner, {"catalog": None}) == []
    mock_client.async_get_offers.side_effect = RemaError("down")
    assert await pe._async_offers(planner, {"catalog": {"id": "cat-42"}}) == []


def test_pantry_words_and_uses() -> None:
    """The basic items, and which recipe ingredients are them."""
    assert pe.pantry_words("Salt, peber; olie og smør\nmel, salt") == [
        "salt", "peber", "olie", "smør", "mel"
    ]  # fmt: skip
    assert pe._uses_item("olie", "rapsolie")
    assert pe._uses_item("mel", "Hvedemel")
    assert pe._uses_item("olie", "Salt, peber og olie")
    assert not pe._uses_item("mel", "mælk")
    assert not pe._uses_item("smør", "smørbar")
    assert not pe._uses_item("", "smør")
    assert pe._sum_amounts(["25 g", "0,1 kg"]) == (125, "g")
    assert pe._sum_amounts(["2 dl", "1 l"]) == (1200, "ml")
    assert pe._sum_amounts(["25 g", "2 spsk"]) is None
    assert pe._sum_amounts(["25 g", "1 dl"]) is None
    assert pe._sum_amounts([]) is None


async def test_pantry_items(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """The basic items the recipes use, put on the list by the family's rules."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    await store.async_set_settings({"pantry": "salt, peber, smør og mel, eddike"})
    plan = store.get_plan("p")
    assert plan is not None
    plan["days"][0]["ingredients"] = [
        {"name": "smør", "amount": "25 g"},
        {"name": "hvedemel", "amount": "2 spsk"},
        {"name": "Salt og peber", "amount": ""},
    ]
    plan["days"][2]["ingredients"] = [{"name": "Smør", "amount": "50 g"}]
    needs = pe.pantry_needs(plan, store.settings["pantry"])
    assert [(n["name"], n["amount"], n["unit"]) for n in needs] == [
        ("salt", None, None), ("peber", None, None), ("smør", 75, "g"), ("mel", None, None)
    ]  # fmt: skip

    butter = make_product(1, "SMØR", 22.0, underline="250 GR. / LURPAK")
    flour = make_product(2, "HVEDEMEL", 11.0, underline="2 KG.")

    async def search(query: str, limit: int = 24, at: Any = None) -> list[Any]:
        return {"smør": [butter], "hvedemel": [flour]}.get(query, [])

    mock_client.async_search_products.side_effect = search
    line = await pe.async_add_pantry_item(planner, "p", "smør")
    assert (line["product"]["name"], line["amount"], line["unit"]) == ("SMØR", 75, "g")
    assert (line["category"], line["pantry"], line["added"]) == ("Basisvarer", "smør", True)
    flour_line = await pe.async_add_pantry_item(planner, "p", "Mel")
    assert flour_line["search"] == "hvedemel"  # the recipe's own word
    assert flour_line["product"]["name"] == "HVEDEMEL"
    salt = await pe.async_add_pantry_item(planner, "p", "salt")
    assert salt["product"] is None  # free text
    needs = pe.pantry_needs(plan, store.settings["pantry"])
    assert [n["on_list"] for n in needs] == [True, False, True, True]
    assert plan["total"] == pytest.approx(40 + 10 + 22 + 11)

    for plan_id, item, key in (("x", "smør", "plan_not_found"), ("p", "eddike", "line_not_found")):
        with pytest.raises(ServiceValidationError) as err:
            await pe.async_add_pantry_item(planner, plan_id, item)
        assert err.value.translation_key == key


async def test_add_and_remove_products(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A searched product goes on the main list or the later one, and can be removed."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    coffee = make_product(90010, "KAFFE", 42.0, underline="400 GR.")
    mock_client.async_get_products.return_value = [coffee]
    line = await pe.async_add_product(planner, "p", 90010, 2)
    assert (line["product"]["id"], line["packages"], line["cost"], line["buy_from"]) == (
        90010, 2, 84, None
    )  # fmt: skip
    plan = store.get_plan("p")
    assert plan is not None
    assert plan["total"] == pytest.approx(40 + 10 + 84)

    with pytest.raises(ServiceValidationError) as err:
        await pe.async_add_product(planner, "p", 90010, part="late")
    assert err.value.translation_key == "no_late_list"
    plan["shopping"][0]["buy_from"] = "2026-10-22"
    late = await pe.async_add_product(planner, "p", 90010, part="late")
    assert late["buy_from"] == "2026-10-22"

    mock_client.async_get_products.return_value = []
    with pytest.raises(ServiceValidationError) as err:
        await pe.async_add_product(planner, "p", 1)
    assert err.value.translation_key == "product_not_found"
    mock_client.async_get_products.side_effect = RemaError("down")
    with pytest.raises(HomeAssistantError):
        await pe.async_add_product(planner, "p", 1)
    with pytest.raises(ServiceValidationError):
        await pe.async_add_product(planner, "x", 1)

    await pe.async_remove_line(planner, "p", line["id"])
    assert line["id"] not in [item.get("id") for item in plan["shopping"]]
    assert plan["total"] == pytest.approx(40 + 10 + 42)
    for plan_id, line_id, key in (("p", "nope", "line_not_found"), ("x", "a", "plan_not_found")):
        with pytest.raises(ServiceValidationError) as err:
            await pe.async_remove_line(planner, plan_id, line_id)
        assert err.value.translation_key == key


async def _ws(client: Any, msg_id: int, **msg: Any) -> dict[str, Any]:
    await client.send_json({"id": msg_id, **msg})
    result: dict[str, Any] = await client.receive_json()
    return result


async def test_websocket_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """The panel's commands for changing a plan."""
    client = await hass_ws_client(hass)
    ai = FakeAI(options=OPTIONS, items={"add": [], "uses": []})
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        options = await _ws(client, 1, type="rema1000/swap/options", plan_id="p", date="2026-10-20")
        assert options["result"]["options"][0]["dish"] == "Kyllingewok"
        swapped = await _ws(client, 2, type="rema1000/swap", plan_id="p", date="2026-10-20",
                            option={"dish": "Kyllingewok"})  # fmt: skip
        assert swapped["result"]["days"][2]["dish"] == "Kyllingewok"

    pantry = await _ws(client, 3, type="rema1000/pantry", plan_id="p")
    assert pantry["result"] == []  # salt, peber … aren't in these recipes
    missing = await _ws(client, 4, type="rema1000/pantry", plan_id="x")
    assert missing["error"]["code"] == "rema1000_error"

    mock_client.async_get_products.return_value = [make_product(90010, "KAFFE", 42.0)]
    added = await _ws(client, 5, type="rema1000/plan/add", plan_id="p", product_id=90010)
    line_id = added["result"]["id"]
    removed = await _ws(client, 6, type="rema1000/plan/remove", plan_id="p", line_id=line_id)
    assert removed["result"] is True
    nothing = await _ws(client, 7, type="rema1000/plan/add", plan_id="p")
    assert not nothing["success"]
    pantry_add = await _ws(client, 8, type="rema1000/plan/add", plan_id="p", pantry="salt")
    assert pantry_add["error"]["code"] == "rema1000_error"  # no recipe uses salt

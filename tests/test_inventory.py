"""Real quantities, conservative subtraction and durable consumption receipts."""

from __future__ import annotations

import copy
import json
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.inventory import (
    FreezerInventory,
    apply_inventory,
    inventory,
    prompt_items,
)
from custom_components.middagsro.mealplan import fit_amounts

from .test_mealplan import SETTINGS, SHOPPING, SKIP, START, FakeAI, ai_answer


def item(name="Hakket oksekød", amount=800, unit="g", identity="beef"):
    return {"id": identity, "name": name, "amount": amount, "unit": unit}


def line(name="Hakket oksekød", amount=1000, unit="g", **extra):
    return {"id": "line", "name": name, "search": name, "amount": amount, "unit": unit, **extra}


def test_partial_full_and_no_double_subtraction():
    raw = {
        "id": "p",
        "shopping": [line(), line("Løg", 2, "stk")],
        "days": [{"ingredients": [{"name": "Hakket oksekød", "amount": "1000 g"}]}],
    }
    stock = [item(), item("Løg", 3, "stk", "onion")]
    original = copy.deepcopy(stock)
    assert apply_inventory(raw, stock)
    assert raw["shopping"][0]["amount"] == 200
    assert raw["shopping"][0]["need"] == {"g": 200}
    assert len(raw["shopping"]) == 1
    assert [i["amount"] for i in raw["freezer_used"]] == [800, 2]
    assert raw["days"][0]["ingredients"][0]["amount"] == "1000 g"
    assert stock == original
    assert not apply_inventory(raw, stock)
    assert raw["shopping"][0]["amount"] == 200


def test_no_guessing_variety_form_units_or_fixed_items():
    lines = [
        line("Hakket svinekød"),
        line("Oksekød i tern"),
        line("Tørret oregano"),
        line("Hakket oksekød", 2, "stk"),
        line(must_have=True),
        line(sent="today"),
        line(added=True),
        line(skipped=True),
    ]
    plan = {"shopping": copy.deepcopy(lines)}
    assert not apply_inventory(plan, [item(), item("Frisk oregano", 100, "g", "herb")])
    assert plan["shopping"] == lines


def test_mixed_needs_and_multiple_rows_only_spend_stock_once():
    plan = {"shopping": [line(amount=300, need={"g": 300, "pack": 1}), line(amount=600)]}
    assert apply_inventory(plan, [item(amount=700)])
    assert plan["shopping"][0]["need"] == {"pack": 1}
    assert plan["shopping"][1]["need"] == {"g": 200}
    assert plan["freezer_used"][0]["amount"] == 700


def test_recipe_fit_does_not_buy_freezer_amount_again():
    plan = {
        "shopping": [line(product={"id": 1, "underline": "400 G", "price": 30}, packages=3)],
        "days": [
            {
                "type": "normal",
                "dish": "Kødsovs",
                "ingredients": [{"name": "Hakket oksekød", "amount": "1000 g"}],
            }
        ],
    }
    apply_inventory(plan, [item()])
    plan["shopping"][0].update(packages=1, cost=30)
    fit_amounts(plan)
    assert plan["shopping"][0]["packages"] == 1


async def test_storage_conversion_confirmation_and_restart(hass):
    stock = inventory(hass)
    await stock.async_edit(None, "Hakket oksekød", 0.8, "kg")
    row = stock.items[0]
    assert row["amount"] == 800 and row["unit"] == "g"
    plan = {"id": "week", "shopping": [line(amount=600)]}
    apply_inventory(plan, stock.items)
    assert stock.items[0]["amount"] == 800
    await stock.async_consume(plan)
    assert stock.items[0]["amount"] == 200
    restored = FreezerInventory(hass)
    await restored.async_load()
    await restored.async_consume(plan)
    assert restored.items[0]["amount"] == 200
    await restored.async_edit(row["id"], "Hakket oksekød", 1, "kg")
    assert restored.items[0]["amount"] == 1000
    await restored.async_delete(row["id"])
    assert restored.items == []


@pytest.mark.parametrize(
    "name,amount,unit",
    [
        ("", 10, "g"),
        ("vand", 10, "g"),
        ("Kød", -1, "g"),
        ("Kød", float("nan"), "g"),
        ("Kød", float("inf"), "g"),
        ("Kød", 100001, "g"),
        ("Kød", 2, "pk"),
    ],
)
async def test_invalid_input(hass, name, amount, unit):
    with pytest.raises(ValueError):
        await inventory(hass).async_edit(None, name, amount, unit)
    assert inventory(hass).items == []


async def test_not_enough_or_changed_stock_does_not_partially_consume(hass):
    stock = inventory(hass)
    await stock.async_edit(None, "Hakket oksekød", 800, "g")
    await stock.async_edit(None, "Løg", 2, "stk")
    plan = {"id": "week", "shopping": [line(amount=700), line("Løg", 2, "stk")]}
    apply_inventory(plan, stock.items)
    onion = stock.items[1]
    await stock.async_delete(onion["id"])
    with pytest.raises(ValueError, match="ændret"):
        await stock.async_consume(plan)
    assert stock.items[0]["amount"] == 800
    assert stock.data["consumed"] == []


async def test_failed_save_does_not_deduct_in_memory(hass):
    stock = inventory(hass)
    await stock.async_edit(None, "Hakket oksekød", 800, "g")
    plan = {"id": "week", "shopping": [line()]}
    apply_inventory(plan, stock.items)
    with (
        patch.object(stock.store, "async_save", AsyncMock(side_effect=OSError("disk"))),
        pytest.raises(OSError),
    ):
        await stock.async_consume(plan)
    assert stock.items[0]["amount"] == 800
    assert not stock.data["consumed"]


async def test_websocket_edit_and_consume(hass, init_integration, hass_ws_client):
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "middagsro/inventory/edit", "name": "Løg", "amount": 2, "unit": "stk"}
    )
    assert (await client.receive_json())["success"]
    await client.send_json({"id": 2, "type": "middagsro/state"})
    state = (await client.receive_json())["result"]
    assert state["freezer_inventory"][0]["amount"] == 2
    plan = {"id": "test", "shopping": [line("Løg", 1, "stk")]}
    apply_inventory(plan, inventory(hass).items)
    init_integration.runtime_data.store.plans.insert(0, plan)
    await client.send_json({"id": 3, "type": "middagsro/inventory/consume", "plan_id": "test"})
    assert (await client.receive_json())["success"]
    assert inventory(hass).items[0]["amount"] == 1
    await client.send_json(
        {"id": 4, "type": "middagsro/inventory/delete", "item_id": inventory(hass).items[0]["id"]}
    )
    assert (await client.receive_json())["success"]
    assert not inventory(hass).items


async def test_generation_prompt_and_real_package_reduction(hass, init_integration, ai_task):
    planner = init_integration.runtime_data.planner
    stock = inventory(hass)
    await stock.async_edit(None, "Spaghetti", 1600, "g")
    planner.store.settings.update(SETTINGS)
    ai = FakeAI(json.dumps(ai_answer(mp.plan_dates(START, 7, {SKIP}), SHOPPING)))
    with patch("homeassistant.components.ai_task.async_generate_data", ai):
        plan = await planner.async_generate(START, {SKIP}, use_freezer=True)
    assert "RÅVARER I FRYSEREN" in ai.prompts[0]
    assert "Spaghetti: 1600 g" in ai.prompts[0]
    pasta = next(row for row in plan["shopping"] if row["name"] == "Spaghetti")
    assert pasta["amount"] == 400
    assert pasta["packages"] == 1
    assert plan["freezer_used"][0]["amount"] == 1600
    assert stock.items[0]["amount"] == 1600
    assert all(
        d["ingredients"][0]["amount"] == "500 g" for d in plan["days"] if d.get("ingredients")
    )
    fit_amounts(plan)
    assert pasta["packages"] == 1
    await planner.async_rematch_all(plan["id"])
    assert pasta["packages"] == 1


def test_prompt_empty_and_full_amounts():
    assert prompt_items([]) == ""
    text = prompt_items([item()])
    assert "HELE planen" in text and "FULDE mængder" in text


def dinner_plan():
    return {
        "id": "cooking",
        "shopping": [line(amount=800), line("Løg", 2, "stk")],
        "days": [
            {
                "date": "2026-11-01",
                "dish": "Pasta med kødsovs",
                "type": "normal",
                "ingredients": [
                    {"name": "Hakket oksekød", "amount": "400 g"},
                    {"name": "Løg", "amount": "1 stk"},
                ],
            },
            {
                "date": "2026-11-02",
                "dish": "Chili",
                "type": "normal",
                "ingredients": [
                    {"name": "Hakket oksekød", "amount": "400 g"},
                    {"name": "Løg", "amount": "1 stk"},
                ],
            },
            {"date": "2026-11-03", "dish": "Rester", "type": "rester", "ingredients": []},
        ],
    }


async def test_confirm_one_dish_with_individual_raw_materials(hass):
    stock = inventory(hass)
    await stock.async_edit(None, "Hakket oksekød", 800, "g")
    await stock.async_edit(None, "Løg", 2, "stk")
    beef_id, onion_id = [i["id"] for i in stock.items]
    plan = dinner_plan()
    assert apply_inventory(plan, stock.items)
    assert plan["shopping"] == []
    groups = plan["freezer_groups"]
    assert len(groups) == 2
    assert [i["amount"] for i in groups[0]["items"]] == [400, 1]
    assert stock.items[0]["amount"] == 800
    with pytest.raises(ValueError, match="én ret"):
        await stock.async_consume(plan)
    await stock.async_consume(plan, groups[0]["id"], [beef_id])
    assert [i["amount"] for i in stock.items] == [400, 2]
    # A copy in another shop and a moved dinner have the same durable receipt.
    copied = copy.deepcopy(plan)
    copied["days"][0]["date"] = "2026-11-04"
    await stock.async_consume(copied, groups[0]["id"], [beef_id, onion_id])
    assert [i["amount"] for i in stock.items] == [400, 2]
    await stock.async_consume(plan, groups[1]["id"], [])
    assert [i["amount"] for i in stock.items] == [400, 2]
    assert stock.data["confirmed"][groups[1]["id"]]["items"] == []
    restored = FreezerInventory(hass)
    await restored.async_load()
    await restored.async_consume(plan, groups[0]["id"], [beef_id])
    assert restored.items[0]["amount"] == 400


async def test_changed_recipe_and_invalid_confirmation_do_not_deduct(hass):
    stock = inventory(hass)
    await stock.async_edit(None, "Hakket oksekød", 800, "g")
    beef_id = stock.items[0]["id"]
    plan = dinner_plan()
    apply_inventory(plan, stock.items)
    group = plan["freezer_groups"][0]
    with pytest.raises(ValueError, match="findes ikke"):
        await stock.async_consume(plan, "missing", [beef_id])
    with pytest.raises(ValueError, match="Vælg"):
        await stock.async_consume(plan, group["id"])
    with pytest.raises(ValueError, match="Vælg"):
        await stock.async_consume(plan, group["id"], ["arbitrary"])
    plan["days"][0]["ingredients"][0]["amount"] = "600 g"
    with pytest.raises(ValueError, match="ændret"):
        await stock.async_consume(plan, group["id"], [beef_id])
    assert stock.items[0]["amount"] == 800
    assert not stock.data.get("confirmed")


async def test_per_dish_websocket_and_shared_state(hass, init_integration, hass_ws_client):
    stock = inventory(hass)
    await stock.async_edit(None, "Hakket oksekød", 800, "g")
    plan = dinner_plan()
    apply_inventory(plan, stock.items)
    init_integration.runtime_data.store.plans.insert(0, plan)
    group = plan["freezer_groups"][0]
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "middagsro/inventory/consume",
            "plan_id": plan["id"],
            "group_id": group["id"],
            "item_ids": [stock.items[0]["id"]],
        }
    )
    assert (await client.receive_json())["success"]
    await client.send_json({"id": 2, "type": "middagsro/state"})
    state = (await client.receive_json())["result"]
    assert state["freezer_inventory"][0]["amount"] == 400
    assert group["id"] in state["freezer_confirmed"]

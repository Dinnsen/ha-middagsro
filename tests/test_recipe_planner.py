"""2.14: a plan built on the week's ready recipes, priced with the avis."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import mealplan as mp, planedit as pe
from custom_components.middagsro.api import RemaError
from custom_components.middagsro.recipes import clean_recipe
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .test_candidates import offer
from .test_mealplan import SETTINGS, START, FakeAI, _generate, ai_answer

BEEF = {"name": "hakket oksekød", "amount": "500 g", "product": {"id": 30001, "underline": "500 GR. / DANSK"}}  # fmt: skip
NAMES = ("Chili con carne", "Kødsovs med kartofler", "Hakkebøf med løg", "Frikadeller", "Burger")


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """Settings without allergies, and five ready recipes with minced beef."""
    recipes = [
        clean_recipe({"name": name, "ingredients": [BEEF, {"name": "løg", "amount": "1 stk"}]})
        for name in NAMES
    ]
    for recipe in recipes:
        recipe["ingredients"][1]["product"] = {"id": 50003, "underline": "1 KG / SPANIEN"}
    return {"settings": {**SETTINGS, "allergies": []}, "recipes": recipes}


def test_new_dishes_and_waiting() -> None:
    plan = {
        "days": [
            {"date": "2026-10-18", "dish": "Tacos", "type": "normal"},
            {"date": "2026-10-19", "dish": "Lasagne", "type": "normal", "recipe_id": "r1"},
            {"date": "2026-10-20", "dish": "Rester", "type": "rester", "uses_leftovers_from": "x"},
            {"date": "2026-10-21", "dish": "Pizza", "type": "fast"},
            {"date": "2026-10-22", "dish": "Spiser ude", "type": "egen"},
        ]
    }
    assert [d["dish"] for d in mp.new_dish_days(plan, {})] == ["Tacos"]
    plan["days"][0]["new_dish"] = True
    assert mp.waiting_dishes(plan) == ["Tacos"]


def test_offer_swap_on_a_line() -> None:
    offers = [
        offer("Rød peber", 6, "1 stk."),
        offer("REMA 1000 Hakket dansk oksekød 15-18%", 35, "400 g"),
    ]
    from custom_components.middagsro.candidates import offer_kinds  # noqa: PLC0415

    by_kind = offer_kinds(offers)
    line: dict[str, Any] = {"name": "Hakket oksekød", "product_id": 30001, "offer": None}
    mp.apply_offer_swap(line, BEEF, by_kind, {30001: (50.0, False)}, offers)
    assert (line["product_id"], line["offer"], line["swapped_from"]) == (
        None,
        "o1",
        "hakket oksekød",
    )
    kept: dict[str, Any] = {"name": "Hakket oksekød", "product_id": 30001, "offer": None}
    mp.apply_offer_swap(kept, BEEF, by_kind, {30001: (40.0, True)}, offers)  # on offer itself
    assert kept["product_id"] == 30001
    mp.apply_offer_swap(kept, {**BEEF, "exact": True}, by_kind, {}, offers)
    assert kept["product_id"] == 30001


async def test_plan_on_the_weeks_recipes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    ai_task: str,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The AI chooses among the candidates; a dish that is none of them waits for
    approval, and the list is not sent before it is approved."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    ids = [r["id"] for r in store.recipes]
    answer = ai_answer(mp.plan_dates(START, 7), [])
    cooked = [d for d in answer["days"] if d["type"] != "rester"]
    for day, recipe_id in zip(cooked, ids[:4], strict=False):
        day["recipe_id"] = recipe_id
    ai = FakeAI(answer)
    await _generate(planner, ai)
    assert planner.status["state"] == "idle", planner.status
    prompt = ai.prompts[0]
    assert "UGENS KANDIDATER" in prompt and ids[0] in prompt
    assert "FAMILIENS OPSKRIFTSSAMLING" not in prompt
    plan = store.latest_plan
    assert plan is not None
    new = [d for d in plan["days"] if d.get("new_dish")]
    assert [d["dish"] for d in new] == [cooked[4]["dish"]]
    beef = next(line for line in plan["shopping"] if line.get("swapped_from"))
    assert beef["offer_name"] == "Hakket oksekød 8-12%"

    with pytest.raises(ServiceValidationError):
        await planner.async_send(plan["id"])
    await planner._async_send_when_ready(plan)  # automatic: waits too
    assert not plan.get("send_at")

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "middagsro/day/approve", "plan_id": plan["id"], "date": new[0]["date"]}
    )
    msg = await client.receive_json()
    assert msg["success"], msg
    day = next(d for d in msg["result"]["days"] if d["date"] == new[0]["date"])
    assert day["recipe_id"] and not day.get("new_dish")
    saved = next(r for r in store.recipes if r["id"] == day["recipe_id"])
    assert saved["name"] == new[0]["dish"]
    with pytest.raises(ServiceValidationError):
        await pe.async_approve_day(planner, plan["id"], new[0]["date"])
    sent = await planner.async_send(plan["id"], "all", strict=False)
    assert any(line.get("sent") for line in sent["shopping"])


async def test_too_many_new_dishes_and_too_few_candidates(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """More than two dishes outside the candidates is sent back to the AI; too few
    candidates, or the setting off, and the plan is made as before."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    ai = FakeAI(ai_answer(mp.plan_dates(START, 7), []))
    await _generate(planner, ai)
    assert len(ai.prompts) == mp.MAX_AI_ROUNDS
    assert "ikke blandt kandidaterne" in ai.prompts[1]

    store.recipes = store.recipes[:2]
    ai = FakeAI(ai_answer(mp.plan_dates(START, 7), []))
    await _generate(planner, ai)
    assert "UGENS KANDIDATER" not in ai.prompts[0]
    assert not any(d.get("new_dish") for d in store.latest_plan["days"])

    await store.async_set_settings({**store.settings, "recipe_planner": False})
    ai = FakeAI(ai_answer(mp.plan_dates(START, 7), []))
    await _generate(planner, ai)
    assert "UGENS KANDIDATER" not in ai.prompts[0]

    # Pricing the recipes fails: the plan is made as before.
    await store.async_set_settings({**store.settings, "recipe_planner": True})
    with patch(
        "custom_components.middagsro.candidates.async_candidates",
        AsyncMock(side_effect=RemaError("nede")),
    ):
        ai = FakeAI(ai_answer(mp.plan_dates(START, 7), []))
        await _generate(planner, ai)
    assert "UGENS KANDIDATER" not in ai.prompts[0]


async def test_rema_candidates_are_saved_when_chosen(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """A REMA recipe the AI chooses goes in the collection, as the day's recipe."""
    from custom_components.middagsro import rema_catalog as rc  # noqa: PLC0415

    from .test_rema_recipes import ENTITY, NOW  # noqa: PLC0415

    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    entity = copy.deepcopy(ENTITY)
    entity["fields"]["customForm"]["ingredientGroups"][0]["ingredients"].append(
        {"ingredient": "hakket oksekød", "amountOfContent": 500, "unitOfContent": "g",
         "digitalProduct": {"id": 2, "title": "OKSE", "is_basic_ingredient": False,
                            "active_product": {"id": 30001, "name": "HK. OKSEKØD",
                                               "underline": "500 GR. / DANSK", "prices": []}}}
    )  # fmt: skip
    entry = rc.entry_from(entity, 0, NOW)
    assert entry is not None
    planner.rema_catalog.recipes = {entry["slug"]: entry}
    answer = ai_answer(mp.plan_dates(START, 7), [])
    cooked = [d for d in answer["days"] if d["type"] != "rester"]
    for day, recipe_id in zip(
        cooked, [*(r["id"] for r in store.recipes[:3]), "rema1"], strict=False
    ):
        day["recipe_id"] = recipe_id
    ai = FakeAI(answer)
    await _generate(planner, ai)
    assert "rema1 | Kylling i cremet svampesauce med ris" in ai.prompts[0]
    plan = store.latest_plan
    assert plan is not None
    saved = next(r for r in store.recipes if r.get("rema_slug") == entry["slug"])
    assert any(d.get("recipe_id") == saved["id"] for d in plan["days"])

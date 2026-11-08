"""Packed lunches, weekly items used by the week, and the pantry's dates and surplus (#66)."""

from __future__ import annotations

from datetime import date
import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.inventory import (
    FreezerInventory,
    apply_inventory,
    inventory,
    prompt_items,
    surplus,
)
from custom_components.middagsro.lunches import (
    async_days_off,
    async_lunches,
    clean_ideas,
    lunch_prompt,
    must_have_lines,
)
from custom_components.middagsro.planedit import async_set_left
from custom_components.middagsro.storage import clean_settings
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import make_plan
from .test_mealplan import SETTINGS, SHOPPING, START, FakeAI, _generate, ai_answer

CALENDAR = "calendar.skole"


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """The family's settings and an earlier plan."""
    return {"settings": SETTINGS, "plans": [make_plan("old", start="2026-10-11")]}


def fake_calendar(hass: HomeAssistant, events: list[dict[str, Any]], fail: bool = False) -> None:
    """A calendar of days off, answering calendar.get_events."""
    hass.states.async_set(CALENDAR, "off", {"friendly_name": "Skole"})

    async def get_events(call: ServiceCall) -> dict[str, Any]:
        if fail:
            raise HomeAssistantError("offline")
        return {CALENDAR: {"events": events}}

    hass.services.async_register(
        "calendar", "get_events", get_events, supports_response=SupportsResponse.ONLY
    )


def test_settings_keep_groups_uses_and_lunches() -> None:
    """Weekly items keep a group and a use; packed lunch settings are kept sane."""
    settings = clean_settings(
        {
            "must_haves": [
                {"name": "Mælk", "mode": "week", "use": "5,5", "unit": "l", "group": "morgenmad"},
                {"name": "Kaffe", "mode": "week", "use": 0, "amount": 2},
                {"name": "Ost", "mode": "x", "group": "x", "unit": "x", "use": "mange"},
            ],
            "lunch_count": 99,
            "lunch_weekdays": ["0", "7", "x", 1],
            "lunch_calendar": CALENDAR,
            "lunch_ideas": 1,
        }
    )
    milk, coffee, cheese = settings["must_haves"]
    assert milk == {"name": "Mælk", "product_id": None, "amount": 1, "group": "morgenmad",
                    "mode": "week", "use": 5.5, "unit": "l"}  # fmt: skip
    assert coffee["mode"] == "packs"  # a use without an amount: packages as before
    assert coffee["amount"] == 2
    assert (cheese["mode"], cheese["group"], cheese["unit"], cheese["use"]) == (
        "packs", "", "stk", 0.0,
    )  # fmt: skip
    assert settings["lunch_count"] == 20
    assert settings["lunch_weekdays"] == ["0", "1"]
    assert settings["lunch_calendar"] == CALENDAR
    assert settings["lunch_ideas"] is True
    assert clean_settings({"lunch_calendar": "sensor.x"})["lunch_calendar"] == ""
    assert clean_settings({"lunch_weekdays": "1"})["lunch_weekdays"] == []


def test_weekly_item_lines_follow_the_packed_lunches() -> None:
    """Per packed lunch, by the week, and fewer or none in a short or holiday week."""
    items = [
        {"name": "Rugbrød", "mode": "lunch", "use": 0.25, "unit": "pk", "group": "madpakker"},
        {"name": "Pikantost", "mode": "packs", "amount": 2, "group": "madpakker"},
        {"name": "Mælk", "mode": "week", "use": 5.5, "unit": "l", "group": "morgenmad",
         "product_id": 20494},
        {"name": "Kaffe", "amount": 1},
    ]  # fmt: skip
    short = {"count": 2, "days": ["a", "b", "c"], "off": ["d", "e"], "lunches": 6, "usual_days": 5}
    bread, cheese, milk, coffee = must_have_lines(items, short)
    assert (bread["amount"], bread["unit"], bread["use_mode"]) == (1.5, "pk", "lunch")
    assert bread["use_note"] == "6 madpakker × 0,25 pk"
    assert bread["category"] == "Madpakker"
    assert (cheese["amount"], cheese["use_note"]) == (2, "3 af 5 skoledage")
    assert "use_mode" not in cheese
    assert (milk["amount"], milk["unit"], milk["use_total"]) == (5.5, "l", 5.5)
    assert milk["category"] == "Morgenmad"
    assert milk["use_note"] == "Bruger 5,5 l om ugen"
    assert milk["product_id"] == 20494
    assert (coffee["amount"], coffee["unit"], coffee["category"]) == (1, "pk", "Faste varer")
    assert "group" not in coffee
    # A holiday week: no packed lunch items at all.
    holiday = {**short, "days": [], "lunches": 0}
    assert [line["name"] for line in must_have_lines(items, holiday)] == ["Mælk", "Kaffe"]
    # No packed lunches set up: per lunch items are left out, the rest as before.
    names = [(line["name"], line["amount"]) for line in must_have_lines(items, None)]
    assert names == [("Pikantost", 2), ("Mælk", 5.5), ("Kaffe", 1)]


def test_lunch_prompt_and_ideas() -> None:
    lunch = {"count": 2, "days": ["a", "b"], "off": [], "lunches": 4, "usual_days": 5}
    text = lunch_prompt({"lunch_ideas": False}, lunch)
    assert "4 madpakker" in text
    assert "lunch_ideas" not in text
    assert "lunch_ideas" in lunch_prompt({"lunch_ideas": True}, lunch)
    assert lunch_prompt({}, None) == ""
    assert lunch_prompt({}, {**lunch, "lunches": 0}) == ""
    assert clean_ideas("ikke en liste") == []
    assert clean_ideas(["Rugbrød med æg", " ", None, "x" * 300]) == ["Rugbrød med æg", "x" * 200]


async def test_days_off_from_the_calendar(hass: HomeAssistant) -> None:
    """All-day events are days off; events at a time of day are not."""
    week = [date(2026, 10, d) for d in range(19, 24)]  # monday to friday
    assert await async_days_off(hass, CALENDAR, week) == set()  # no such calendar
    fake_calendar(
        hass,
        [
            {"start": "2026-10-19", "end": "2026-10-21", "summary": "Efterårsferie"},
            {"start": {"date": "2026-10-23"}, "summary": "Skolefri"},
            {"start": "2026-10-22T17:00:00+02:00", "end": "2026-10-22T19:00:00+02:00"},
            {"start": "2026-13-40", "end": "2026-13-41"},
            "ikke en begivenhed",
        ],
    )
    off = await async_days_off(hass, CALENDAR, week)
    assert off == {date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 23)}
    assert await async_days_off(hass, "", week) == set()


async def test_days_off_calendar_that_fails(hass: HomeAssistant) -> None:
    fake_calendar(hass, [], fail=True)
    assert await async_days_off(hass, CALENDAR, [date(2026, 10, 19)]) == set()


async def test_lunches_of_a_period(hass: HomeAssistant) -> None:
    window = [date(2026, 10, 18 + i) for i in range(7)]  # sunday to saturday
    assert await async_lunches(hass, {"lunch_count": 0}, window) is None
    assert await async_lunches(hass, {"lunch_count": 2, "lunch_weekdays": []}, window) is None
    fake_calendar(hass, [{"start": "2026-10-21", "end": "2026-10-22"}])
    settings = {"lunch_count": 2, "lunch_weekdays": ["0", "1", "2", "3", "4"],
                "lunch_calendar": CALENDAR}  # fmt: skip
    lunch = await async_lunches(hass, settings, window)
    assert lunch == {
        "count": 2,
        "days": ["2026-10-19", "2026-10-20", "2026-10-22", "2026-10-23"],
        "off": ["2026-10-21"],
        "lunches": 8,
        "usual_days": 5,
    }


async def test_plan_with_packed_lunches(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """A new plan buys the week's packed lunches and the milk the week uses."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    fake_calendar(hass, [{"start": "2026-10-21", "end": "2026-10-22"}])
    await store.async_set_settings(
        {
            **SETTINGS,
            "must_haves": [
                {"name": "Rugbrød", "product_id": 70001, "mode": "lunch", "use": 0.25,
                 "unit": "pk", "group": "madpakker"},
                {"name": "Letmælk", "product_id": 20494, "mode": "week", "use": 5.5, "unit": "l",
                 "group": "morgenmad"},
                {"name": "Hvidløg", "mode": "week", "use": 6, "unit": "stk"},
                {"name": "Pikantost", "amount": 2, "group": "madpakker"},
            ],
            "lunch_count": 2,
            "lunch_calendar": CALENDAR,
            "lunch_ideas": True,
        }
    )  # fmt: skip
    dates = mp.plan_dates(START, 7, set())
    answer = {**ai_answer(dates, SHOPPING), "lunch_ideas": ["Rugbrød med frikadelle", ""]}
    ai = FakeAI(json.dumps(answer))  # type: ignore[arg-type]
    await _generate(planner, ai)
    plan = store.latest_plan
    assert plan is not None
    assert "8 madpakker" in ai.prompts[0]
    assert "lunch_ideas" in ai.prompts[0]
    assert plan["lunch"]["lunches"] == 8
    assert plan["lunch"]["off"] == ["2026-10-21"]
    assert plan["lunch_ideas"] == ["Rugbrød med frikadelle"]
    weekly = [line for line in plan["shopping"] if line.get("must_have")]
    bread, milk, other, cheese = weekly
    assert (bread["amount"], bread["packages"], bread["category"]) == (2.0, 2, "Madpakker")
    assert (milk["product"]["id"], milk["packages"]) == (20494, 6)  # 5.5 l of 1 l bottles
    assert other["product"]["id"] == 50004  # found by name: 6 cloves of 3 a package
    assert (other["packages"], other["category"]) == (2, "Faste varer")
    assert cheese["amount"] == 2  # 4 of 5 school days: still the two packages
    assert cheese["use_note"] == "4 af 5 skoledage"


async def test_how_much_is_left(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Only the rest of a weekly item's use is bought; all of it left: not bought."""
    planner = init_integration.runtime_data.planner
    plan = make_plan("left")
    milk = {
        "id": "milk",
        "name": "Letmælk",
        "amount": 5.5,
        "unit": "l",
        "must_have": True,
        "use_mode": "week",
        "use_total": 5.5,
        "packages": 6,
        "cost": 65.7,
        "product": {"id": 20494, "underline": "1 LTR. / REMA 1000", "price": 10.95},
    }
    bread = {
        "id": "bread",
        "name": "Rugbrød",
        "amount": 2.5,
        "unit": "pk",
        "must_have": True,
        "use_mode": "lunch",
        "use_total": 2.5,
        "packages": 3,
        "product": None,
    }
    odd = {
        "id": "odd",
        "name": "Ost",
        "amount": 400,
        "unit": "g",
        "must_have": True,
        "use_mode": "week",
        "use_total": 400,
        "packages": 2,
        "product": {"id": 1, "underline": "2 STK.", "price": 20},
    }
    plain = {"id": "plain", "name": "Kaffe", "amount": 1, "unit": "pk", "must_have": True}
    sent = {**milk, "id": "sent", "sent": "2026-10-11T10:00:00"}
    plan["shopping"] = [milk, bread, odd, plain, sent]
    init_integration.runtime_data.store.plans.insert(0, plan)

    await async_set_left(planner, "left", "milk", 2)
    assert (milk["amount"], milk["packages"], milk["cost"], milk["left"]) == (3.5, 4, 43.8, 2)
    await async_set_left(planner, "left", "milk", 9)
    assert milk["skipped"] and milk["have"] and milk["amount"] == 0
    await async_set_left(planner, "left", "milk", 0)
    assert "skipped" not in milk
    assert milk["packages"] == 6
    await async_set_left(planner, "left", "bread", 1)
    assert (bread["amount"], bread["packages"], bread["cost"]) == (1.5, 2, None)
    await async_set_left(planner, "left", "odd", 100)
    assert (odd["amount"], odd["packages"], odd["cost"]) == (300, 2, 40)

    with pytest.raises(ServiceValidationError):
        await async_set_left(planner, "nope", "milk", 1)
    with pytest.raises(ServiceValidationError):
        await async_set_left(planner, "left", "plain", 1)
    with pytest.raises(ServiceValidationError):
        await async_set_left(planner, "left", "sent", 1)

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "middagsro/line/left", "plan_id": "left", "line_id": "milk", "left": 1.5}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert next(line for line in msg["result"]["shopping"] if line["id"] == "milk")["amount"] == 4


async def test_pantry_places_dates_and_adding(hass: HomeAssistant) -> None:
    """Items keep where they are and when to use them; the first to use come first."""
    stock = FreezerInventory(hass)
    await stock.async_edit(None, "Hakket oksekød", 500, "g", "fryser", None)
    await stock.async_edit(None, "Fløde", 250, "ml", "køleskab", "2026-11-10")
    await stock.async_edit(None, "Løg", 3, "stk", "garage", "")
    assert [i["name"] for i in stock.items] == ["Fløde", "Hakket oksekød", "Løg"]
    cream, beef, onion = stock.items
    assert (cream["place"], cream["best_before"]) == ("køleskab", "2026-11-10")
    assert beef["place"] == "fryser" and "best_before" not in beef
    assert "place" not in onion
    with pytest.raises(ValueError, match="gyldig dato"):
        await stock.async_edit(None, "Mælk", 1, "l", "", "i morgen")

    added = await stock.async_add("løg", 2, "stk")
    assert (added["name"], added["amount"]) == ("Løg", 5)
    cream2 = await stock.async_add("Fløde", 0.25, "l", best_before="2026-11-20")
    assert cream2["amount"] == 250  # another date: kept apart
    assert len(stock.items) == 4
    same = await stock.async_add("Fløde", 100, "ml", best_before="2026-11-10")
    assert same["amount"] == 350
    new = await stock.async_add("Peberfrugt", 2, "stk", "køleskab")
    assert new["place"] == "køleskab"
    with pytest.raises(ValueError):
        await stock.async_add("Mel", 1, "pk")

    text = prompt_items(stock.items)
    assert "Fløde: 350 ml (køleskab, brug senest 10/11)" in text
    assert "de første datoer først" in text
    assert "Hakket oksekød: 500 g (fryser)" in text
    assert "brug senest" not in prompt_items([beef])


def test_surplus_of_a_plan() -> None:
    """What the packages hold beyond the dishes' needs, by ingredient."""
    rice = {
        "name": "Basmati ris",
        "search": "basmati ris",
        "amount": 480,
        "unit": "g",
        "packages": 1,
        "product": {"underline": "1 KG. / REMA 1000"},
    }
    more_rice = {**rice, "amount": 700}
    plan = {
        "shopping": [
            rice,
            more_rice,
            {**rice, "amount": 990},  # 10 g left: too little to keep track of
            {**rice, "must_have": True},
            {**rice, "skipped": True},
            {**rice, "buy_at": "93f13"},
            {**rice, "product": {"underline": "Løs vægt"}},
            {**rice, "product": {"underline": "1 KG"}, "unit": "pk", "amount": 1},
            {**rice, "product": {"underline": "2 KASSER"}},
            {"name": "Vand", "search": "vand", "amount": 500, "unit": "ml", "packages": 2,
             "product": {"underline": "1 LTR."}},
            {"name": "Æg", "search": "æg", "amount": 2, "unit": "stk", "packages": 1,
             "product": {"underline": "10 STK."}},
        ]
    }  # fmt: skip
    assert surplus(plan) == [
        {"name": "basmati ris", "amount": 820.0, "unit": "g"},
        {"name": "æg", "amount": 8.0, "unit": "stk"},
    ]
    assert surplus({}) == []


async def test_surplus_to_the_pantry(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    plan = make_plan("stock")
    plan["shopping"] = [
        {"id": "r", "name": "Ris", "search": "ris", "amount": 480, "unit": "g", "packages": 1,
         "product": {"underline": "1 KG"}}
    ]  # fmt: skip
    init_integration.runtime_data.store.plans.insert(0, plan)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/inventory/surplus", "plan_id": "stock"})
    msg = await client.receive_json()
    assert msg["result"] == {"items": [{"name": "ris", "amount": 520.0, "unit": "g"}],
                             "stocked": None}  # fmt: skip
    assert not inventory(hass).items  # only shown
    await client.send_json(
        {"id": 2, "type": "middagsro/inventory/surplus", "plan_id": "stock", "apply": True}
    )
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["stocked"]
    assert inventory(hass).items[0]["amount"] == 520
    await client.send_json(
        {"id": 3, "type": "middagsro/inventory/surplus", "plan_id": "stock", "apply": True}
    )
    assert not (await client.receive_json())["success"]  # once
    await client.send_json({"id": 4, "type": "middagsro/inventory/surplus", "plan_id": "nope"})
    assert not (await client.receive_json())["success"]

    # The panel saves where an item is and when to use it.
    await client.send_json(
        {"id": 5, "type": "middagsro/inventory/edit", "name": "Fløde", "amount": 2, "unit": "dl"}
    )
    assert not (await client.receive_json())["success"]
    await client.send_json(
        {"id": 6, "type": "middagsro/inventory/edit", "name": "Fløde", "amount": 250,
         "unit": "ml", "place": "køleskab", "best_before": "2026-11-10"}
    )  # fmt: skip
    assert (await client.receive_json())["success"]
    assert inventory(hass).items[0]["best_before"] == "2026-11-10"


async def test_add_to_pantry_action(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """From a voice command or an automation: "vi har 2 peberfrugter"."""
    answer = await hass.services.async_call(
        DOMAIN,
        "add_to_pantry",
        {"name": "Peberfrugter", "amount": 2, "place": "køleskab"},
        blocking=True,
        return_response=True,
    )
    assert answer == {"name": "Peberfrugter", "amount": 2, "unit": "stk"}
    await hass.services.async_call(
        DOMAIN, "add_to_pantry", {"name": "peberfrugter", "amount": 1}, blocking=True
    )
    assert inventory(hass).items[0]["amount"] == 3
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "add_to_pantry",
            {"name": "Mælk", "amount": 1, "unit": "l", "best_before": "snart"},
            blocking=True,
        )


def test_used_weekly_items_take_from_the_pantry() -> None:
    """Milk used by the week is bought less when some is in the pantry."""
    milk = {"id": "m", "name": "Letmælk", "search": "letmælk", "amount": 5500, "unit": "ml",
            "must_have": True, "use_mode": "week"}  # fmt: skip
    coffee = {"id": "c", "name": "Kaffe", "search": "kaffe", "amount": 1, "unit": "pk",
              "must_have": True}  # fmt: skip
    plan = {"shopping": [milk, coffee]}
    stock = [{"id": "s", "name": "Letmælk", "amount": 2000, "unit": "ml"},
             {"id": "k", "name": "Kaffe", "amount": 1, "unit": "stk"}]  # fmt: skip
    assert apply_inventory(plan, stock)
    assert milk["amount"] == 3500
    assert coffee["amount"] == 1


async def test_lunches_of_a_generated_plan_without_lunches(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """Without packed lunches the plan has none, and the prompt says nothing of them."""
    planner = init_integration.runtime_data.planner
    dates = mp.plan_dates(START, 7, set())
    ai = FakeAI(json.dumps({**ai_answer(dates, SHOPPING), "lunch_ideas": ["Æg"]}))  # type: ignore[arg-type]
    await _generate(planner, ai)
    plan = init_integration.runtime_data.store.latest_plan
    assert plan is not None
    assert plan["lunch"] is None
    assert plan["lunch_ideas"] == []
    assert "madpakker" not in ai.prompts[0]

"""Shopping before the first dinner: prices, persisted plans and send scheduling (#76)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.middagsro import mealplan as mp, planedit as pe
from custom_components.middagsro.planning_dates import plan_shopping_day, shopping_day
from custom_components.middagsro.storage import RemaPlanStore, clean_settings
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import CURRENT, UPCOMING, fake_search, make_plan
from .test_mealplan import SHOPPING, FakeAI, ai_answer


@pytest.mark.parametrize(
    ("start", "weekday", "expected"),
    [
        ("2026-10-19", None, "2026-10-19"),
        ("2026-10-19", 6, "2026-10-18"),
        ("2026-10-19", 5, "2026-10-17"),
        ("2026-10-19", 0, "2026-10-19"),
        ("2026-10-18", 0, "2026-10-12"),
        ("2027-01-01", 6, "2026-12-27"),
    ],
)
def test_shopping_day(start: str, weekday: int | None, expected: str) -> None:
    assert (
        shopping_day(date.fromisoformat(start), {"shopping_weekday": weekday}).isoformat()
        == expected
    )
    assert plan_shopping_day({"start_date": start}).isoformat() == start
    assert (
        plan_shopping_day({"start_date": start, "shopping_date": expected}).isoformat() == expected
    )


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, None), ("", None), ("0", 0), (6, 6), ("bad", 0)]
)
def test_setting(raw: Any, expected: int | None) -> None:
    assert (
        clean_settings({"start_weekday": 0, "shopping_weekday": raw})["shopping_weekday"]
        == expected
    )
    assert clean_settings({})["shopping_weekday"] is None


@pytest.mark.parametrize(
    ("weekday", "shopping", "catalog"),
    [
        (6, date(2026, 10, 18), UPCOMING),
        (5, date(2026, 10, 17), CURRENT),
    ],
)
async def test_generation_and_update_use_the_buying_day(
    hass: HomeAssistant,
    init_integration: Any,
    mock_client: Any,
    ai_task: str,
    weekday: int,
    shopping: date,
    catalog: Any,
) -> None:
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    await store.async_set_settings({"start_weekday": 0, "shopping_weekday": weekday})
    start = date(2026, 10, 19)
    dates = mp.plan_dates(start, 7)
    seen = []

    async def search(query: str, limit: int = 24, at: datetime | None = None) -> list[Any]:
        seen.append(at)
        return await fake_search(query, limit)

    mock_client.async_search_products.side_effect = search
    mock_client.async_get_offers.reset_mock()
    ai = FakeAI(ai_answer(dates, SHOPPING[:2]))
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        plan = await planner.async_generate(start)
    assert plan["shopping_date"] == shopping.isoformat()
    assert plan["start_date"] == "2026-10-19"
    assert [d["date"] for d in plan["days"]] == [d.isoformat() for d in dates]
    assert plan["catalog"]["id"] == catalog.id
    assert mock_client.async_get_offers.call_args_list[0].args[0] == catalog.id
    expected_time = datetime(2026, 10, shopping.day, 10, tzinfo=UTC)
    assert seen and set(seen) == {expected_time}
    assert shopping.isoformat() in ai.prompts[0]
    # Add a product after generation: it must use the saved buying date too.
    with patch.object(mock_client, "async_get_products", AsyncMock(return_value=[])) as products:
        with pytest.raises(ServiceValidationError):
            await pe.async_add_product(planner, plan["id"], 999999)
        assert products.call_args.args[1] == expected_time
    # A changed preference applies to new plans, not this existing plan.
    await store.async_set_settings({"shopping_weekday": 2})
    seen.clear()
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        updated = await planner.async_generate(start, base_id=plan["id"])
    assert updated["shopping_date"] == shopping.isoformat()
    assert seen and set(seen) == {expected_time}
    loaded = RemaPlanStore(hass, init_integration.entry_id)
    await loaded.async_load()
    assert loaded.latest_plan["shopping_date"] == shopping.isoformat()


async def test_avis_limit_applies_to_shopping_not_dinners(
    hass: HomeAssistant,
    init_integration: Any,
    ai_task: str,
) -> None:
    planner = init_integration.runtime_data.planner
    await planner.store.async_set_settings({"start_weekday": 0, "shopping_weekday": 5})
    # The latest avis ends Saturday 24/10; dinners may begin Monday 26/10.
    dates = mp.plan_dates(date(2026, 10, 26), 7)
    with patch(
        "homeassistant.components.ai_task.async_generate_data", new=FakeAI(ai_answer(dates, []))
    ):
        plan = await planner.async_generate(dates[0])
    assert plan["shopping_date"] == "2026-10-24"
    assert plan["end_date"] == "2026-11-01"
    with pytest.raises(ServiceValidationError) as error:
        await planner.async_generate(date(2026, 11, 2))
    assert error.value.translation_key == "avis_not_out"


async def test_refresh_and_automatic_sends_use_saved_shopping_date(
    hass: HomeAssistant,
    init_integration: Any,
) -> None:
    planner = init_integration.runtime_data.planner
    plan = make_plan("shopping", start="2026-10-19")
    plan["shopping_date"] = "2026-10-18"
    await planner.store.async_add_plan(plan)
    with patch.object(planner, "_schedule_send") as schedule:
        planner._schedule_refreshes(plan)
        assert plan["refresh_at"] == mp.prices_from(date(2026, 10, 18)).isoformat()
        await planner._async_send_when_ready(plan)
        assert plan["send_at"] == plan["refresh_at"]
        assert [c.args[1] for c in schedule.call_args_list] == ["refresh_at", "send_at"]
    # The original weekday remains when the setting is absent on old plans.
    legacy = make_plan("legacy", start="2026-10-19")
    with patch.object(planner, "_schedule_send"):
        planner._schedule_refreshes(legacy)
    assert legacy["refresh_at"] == mp.prices_from(date(2026, 10, 19)).isoformat()


async def test_auto_generation_keeps_dinner_start_with_separate_shopping_day(
    hass: HomeAssistant,
    init_integration: Any,
) -> None:
    planner = init_integration.runtime_data.planner
    await planner.store.async_set_settings(
        {"auto_generate": True, "start_weekday": 0, "shopping_weekday": 6}
    )
    with patch.object(planner, "async_start_generation") as generate:
        planner.async_check_auto_generate(UPCOMING)
    assert generate.call_args.args[0] == date(2026, 10, 19)
    assert shopping_day(generate.call_args.args[0], planner.store.settings) == date(2026, 10, 18)

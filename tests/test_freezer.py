"""Batch cooking is independent of family percentages and the dinner calendar."""

from __future__ import annotations

import copy
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.middagsro.freezer import async_generate, async_portions, build_prompt
from custom_components.middagsro.storage import RemaPlanStore

from .conftest import make_plan


def answer(count=4):
    return {
        "days": [
            {
                "dish": f"Gryderet {i}",
                "servings": 4,
                "ingredients": [
                    {"name": "Hakket oksekød", "amount": "400 g"},
                    {"name": "Vand", "amount": "2 dl"},
                    {"name": "Salt", "amount": "1 tsk"},
                ],
                "steps": [{"text": "Brun kødet og tilsæt væsken.", "minutes": 5}],
                "tip": "Server med friskkogte ris.",
            }
            for i in range(count)
        ]
    }


async def test_portions_absolute_and_persisted_without_calendar_changes(init_integration):
    planner = init_integration.runtime_data.planner
    planner.store.settings.update(portion_percent=200, must_haves=[{"name": "Mælk", "amount": 2}])
    weekly = make_plan()
    await planner.store.async_add_plan(weekly)
    with (
        patch.object(planner, "_async_ask_ai", AsyncMock(return_value=answer())),
        patch.object(planner, "_async_price_lines", AsyncMock()),
    ):
        plan = await async_generate(planner, 4)
        assert plan["portion_percent"] == 100
        assert [d["servings"] for d in plan["days"]] == [4] * 4
        assert [(line["name"], line["amount"]) for line in plan["shopping"]] == [
            ("Hakket oksekød", 1600)
        ]
        day = plan["days"][0]
        await async_portions(planner, plan["id"], day["date"], 16)
        assert plan["days"][0]["ingredients"][0]["amount"] == "1600 g"
        assert plan["shopping"][0]["amount"] == 2800
        await async_portions(planner, plan["id"], day["date"], 8)
        assert plan["days"][0]["ingredients"][0]["amount"] == "800 g"
        assert plan["shopping"][0]["amount"] == 2000
        assert plan["days"][1]["servings"] == 4
        assert plan["days"][0]["base_ingredients"][0]["amount"] == "400 g"
    assert planner.store.latest_plan is weekly
    assert planner.store.plan_covering(date.fromisoformat(weekly["start_date"])) is weekly
    reloaded = RemaPlanStore(planner.hass, init_integration.entry_id)
    await reloaded.async_load()
    assert reloaded.get_plan(plan["id"])["days"][0]["servings"] == 8
    assert reloaded.latest_plan["id"] == weekly["id"]
    await reloaded.async_delete_plan(plan["id"])
    assert reloaded.get_plan(plan["id"]) is None
    assert reloaded.latest_plan["id"] == weekly["id"]


async def test_failed_reprice_and_started_transfer_preserve_plan(init_integration):
    planner = init_integration.runtime_data.planner
    with (
        patch.object(planner, "_async_ask_ai", AsyncMock(return_value=answer())),
        patch.object(planner, "_async_price_lines", AsyncMock()),
    ):
        plan = await async_generate(planner, 4)
    original = copy.deepcopy(plan)
    with (
        patch.object(planner, "_async_price_lines", AsyncMock(side_effect=ValueError("offline"))),
        pytest.raises(ValueError, match="offline"),
    ):
        await async_portions(planner, plan["id"], plan["days"][0]["date"], 16)
    assert plan == original
    plan["portions_locked"] = True
    with pytest.raises(ValueError, match="før varer sendes"):
        await async_portions(planner, plan["id"], plan["days"][0]["date"], 16)


@pytest.mark.parametrize("raw", [answer(3), {"days": []}, {"days": [{}] * 4}])
async def test_invalid_ai_answer_not_saved(init_integration, raw):
    planner = init_integration.runtime_data.planner
    with (
        patch.object(planner, "_async_ask_ai", AsyncMock(return_value=raw)),
        pytest.raises(ValueError),
    ):
        await async_generate(planner, 4)
    assert not planner.store.freezer_plans


def test_prompt_separates_sides_and_portion_percentage():
    prompt = build_prompt(
        {
            "portion_percent": 200,
            "allergies": ["mælk"],
            "avoid": ["fisk"],
            "allergies_other": "selleri",
            "avoid_other": "oliven",
            "wishes": "mild mad",
        },
        5,
        "chili",
    )
    assert "præcis 5" in prompt
    assert "præcis 4 portioner" in prompt
    assert "IKKE ris/pasta" in prompt
    assert "mælk" in prompt and "fisk" in prompt and "chili" in prompt
    assert "selleri" in prompt and "oliven" in prompt and "mild mad" in prompt


async def test_websocket_background_generation_and_portions(
    hass, init_integration, hass_ws_client, ai_task
):
    planner = init_integration.runtime_data.planner
    client = await hass_ws_client(hass)
    with (
        patch.object(planner, "_async_ask_ai", AsyncMock(return_value=answer(5))),
        patch.object(planner, "_async_price_lines", AsyncMock()),
    ):
        await client.send_json({"id": 1, "type": "middagsro/freezer/generate", "count": 5})
        assert (await client.receive_json())["success"]
        await planner._task
        assert planner.status["state"] == "idle"
        plan = planner.store.freezer_plans[0]
        await client.send_json(
            {
                "id": 2,
                "type": "middagsro/freezer/portions",
                "plan_id": plan["id"],
                "date": plan["days"][0]["date"],
                "portions": 16,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"]["days"][0]["servings"] == 16
        await client.send_json({"id": 3, "type": "middagsro/state"})
        response = await client.receive_json()
        assert response["result"]["freezer_plans"][0]["id"] == plan["id"]


async def test_priced_batch_can_be_sent_without_affecting_weekly_plan(
    init_integration, mock_client
):
    planner = init_integration.runtime_data.planner
    with patch.object(planner, "_async_ask_ai", AsyncMock(return_value=answer())):
        plan = await async_generate(planner, 4)
        await async_portions(planner, plan["id"], plan["days"][0]["date"], 16)
    line = plan["shopping"][0]
    assert line["product"] is not None
    assert line["amount"] == 2800
    assert line["packages"] >= 4
    await planner.async_send(plan["id"], "all")
    assert plan["portions_locked"]
    assert line["sent"]
    assert plan["sent_at"]
    assert planner.store.latest_plan is None
    mock_client.async_add_to_list.assert_awaited()


async def test_background_failure_reported(hass, init_integration, hass_ws_client, ai_task):
    planner = init_integration.runtime_data.planner
    client = await hass_ws_client(hass)
    with patch.object(planner, "_async_ask_ai", AsyncMock(side_effect=ValueError("offline"))):
        await client.send_json({"id": 1, "type": "middagsro/freezer/generate", "count": 4})
        assert (await client.receive_json())["success"]
        await planner._task
    assert planner.status["state"] == "error"
    assert not planner.store.freezer_plans


async def test_freezer_wishes_are_their_own(hass, init_integration, hass_ws_client, ai_task):
    """The freezer plan uses its own wishes (kept for next time), not the week's note."""
    planner = init_integration.runtime_data.planner
    planner.store.note = "Pizza fredag"
    client = await hass_ws_client(hass)
    ask = AsyncMock(return_value=answer())
    with (
        patch.object(planner, "_async_ask_ai", ask),
        patch.object(planner, "_async_price_lines", AsyncMock()),
    ):
        await client.send_json(
            {
                "id": 1,
                "type": "middagsro/freezer/generate",
                "count": 4,
                "note": "Gryderetter med kylling,\n ingen svampe",
            }
        )
        assert (await client.receive_json())["success"]
        await planner._task
        prompt = ask.await_args.args[0]
        assert "Gryderetter med kylling, ingen svampe" in prompt
        assert "Pizza fredag" not in prompt
        assert planner.store.freezer_note == "Gryderetter med kylling, ingen svampe"
        await client.send_json({"id": 2, "type": "middagsro/state"})
        assert (await client.receive_json())["result"]["freezer_note"] == planner.store.freezer_note
        # Without a note the kept wishes are used again.
        await async_generate(planner, 4)
        assert "Gryderetter med kylling" in ask.await_args.args[0]
    stored = RemaPlanStore(hass, init_integration.entry_id)
    await stored.async_load()
    assert stored.freezer_note == "Gryderetter med kylling, ingen svampe"


@pytest.mark.parametrize(
    ("error", "level"), [(ValueError("ingen plan"), "WARNING"), (RuntimeError("boom"), "ERROR")]
)
async def test_background_failure_logged(
    hass, init_integration, hass_ws_client, ai_task, caplog, error, level
):
    """An expected failure is a warning; an unexpected one is logged with its traceback."""
    planner = init_integration.runtime_data.planner
    client = await hass_ws_client(hass)
    with patch.object(planner, "_async_ask_ai", AsyncMock(side_effect=error)):
        await client.send_json({"id": 1, "type": "middagsro/freezer/generate", "count": 4})
        assert (await client.receive_json())["success"]
        await planner._task
    record = next(r for r in caplog.records if "freezer plan" in r.getMessage())
    assert record.levelname == level
    assert planner.status["state"] == "error"

"""Installed-shop selection, plan transfer and retained shopping receipts."""

from __future__ import annotations

import copy
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.middagsro.api import RemaConnectionError
from custom_components.middagsro.bilka import BILKA_ID
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.store_selection import (
    StoreSelection,
    async_switch,
    selected_entry,
    selection,
)
from homeassistant.util import dt as dt_util

from .conftest import make_plan


@pytest.fixture
async def second_entry(hass, init_integration, mock_client):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Bilka", unique_id="bilka-test", data={"store": BILKA_ID}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.middagsro.BilkaStoreClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    async def price(lines, offers):
        for i, line in enumerate(lines):
            assert not line.get("product_id") and not line.get("product")
            line.update(
                product={"id": 9000 + i, "name": line["name"], "price": 10}, packages=1, cost=10
            )

    with patch.object(
        entry.runtime_data.planner, "_async_price_lines", AsyncMock(side_effect=price)
    ):
        yield entry


async def ws(client, number, **message):
    await client.send_json({"id": number, **message})
    return await client.receive_json()


async def test_copy_and_remember_with_real_websocket(
    hass, init_integration, second_entry, hass_ws_client, mock_client
):
    source, target = init_integration, second_entry
    source.runtime_data.store.settings.update(
        household=[{"role": "adult"}, {"role": "child", "age": 2}], allergies_other="selleri"
    )
    target.runtime_data.store.settings["must_haves"] = [{"name": "Bilka-vare", "amount": 2}]
    plan = make_plan()
    plan["shopping"][0].update(product_id=30001, buy_at="some-other-shop")
    plan["shopping"][1]["sent"] = "2026-10-28T12:00:00+01:00"
    await source.runtime_data.store.async_add_plan(plan)
    original = copy.deepcopy(plan)
    client = await hass_ws_client(hass)
    state = (await ws(client, 1, type="middagsro/state"))["result"]
    assert {s["entry_id"] for s in state["stores"]} == {source.entry_id, target.entry_id}
    result = await ws(
        client,
        2,
        type="middagsro/store/switch",
        target_entry_id=target.entry_id,
        action="copy",
        remember=True,
        plan_id=plan["id"],
    )
    assert result["success"]
    copied = target.runtime_data.store.latest_plan
    assert copied["id"] == plan["id"]
    assert copied["shopping"][0]["id"] == plan["shopping"][0]["id"]
    assert copied["shopping"][0]["product"]["id"] == 9000
    assert copied["shopping"][1]["sent"]
    assert copied["total"] == 30
    assert plan == original
    assert target.runtime_data.store.settings["allergies_other"] == "selleri"
    assert target.runtime_data.store.settings["must_haves"][0]["name"] == "Bilka-vare"
    state = (await ws(client, 3, type="middagsro/state"))["result"]
    assert state["entry_id"] == target.entry_id
    assert state["shop"]["id"] == BILKA_ID
    assert state["store_switch_preference"] == "copy"
    again = StoreSelection(hass)
    await again.async_load()
    assert again.data["entry_id"] == target.entry_id and again.preference == "copy"
    assert (await ws(client, 4, type="middagsro/store/ask"))["success"]
    assert selection(hass).preference == "ask"
    mock_client.async_add_to_list.assert_not_awaited()


async def test_new_plan_preserves_history_without_running_ai(
    hass, init_integration, second_entry, hass_ws_client
):
    target = second_entry
    await target.runtime_data.store.async_add_plan(make_plan("old-target"))
    client = await hass_ws_client(hass)
    with patch.object(target.runtime_data.planner, "async_start_generation") as generate:
        result = await ws(
            client, 1, type="middagsro/store/switch", target_entry_id=target.entry_id, action="new"
        )
    assert result["success"]
    generate.assert_not_called()
    state = (await ws(client, 2, type="middagsro/state"))["result"]
    assert state["start_new_plan"]
    assert target.runtime_data.store.get_plan("old-target")
    await target.runtime_data.store.async_add_plan(make_plan("new-target"))
    assert not (await ws(client, 3, type="middagsro/state"))["result"]["start_new_plan"]
    assert selection(hass).preference == "ask"


async def test_failed_matching_does_not_switch_or_change_destination(
    hass, init_integration, second_entry
):
    source, target = init_integration, second_entry
    await source.runtime_data.store.async_add_plan(make_plan())
    settings = copy.deepcopy(target.runtime_data.store.settings)
    with (
        patch.object(
            target.runtime_data.planner,
            "_async_price_lines",
            AsyncMock(side_effect=RemaConnectionError("offline")),
        ),
        pytest.raises(RemaConnectionError),
    ):
        await async_switch(hass, source, target, "copy", True, "plan-1")
    assert selection(hass).data.get("entry_id") is None
    assert not target.runtime_data.store.plans
    assert target.runtime_data.store.settings == settings


async def test_repeat_transfer_preserves_sent_target_and_does_not_duplicate_plan(
    hass, init_integration, second_entry
):
    source, target = init_integration, second_entry
    await source.runtime_data.store.async_add_plan(make_plan())
    await async_switch(hass, source, target, "copy", False, "plan-1")
    target.runtime_data.store.latest_plan["shopping"][0]["sent"] = "already-sent"
    await async_switch(hass, source, target, "copy", False, "plan-1")
    assert len(target.runtime_data.store.plans) == 1
    assert target.runtime_data.store.latest_plan["shopping"][0]["sent"] == "already-sent"


async def test_default_dashboard_subscription_reloads_on_store_change(
    hass, init_integration, second_entry, hass_ws_client
):
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/subscribe"})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["entry_id"] == init_integration.entry_id
    await async_switch(hass, init_integration, second_entry, "new", False, None)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    assert (await client.receive_json())["event"] == {"reload": True}


async def test_invalid_destination_is_rejected(hass, init_integration, hass_ws_client):
    client = await hass_ws_client(hass)
    result = await ws(
        client, 1, type="middagsro/store/switch", target_entry_id="missing", action="new"
    )
    assert not result["success"]
    assert not selection(hass).data


async def test_saved_recipe_skus_are_not_copied_or_duplicated(hass, init_integration, second_entry):
    source, target = init_integration, second_entry
    plan = make_plan()
    plan["days"][0]["recipe_id"] = "source-recipe"
    source.runtime_data.store.recipes = [
        {
            "id": "source-recipe",
            "name": "Egen ret",
            "ingredients": [{"name": "Ris", "amount": "300 g", "product": {"id": 123}}],
        }
    ]
    await source.runtime_data.store.async_add_plan(plan)
    await async_switch(hass, source, target, "copy", False, plan["id"])
    assert len(target.runtime_data.store.recipes) == 1
    recipe = target.runtime_data.store.recipes[0]
    assert "product" not in recipe["ingredients"][0]
    assert target.runtime_data.store.latest_plan["days"][0]["recipe_id"] == recipe["id"]
    await async_switch(hass, source, target, "copy", False, plan["id"])
    assert len(target.runtime_data.store.recipes) == 1
    assert source.runtime_data.store.recipes[0]["ingredients"][0]["product"]["id"] == 123


async def test_freezer_plan_remains_a_freezer_plan(
    hass, init_integration, second_entry, hass_ws_client
):
    plan = {**make_plan("batch"), "kind": "freezer"}
    await init_integration.runtime_data.store.async_add_plan(plan)
    await async_switch(hass, init_integration, second_entry, "copy", False, "batch")
    assert not second_entry.runtime_data.store.plans
    assert second_entry.runtime_data.store.freezer_plans[0]["kind"] == "freezer"
    client = await hass_ws_client(hass)
    state = (await ws(client, 1, type="middagsro/state"))["result"]
    assert state["switched_plan"]["id"] == "batch"
    assert not state["start_new_plan"]


async def test_busy_and_missing_source_plan_leave_active_store_unchanged(
    hass, init_integration, second_entry
):
    with pytest.raises(ValueError, match="findes ikke"):
        await async_switch(hass, init_integration, second_entry, "copy", True, "unknown")
    task = MagicMock()
    task.done.return_value = False
    with (
        patch.object(init_integration.runtime_data.planner, "_task", task),
        pytest.raises(ValueError, match="Vent"),
    ):
        await async_switch(hass, init_integration, second_entry, "new", True, None)
    assert not selection(hass).data


async def test_copy_without_a_plan_opens_new_plan_and_selection_survives_removal(
    hass, init_integration, second_entry
):
    await async_switch(hass, init_integration, second_entry, "copy", True, None)
    assert selection(hass).data["start_new"]
    assert selection(hass).preference == "copy"
    assert selected_entry(hass, [init_integration]) is init_integration


async def test_copy_keeps_have_but_rechecks_rejected_product(hass, init_integration, second_entry):
    plan = make_plan()
    plan["shopping"][0].update(skipped=True, have=True, reviewed=True)
    plan["shopping"][1].update(skipped=True, reviewed=True)
    await init_integration.runtime_data.store.async_add_plan(plan)
    await async_switch(hass, init_integration, second_entry, "copy", False, plan["id"])
    copied = second_entry.runtime_data.store.latest_plan
    assert copied["shopping"][0]["have"] and copied["shopping"][0]["skipped"]
    assert not copied["shopping"][1].get("skipped")
    assert copied["total"] == 20

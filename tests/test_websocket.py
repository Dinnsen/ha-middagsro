"""Tests for the websocket commands used by the panel."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro.api import RemaError
from homeassistant.core import HomeAssistant

from .conftest import make_plan


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """One stored plan and a favourite dish."""
    return {
        "plans": [make_plan()],
        "favorites": [{"id": "fav1", "text": "Lasagne", "frequency": "monthly", "last_used": None}],
    }


async def _ws(client: Any, msg_id: int, **msg: Any) -> dict[str, Any]:
    await client.send_json({"id": msg_id, **msg})
    result: dict[str, Any] = await client.receive_json()
    return result


async def test_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """Everything the panel shows."""
    client = await hass_ws_client(hass)
    msg = await _ws(client, 1, type="middagsro/state")
    assert msg["success"]
    state = msg["result"]
    assert state["entry_id"] == init_integration.entry_id
    assert state["latest_plan"]["id"] == "plan-1"
    assert state["plans"][0]["dishes"][0] == "Spaghetti bolognese"
    assert state["favorites"][0]["text"] == "Lasagne"
    assert state["ai_entities"] == [{"entity_id": ai_task, "name": "Assistant"}]
    assert state["catalogs"]["current"]["label"] == "Uge 42"
    assert state["rema_list"]["total"] == 21.9
    assert "fish" in state["options"]["allergies"]
    assert state["default_start"] == "2026-10-18"

    calls = mock_client.async_get_primary_list.await_count
    msg = await _ws(client, 2, type="middagsro/state", refresh=True)
    assert msg["success"]
    assert mock_client.async_get_primary_list.await_count == calls + 1

    msg = await _ws(client, 3, type="middagsro/state", entry_id="missing")
    assert not msg["success"]
    assert msg["error"]["code"] == "middagsro_error"


async def test_plans(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Read, delete and regenerate recipes of plans."""
    client = await hass_ws_client(hass)
    msg = await _ws(client, 1, type="middagsro/plan", plan_id="plan-1")
    assert msg["result"]["title"] == "Madplan uge 42"
    msg = await _ws(client, 2, type="middagsro/plan", plan_id="nope")
    assert not msg["success"]

    planner = init_integration.runtime_data.planner
    with patch.object(planner, "async_regenerate_recipe", return_value={"date": "2026-10-11"}):
        msg = await _ws(client, 3, type="middagsro/recipe", plan_id="plan-1", date="2026-10-11")
    assert msg["result"] == {"date": "2026-10-11"}

    assert hass.states.get("sensor.middagsro_meal_plan").state != "none"  # type: ignore[union-attr]
    msg = await _ws(client, 4, type="middagsro/plan/delete", plan_id="plan-1")
    assert msg["success"]
    assert init_integration.runtime_data.store.plans == []
    await hass.async_block_till_done()
    assert hass.states.get("sensor.middagsro_meal_plan").state == "none"  # type: ignore[union-attr]


async def test_settings_and_favorites(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Settings are cleaned and saved; favourites can be changed."""
    client = await hass_ws_client(hass)
    msg = await _ws(client, 1, type="middagsro/settings", settings={"budget": "650", "days": 99})
    assert msg["result"]["budget"] == 650
    assert msg["result"]["days"] == 14

    msg = await _ws(
        client, 2, type="middagsro/favorite/save", favorite={"text": "Tacos", "frequency": "weekly"}
    )
    new_id = msg["result"]["id"]
    msg = await _ws(
        client, 3, type="middagsro/favorite/save", favorite={"id": new_id, "text": "Fisketacos"}
    )
    assert msg["result"]["frequency"] == "inspiration"
    msg = await _ws(client, 4, type="middagsro/favorite/save", favorite={"text": " "})
    assert not msg["success"]
    msg = await _ws(client, 5, type="middagsro/favorite/delete", favorite_id=new_id)
    assert msg["success"]
    assert [f["id"] for f in init_integration.runtime_data.store.favorites] == ["fav1"]


async def test_generate_and_send(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Start a plan with skipped days, and send a plan."""
    client = await hass_ws_client(hass)
    planner = init_integration.runtime_data.planner
    with patch.object(planner, "async_start_generation") as start:
        msg = await _ws(
            client,
            1,
            type="middagsro/generate",
            start_date="2026-10-18",
            skip_dates=["2026-10-19", "bad"],
        )
    assert not msg["success"]  # "bad" is not a date
    with patch.object(planner, "async_start_generation") as start:
        msg = await _ws(
            client, 2, type="middagsro/generate", start_date="2026-10-18", skip_dates=["2026-10-19"]
        )
    assert msg["success"]
    assert start.call_args.kwargs["skip"] == {start.call_args.args[0].replace(day=19)}

    msg = await _ws(client, 3, type="middagsro/send", plan_id="plan-1")
    assert msg["result"] == {"plan_id": "plan-1", "status": "sent"}

    mock_client.async_add_to_list.side_effect = RemaError("HTTP 500")
    msg = await _ws(client, 4, type="middagsro/send")
    assert not msg["success"]
    assert "HTTP 500" in msg["error"]["message"]


async def test_products_and_list(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Search, favourites, add one product and clear the list."""
    client = await hass_ws_client(hass)
    msg = await _ws(client, 1, type="middagsro/search", query="broccoli")
    assert [p["name"] for p in msg["result"]] == ["BROCCOLI", "ØKO. BROCCOLI"]

    msg = await _ws(client, 2, type="middagsro/favorites", force=True)
    mock_client.async_get_favorites.assert_awaited_with(force=True)
    assert len(msg["result"]["products"]) == 3

    msg = await _ws(client, 3, type="middagsro/list/add", product_id=20494, amount=500)
    assert msg["success"]
    assert mock_client.async_add_to_list.call_args.kwargs["amount"] == 99

    msg = await _ws(client, 4, type="middagsro/list/clear")
    assert msg["result"] == {"removed": 3}
    mock_client.async_delete_items.assert_awaited_with(777, [1, 2, 3])


async def test_running_plan_and_note(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Tonight's plan is sent when it is not the newest; wishes can be saved."""
    store = init_integration.runtime_data.store
    store.plans[:] = [make_plan("next", start="2026-10-18"), make_plan("now", start="2026-10-13")]
    client = await hass_ws_client(hass)
    state = (await _ws(client, 1, type="middagsro/state"))["result"]
    assert state["latest_plan"]["id"] == "next"
    assert state["current_plan"]["id"] == "now"
    assert state["note"] == ""

    msg = await _ws(client, 2, type="middagsro/note", text="  Pizza fredag ")
    assert msg["result"] == {"note": "Pizza fredag"}
    store.plans[:] = [make_plan("now", start="2026-10-13")]
    state = (await _ws(client, 3, type="middagsro/state"))["result"]
    assert state["current_plan"] is None  # the newest plan has tonight's dinner
    assert state["note"] == "Pizza fredag"


async def test_favorite_weeks(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Favourites on offer this week and next week, with this week as a fallback."""
    client = await hass_ws_client(hass)
    result = (await _ws(client, 1, type="middagsro/favorites"))["result"]
    assert result["week"] == "current"
    assert result["fallback"] is False
    assert result["catalog"]["label"] == "Uge 42"
    assert len(result["products"]) == 3
    assert result["on_offer"] == []

    result = (await _ws(client, 2, type="middagsro/favorites", week="next"))["result"]
    assert result["catalog"]["label"] == "Uge 43"
    assert result["fallback"] is False

    # Until next week's avis is out, next week shows this week's offers.
    offers = init_integration.runtime_data.offers.data
    assert offers is not None
    offers.upcoming = None
    result = (await _ws(client, 3, type="middagsro/favorites", week="next", force=True))["result"]
    assert result["fallback"] is True
    assert result["catalog"]["label"] == "Uge 42"

    msg = await _ws(client, 4, type="middagsro/favorites", week="later")
    assert not msg["success"]

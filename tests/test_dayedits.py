"""2.14: taking a skipped day back, a day written by hand, and taking what was
sent off the shop's list again when it leaves the plan."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import planedit as pe
from custom_components.middagsro.api import RemaError
from custom_components.middagsro.dishes import is_cooked
from custom_components.middagsro.mealplan import list_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import list_item, make_list, make_plan

SENT = "2026-10-17T10:00:00+02:00"


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan sent to REMA's list, whose dishes say which items they use."""
    plan = make_plan("p", start="2026-10-18", status="sent")
    sunday, monday, tuesday = plan["days"]
    sunday["uses"] = ["Hakket oksekød", "Spaghetti"]
    monday["uses"] = []
    tuesday["uses"] = ["Persille"]
    for i, line in enumerate(plan["shopping"]):
        line.update(id=f"l{i}", sent=SENT)
    return {"plans": [plan]}


def _names(plan: dict[str, Any]) -> list[str]:
    return [line["name"] for line in plan["shopping"]]


def test_list_entry() -> None:
    """A line as the shop's list has it: a product, the avis's name, or the name and amount."""
    assert list_entry({"name": "Kød", "product": {"id": 5}, "packages": 2}) == {
        "product_id": 5,
        "amount": 2,
    }
    assert list_entry({"name": "x", "avis_item": {"name": "Æbler"}, "packages": 1}) == {
        "name": "Æbler",
        "amount": 1,
    }
    assert list_entry({"name": "Persille", "amount": 1.0, "unit": "bundt"}) == {
        "name": "Persille (1 bundt)",
        "amount": 1,
    }
    assert list_entry({"name": "Spaghetti", "amount": 1, "unit": "pk", "packages": 2}) == {
        "name": "Spaghetti",
        "amount": 2,
    }


async def test_skip_and_take_back(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A skipped day's items come off REMA's list (only what was sent, never what is
    bought), and taking the day back brings the dish, its items and its leftovers back."""
    planner = init_integration.runtime_data.planner
    mock_client.async_get_primary_list = AsyncMock(
        return_value=make_list(
            list_item(1, "HK. OKSEKØD 8-12%", amount=3, product_id=30001),
            list_item(2, "Spaghetti", amount=1),
            list_item(3, "Persille (1 bundt)", bought=True),
        )
    )
    mock_client.async_update_item.reset_mock()
    mock_client.async_delete_items.reset_mock()
    plan = await pe.async_clear_day(planner, "p", "2026-10-18", skip=True)
    assert [d["date"] for d in plan["days"]] == ["2026-10-19", "2026-10-20"]
    assert plan["days"][0]["type"] == "tom"  # its leftovers went with it
    assert _names(plan) == ["Persille"]
    assert plan["skipped"] == ["2026-10-18"]
    mock_client.async_update_item.assert_awaited_once_with(777, 1, amount=2)
    mock_client.async_delete_items.assert_awaited_once_with(777, [2])

    plan = await pe.async_restore_day(planner, "p", "2026-10-18")
    assert [d["date"] for d in plan["days"]] == ["2026-10-18", "2026-10-19", "2026-10-20"]
    sunday, monday, _ = plan["days"]
    assert sunday["dish"] == "Spaghetti bolognese"
    assert (monday["type"], monday["uses_leftovers_from"]) == ("rester", "2026-10-18")
    assert sorted(_names(plan)) == ["Hakket oksekød", "Persille", "Spaghetti"]
    back = [line for line in plan["shopping"] if line["name"] != "Persille"]
    assert not any(line.get("sent") for line in back)  # to be sent again
    assert plan["skipped"] == [] and plan["skipped_days"] == {}
    with pytest.raises(ServiceValidationError):
        await pe.async_restore_day(planner, "p", "2026-10-18")
    with pytest.raises(ServiceValidationError):
        await pe.async_restore_day(planner, "nope", "2026-10-18")

    # Skipped before the day was kept aside: it comes back empty, for a new dish.
    plan["skipped"] = ["2026-10-21"]
    plan = await pe.async_restore_day(planner, "p", "2026-10-21")
    added = plan["days"][-1]
    assert (added["date"], added["weekday"], added["type"], added["dish"]) == (
        "2026-10-21",
        "onsdag",
        "tom",
        "",
    )


async def test_take_back_keeps_a_new_leftovers_dish(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A leftovers day that got a dish of its own meanwhile keeps it; a Mealie entry
    not removed yet is kept."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    store.get_plan("p")["days"][0]["mealie_entry"] = 42
    plan = await pe.async_clear_day(planner, "p", "2026-10-18", skip=True)
    assert plan["skipped_entries"] == [42]
    plan["days"][0].update(dish="Omelet", type="normal")
    plan = await pe.async_restore_day(planner, "p", "2026-10-18")
    assert plan["days"][1]["dish"] == "Omelet"
    assert plan["days"][0]["mealie_entry"] == 42
    assert plan["skipped_entries"] == []


async def test_written_day(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A day written by hand: no dinner, so the dish's own items leave the list."""
    planner = init_integration.runtime_data.planner
    mock_client.async_get_primary_list = AsyncMock(return_value=make_list())
    plan = await pe.async_set_day_text(planner, "p", "2026-10-20", "  Skolefest   i  hallen ")
    tuesday = plan["days"][2]
    assert (tuesday["dish"], tuesday["type"], tuesday["ingredients"]) == (
        "Skolefest i hallen",
        "egen",
        [],
    )
    assert not is_cooked(tuesday)
    assert "Persille" not in _names(plan)
    with pytest.raises(ServiceValidationError):
        await pe.async_set_day_text(planner, "p", "2026-10-20", "   ")
    # A new dish for it is chosen like for an empty day.
    swap = pe.build_swap_prompt(
        settings=init_integration.runtime_data.store.settings,
        plan=plan,
        day=tuesday,
        offer_lines=[],
    )
    assert "mangler aftensmad" in swap


async def test_unlisting(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Only lines that were sent; nothing in BilkaToGo's basket; REMA not answering
    leaves the plan changed all the same."""
    planner = init_integration.runtime_data.planner
    take = AsyncMock(return_value=1)
    planner._take_items = take
    assert await planner.async_unlist([{"name": "x", "packages": 1}]) == 0
    assert await planner.async_unlist([{"name": "x", "sent": SENT, "must_have": True}]) == 0
    assert await planner.async_unlist([{"name": "x", "sent": SENT, "buy_at": "93f13"}]) == 0
    assert not take.called
    line = {"name": "Salt", "amount": 1, "unit": "pk", "packages": 1, "sent": SENT}
    assert await planner.async_unlist([line]) == 1
    take.assert_awaited_once_with([{"name": "Salt", "amount": 1}])
    assert "sent" not in line
    take.side_effect = RemaError("nede")
    assert await planner.async_unlist([{**line, "sent": SENT}]) == 0
    planner._take_items = None
    assert await planner.async_unlist([{**line, "sent": SENT}]) == 0
    planner._take_items = take
    shop = planner.client
    planner.client = MagicMock(cart=object())
    take.reset_mock()
    assert await planner.async_unlist([{**line, "sent": SENT}]) == 0
    assert not take.called
    planner.client = shop


async def test_review_and_delete_take_off_the_list(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Har det, Forkert vare and deleting a sent line take it off REMA's list too."""
    planner = init_integration.runtime_data.planner
    take = AsyncMock(return_value=1)
    planner._take_items = take
    await pe.async_review_line(planner, "p", "l0", "have")
    await pe.async_edit_line(planner, "p", "l2", delete=True)
    assert [c.args[0] for c in take.await_args_list] == [
        [{"product_id": 30001, "amount": 1}],
        [{"name": "Spaghetti", "amount": 1}],
    ]


async def test_websocket(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Skriv på dagen and taking a day back, from the panel."""
    mock_client.async_get_primary_list = AsyncMock(return_value=make_list())
    client = await hass_ws_client(hass)

    async def ws(msg_id: int, **msg: Any) -> dict[str, Any]:
        await client.send_json({"id": msg_id, **msg})
        answer: dict[str, Any] = await client.receive_json()
        return answer

    msg = await ws(1, type="middagsro/day/text", plan_id="p", date="2026-10-20", text="Spiser ude")
    assert msg["success"], msg
    assert msg["result"]["days"][2]["dish"] == "Spiser ude"
    msg = await ws(2, type="middagsro/day/clear", plan_id="p", date="2026-10-20", skip=True)
    assert msg["result"]["skipped"] == ["2026-10-20"]
    msg = await ws(3, type="middagsro/day/restore", plan_id="p", date="2026-10-20")
    assert msg["result"]["days"][2]["dish"] == "Spiser ude"
    msg = await ws(4, type="middagsro/day/restore", plan_id="p", date="2026-10-20")
    assert not msg["success"]

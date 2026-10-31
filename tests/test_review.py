"""The review step: uncertain lines, the family's answers, and what the send does with them."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.planedit import async_edit_line, async_review_line
from custom_components.middagsro.record import answered
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import make_plan, make_product


def _unsure_plan(plan_id: str = "unsure") -> dict[str, Any]:
    """A plan whose minced beef is sure and whose spaghetti is not."""
    plan = make_plan(plan_id, start="2026-10-18")
    beef, parsley, pasta = plan["shopping"]
    beef.update(id="beef", key="hakket oksekød", confidence="high")
    parsley.update(id="parsley", key="persille", confidence="low", alternatives=[])
    pasta.update(
        id="pasta",
        key="spaghetti",
        confidence="medium",
        product={"id": 60002, "name": "SPAGHETTI", "underline": "500 GR.", "price": 9.0},
        packages=1,
        cost=9.0,
        alternatives=[{"id": 60003, "name": "FULDKORNSSPAGHETTI", "price": 12.0}],
    )
    return plan


def test_needs_review() -> None:
    """Only an unsure, untouched, unsent line of the plan's own needs a look."""
    assert mp.needs_review({"confidence": "low"})
    assert mp.needs_review({"confidence": "medium"})
    assert not mp.needs_review({"confidence": "high"})
    assert not mp.needs_review({})
    assert not mp.needs_review({"confidence": "low", "reviewed": True})
    assert not mp.needs_review({"confidence": "low", "skipped": True})
    assert not mp.needs_review({"confidence": "low", "must_have": True})
    assert not mp.needs_review({"confidence": "low", "added": True})
    assert not mp.needs_review({"confidence": "low", "sent": "2026-10-18T10:00:00"})


async def test_send_waits_for_the_review(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """With "review", a send by hand refuses while lines wait; an automatic one goes without them."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = _unsure_plan()
    await store.async_add_plan(plan)
    assert store.settings["uncertain_items"] == "review"

    with pytest.raises(ServiceValidationError) as err:
        await planner.async_send("unsure")
    assert err.value.translation_key == "review_needed"
    assert err.value.translation_placeholders == {"count": "2 varer"}
    assert not mock_client.async_add_to_list.called
    assert not any(line.get("sent") for line in plan["shopping"])

    # Nobody there at 02:00: the sure lines go, the others wait on the list.
    await planner.async_send("unsure", strict=False)
    sent = [line["id"] for line in plan["shopping"] if line.get("sent")]
    assert sent == ["beef"]
    assert plan["last_sent"]["ids"] == ["beef"]


async def test_send_modes(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """ "send" sends the unsure lines as they are; "skip" leaves them on the list."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = _unsure_plan("modes")
    await store.async_add_plan(plan)
    await store.async_set_settings({"uncertain_items": "skip"})
    await planner.async_send("modes")
    assert [line["id"] for line in plan["shopping"] if line.get("sent")] == ["beef"]

    plan = _unsure_plan("modes2")
    await store.async_add_plan(plan)
    await store.async_set_settings({"uncertain_items": "send"})
    await planner.async_send("modes2")
    assert [line["id"] for line in plan["shopping"] if line.get("sent")] == [
        "beef",
        "parsley",
        "pasta",
    ]
    # One line by hand is always sent, and a line left out never is.
    plan = _unsure_plan("one")
    plan["shopping"][0]["skipped"] = True
    await store.async_add_plan(plan)
    await store.async_set_settings({"uncertain_items": "review"})
    await planner.async_send("one", line_id="pasta")
    assert [line["id"] for line in plan["shopping"] if line.get("sent")] == ["pasta"]
    with pytest.raises(ServiceValidationError):
        await planner.async_send("one")  # parsley still waits
    plan["shopping"][1]["reviewed"] = True
    await planner.async_send("one")  # the checked parsley goes too
    assert [line["id"] for line in plan["shopping"] if line.get("sent")] == ["parsley", "pasta"]
    assert plan["total"] == 9.0  # the skipped beef does not count


async def test_review_answers_are_remembered(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Keep, choose, skip, take back and forget: what each does to the line and the memory."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = _unsure_plan("answers")
    await store.async_add_plan(plan)
    pasta = plan["shopping"][2]

    await async_review_line(planner, "answers", "pasta", "keep")
    assert pasta["reviewed"] is True
    assert pasta["product_id"] == 60002
    assert store.choice_for("spaghetti", "REMA 1000") == {
        "product_id": 60002,
        "name": "SPAGHETTI",
        "rejected": [],
        "at": store.choice_for("spaghetti", "REMA 1000")["at"],
    }
    assert not mp.needs_review(pasta)

    # Another product from the alternatives: fetched, put on, remembered instead.
    mock_client.async_get_products.return_value = [
        make_product(60003, "FULDKORNSSPAGHETTI", 12.0, underline="500 GR.")
    ]
    await async_review_line(planner, "answers", "pasta", "choose", 60003)
    assert pasta["product"]["id"] == 60003
    assert pasta["confidence"] == "high"
    assert "alternatives" not in pasta
    choice = store.choice_for("spaghetti", "REMA 1000")
    assert (choice["product_id"], choice["rejected"]) == (60003, [60002])
    assert store.rejected_products("spaghetti", "REMA 1000") == {60002}
    with pytest.raises(ServiceValidationError) as err:
        await async_review_line(planner, "answers", "pasta", "choose")
    assert err.value.translation_key == "product_required"

    await async_review_line(planner, "answers", "pasta", "skip")
    assert pasta["skipped"] is True
    assert store.choice_for("spaghetti", "REMA 1000") is None  # not that one again
    assert store.rejected_products("spaghetti", "REMA 1000") == {60002, 60003}
    assert plan["total"] == 40.0
    await async_review_line(planner, "answers", "pasta", "unskip")
    assert "skipped" not in pasta
    assert plan["total"] == 52.0

    pasta["remembered"] = True
    pasta["note"] = "Jeres valg fra en tidligere madplan"
    await async_review_line(planner, "answers", "pasta", "forget")
    assert store.choice_for("spaghetti", "REMA 1000") is None
    assert "remembered" not in pasta
    assert pasta["note"] is None

    for args in (("answers", "nope", "keep"), ("nope", "pasta", "keep")):
        with pytest.raises(ServiceValidationError):
            await async_review_line(planner, *args)
    with pytest.raises(ServiceValidationError) as err:
        await async_review_line(planner, "answers", "pasta", "dance")
    assert err.value.translation_key == "unknown_action"


async def test_choosing_by_hand_is_remembered_and_used(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A product put on a line in the panel is the one that ingredient gets next time."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = _unsure_plan("hand")
    await store.async_add_plan(plan)
    chosen = make_product(60003, "FULDKORNSSPAGHETTI", 12.0, underline="500 GR.")
    mock_client.async_get_products.return_value = [chosen]
    await async_edit_line(planner, "hand", "pasta", product_id=60003)
    assert store.choice_for("spaghetti", "REMA 1000")["product_id"] == 60003

    line: dict[str, Any] = {"name": "Spaghetti", "search": "spaghetti", "amount": 500, "unit": "g",
                            "category": "Kolonial"}  # fmt: skip
    mock_client.async_search_products.reset_mock()
    await planner._async_match(line)
    assert line["product"]["id"] == 60003
    assert line["remembered"] is True
    assert line["confidence"] == "high"
    assert line["note"] == "Jeres valg fra en tidligere madplan"
    assert not mock_client.async_search_products.called

    # Not sold any more: searched as usual, and the rejected one is never taken.
    mock_client.async_get_products.return_value = []
    line = {"name": "Spaghetti", "search": "spaghetti", "amount": 500, "unit": "g",
            "category": "Kolonial"}  # fmt: skip
    await planner._async_match(line)
    assert "remembered" not in line
    assert mock_client.async_search_products.called

    # A must-have or an added product is the family's own choice already: no memory.
    await store.async_remember_choice("", "REMA 1000", 1, "x")
    assert store.choice_for("", "REMA 1000") is None


async def test_uncertain_items_setting(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The setting takes its three values and falls back to review."""
    store = init_integration.runtime_data.store
    for value in ("send", "skip", "review"):
        await store.async_set_settings({"uncertain_items": value})
        assert store.settings["uncertain_items"] == value
    await store.async_set_settings({"uncertain_items": "whatever"})
    assert store.settings["uncertain_items"] == "review"


async def test_review_over_websocket(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: Any,
) -> None:
    """The panel's Behold and Udelad reach the plan (the command is registered)."""
    store = init_integration.runtime_data.store
    plan = _unsure_plan("ws")
    await store.async_add_plan(plan)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "middagsro/plan/review", "plan_id": "ws", "line_id": "pasta",
         "action": "keep", "product_id": None}
    )  # fmt: skip
    answer = await client.receive_json()
    assert answer["success"], answer
    pasta = next(line for line in answer["result"]["shopping"] if line["id"] == "pasta")
    assert pasta["reviewed"] and pasta["product_id"] == 60002
    await client.send_json(
        {"id": 2, "type": "middagsro/plan/review", "plan_id": "ws", "line_id": "parsley",
         "action": "skip"}
    )  # fmt: skip
    answer = await client.receive_json()
    assert answer["success"], answer
    parsley = next(line for line in answer["result"]["shopping"] if line["id"] == "parsley")
    assert parsley["skipped"]


def test_every_websocket_command_is_registered(hass: HomeAssistant) -> None:
    """A ws_ handler that is never registered answers "Unknown command" in the panel."""
    import inspect  # noqa: PLC0415
    from unittest.mock import patch  # noqa: PLC0415

    from custom_components.middagsro import websocket as ws  # noqa: PLC0415

    handlers = {name: f for name, f in inspect.getmembers(ws) if name.startswith("ws_")}
    with patch.object(ws.websocket_api, "async_register_command") as register:
        ws.async_register_websocket(hass)
    registered = [call.args[1] for call in register.call_args_list]
    missing = [name for name, f in handlers.items() if not any(f is r for r in registered)]
    assert missing == []


async def test_have_it_at_home_is_not_learned(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Har det: off the list this time, nothing remembered; and after Forkert vare it
    takes the no back (as Tag den med igen does)."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = _unsure_plan("have")
    await store.async_add_plan(plan)
    shop = planner.shop

    result = await async_review_line(planner, "have", "pasta", "have")
    pasta = next(line for line in result["shopping"] if line["id"] == "pasta")
    assert pasta["skipped"] and pasta["have"] and pasta["reviewed"]
    assert store.rejected_products("spaghetti", shop) == set()
    assert answered(pasta) is None  # says nothing about the product

    await async_review_line(planner, "have", "pasta", "skip")
    assert "have" not in pasta
    assert store.rejected_products("spaghetti", shop) == {60002}
    assert answered(pasta) == "unknown"
    await async_review_line(planner, "have", "pasta", "have")
    assert store.rejected_products("spaghetti", shop) == set()
    assert "spaghetti" not in str(store.choices)  # nothing left to remember

    await async_review_line(planner, "have", "pasta", "skip")
    await async_review_line(planner, "have", "pasta", "unskip")
    assert store.rejected_products("spaghetti", shop) == set()
    assert not pasta.get("skipped") and not pasta.get("have")

    # A product the family also chose stays chosen when one no is taken back.
    await store.async_remember_choice("spaghetti", shop, 60003, "FULDKORNSSPAGHETTI", 60002)
    await store.async_unreject_product("spaghetti", shop, 60002)
    assert store.choice_for("spaghetti", shop)["product_id"] == 60003
    await store.async_unreject_product("spaghetti", shop, 60002)  # nothing to take back
    await store.async_unreject_product("persille", shop, 1)

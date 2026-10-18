"""Tests for matching a plan's offer items again once REMA has the offers (02:00)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.rema1000.api import Offer, RemaError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import make_plan, make_product

# Week 43's salmon offer: Tjek says it is REMA's product 440095, which REMA
# only had from sunday 02:00 (HEL LAKSEFILET, 600 g, 89 kr).
LAKS = Offer(
    id="laks",
    heading="REMA 1000 Laksefilet",
    description="600 g\nPartivare.",
    price=89,
    pre_price=None,
    quantity="600 g",
    valid_from="2026-10-17T22:00:00+0000",
    valid_to="2026-10-24T21:59:59+0000",
    product_ids=(440095,),
    product_names=("REMA 1000 laksefilet 600g",),
)
WHOLE = make_product(440095, "HEL LAKSEFILET", 89.0, underline="600 GR. / REMA 1000",
                     is_advertised=True)  # fmt: skip
SMALL = make_product(440065, "LAKSEFILETER", 43.95, underline="225 GR. / REMA 1000")


def salmon_plan(plan_id: str = "laks") -> dict[str, Any]:
    """A plan made saturday: the salmon offer's product wasn't in REMA yet."""
    plan = make_plan(plan_id, start="2026-10-18")
    plan["catalog"] = {"id": "cat-43", "label": "Uge 43"}
    plan["shopping"] = [
        {
            "name": "Laksefilet", "amount": 600, "unit": "g", "search": "laks", "category": "Fisk",
            "offer": "o13", "offer_name": "REMA 1000 Laksefilet", "must_have": False,
            "product_id": None, "buy_from": None,
            "product": {"id": 440065, "name": "LAKSEFILETER", "price": 43.95},
            "packages": 3, "cost": 131.85, "note": None,
        },
        {
            "name": "Æg", "amount": 10, "unit": "stk", "search": "æg", "category": "Mejeri",
            "offer": "o0", "offer_name": "Æg", "must_have": False, "product_id": None,
            "buy_from": "2026-10-22", "product": {"id": 1, "name": "ÆG", "price": 30},
            "packages": 1, "cost": 30, "note": None,
        },
        {
            "name": "Kaffe", "amount": 1, "unit": "pk", "search": "kaffe", "category": "Tilføjet",
            "offer_name": "REMA 1000 Laksefilet", "added": True, "id": "a1",
            "product": {"id": 2, "name": "KAFFE", "price": 40}, "packages": 1, "cost": 40,
        },
    ]  # fmt: skip
    return plan


@pytest.fixture
def salmon(mock_client: MagicMock) -> None:
    """REMA and Tjek as on sunday morning."""
    mock_client.async_get_offers.return_value = [LAKS, replace(LAKS, id="x", heading="Æg")]
    mock_client.async_get_products.return_value = [WHOLE]

    async def search(query: str, limit: int = 24, at: Any = None) -> list[Any]:
        return [SMALL, WHOLE]

    mock_client.async_search_products.side_effect = search


@pytest.mark.usefixtures("salmon")
async def test_refresh_after_the_offer_starts(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, freezer: Any
) -> None:
    """From 02:00 on the first day the offer's own product is chosen."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = salmon_plan()
    await store.async_add_plan(plan)

    # Before it starts nothing changes.
    await planner.async_refresh_offers("laks")
    assert plan["shopping"][0]["product"]["id"] == 440065

    freezer.move_to(datetime(2026, 10, 18, 8, tzinfo=UTC))
    await planner.async_refresh_offers("laks")
    fish, eggs, coffee = plan["shopping"]
    assert (fish["product"]["id"], fish["packages"], fish["cost"]) == (440095, 1, 89)
    assert eggs["product"]["id"] == 1  # thursday's offer hasn't started
    assert coffee["product"]["id"] == 2  # added by hand: left alone
    assert plan["total"] == pytest.approx(89 + 30 + 40)
    assert plan["refreshed_at"]

    # Gone from the avis, or a plan without an avis: left alone.
    mock_client.async_get_offers.return_value = []
    fish["product"] = {"id": 7}
    await planner.async_refresh_offers("laks", "main")
    assert fish["product"] == {"id": 7}
    plan["catalog"] = None
    await planner.async_refresh_offers("laks")
    with pytest.raises(ServiceValidationError):
        await planner.async_refresh_offers("nope")


@pytest.mark.usefixtures("salmon")
async def test_send_looks_at_the_offers_again(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, freezer: Any
) -> None:
    """Sending on the shopping day sends the offer's own product."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    await store.async_add_plan(salmon_plan())
    freezer.move_to(datetime(2026, 10, 18, 8, tzinfo=UTC))
    await planner.async_send("laks")
    sent = [c.kwargs.get("product_id") for c in mock_client.async_add_to_list.call_args_list]
    assert 440095 in sent

    # Thursday, and Tjek can't be reached: sent as it was.
    freezer.move_to(datetime(2026, 10, 22, 8, tzinfo=UTC))
    mock_client.async_get_offers.side_effect = RemaError("down")
    mock_client.async_add_to_list.reset_mock()
    await planner.async_send("laks", "late")
    assert [c.kwargs.get("product_id") for c in mock_client.async_add_to_list.call_args_list] == [1]


@pytest.mark.usefixtures("salmon")
async def test_refresh_at_two_on_the_shopping_day(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, freezer: Any
) -> None:
    """A new plan looks at its offers again at 02:00, also after a restart."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = salmon_plan()
    await store.async_add_plan(plan)
    planner._schedule_refreshes(plan)
    assert plan["refresh_at"] == "2026-10-18T00:05:00+00:00"
    assert plan["late_refresh_at"] == "2026-10-22T00:05:00+00:00"

    planner.async_cancel()
    other = salmon_plan("sent")
    other["send_at"] = "2026-10-18T00:05:00+00:00"
    other["refresh_at"] = "2026-10-18T00:05:00+00:00"
    await store.async_add_plan(other)
    planner.async_restore_sends()
    assert set(planner._sends) == {
        ("laks", "refresh_at"), ("laks", "late_refresh_at"),
        ("sent", "send_at"), ("sent", "refresh_at"),
    }  # fmt: skip
    await store.async_delete_plan("sent")

    freezer.move_to(datetime(2026, 10, 18, 0, 6, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert plan["shopping"][0]["product"]["id"] == 440095
    assert "refresh_at" not in plan

    # Thursday: Tjek is down: logged, and tried again when the list is sent.
    mock_client.async_get_offers.side_effect = RemaError("down")
    freezer.move_to(datetime(2026, 10, 22, 0, 6, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "late_refresh_at" not in plan

    # A plan sent automatically at the same time: the send looks at the offers.
    late = salmon_plan("both")
    late["start_date"] = "2026-10-25"
    late["end_date"] = "2026-10-27"
    late["shopping"] = [line for line in late["shopping"] if not line.get("buy_from")]
    await store.async_add_plan(late)
    planner._schedule_refreshes(late)
    late["send_at"] = late["refresh_at"]
    await planner._async_refresh_due("both", "main")
    assert "refresh_at" not in late
    assert late["shopping"][0]["product"]["id"] == 440065  # left to the send
    await planner._async_refresh_due("gone", "main")


@pytest.mark.usefixtures("salmon")
async def test_refresh_command(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    freezer: Any,
) -> None:
    """The panel's button."""
    await init_integration.runtime_data.store.async_add_plan(salmon_plan())
    client = await hass_ws_client(hass)  # signed in before the clock moves on
    freezer.move_to(datetime(2026, 10, 18, 8, tzinfo=UTC))
    await client.send_json({"id": 1, "type": "rema1000/plan/refresh", "plan_id": "laks"})
    result = await client.receive_json()
    assert result["result"]["shopping"][0]["product"]["id"] == 440095

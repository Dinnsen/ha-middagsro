"""Tests for 2.7.0: another shop than REMA 1000 (no login, its avis, a list in Home Assistant)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import budget, mealplan as mp, planedit as pe, watch
from custom_components.middagsro.api import Catalog, RemaClient
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.storage import clean_settings
from custom_components.middagsro.store_client import (
    CONF_STORE,
    REMA,
    StoreClient,
    genitive,
    store_name,
    store_of,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import CURRENT, NOW, OFFERS, UPCOMING, make_plan, store_data

NETTO = "9ba51"
TOYS = Catalog(id="toys", label="Legetøj", valid_from=None, valid_to=None, offer_count=10)


def test_helpers() -> None:
    """The shop of an entry (REMA 1000 when none is chosen), and its name."""
    assert store_of({}) == REMA
    assert store_of(None) == REMA
    assert store_of({CONF_STORE: NETTO}) == NETTO
    assert store_of({CONF_STORE: "ukendt"}) == REMA
    assert store_name(NETTO) == "Netto"
    assert store_name("ukendt") == "ukendt"
    assert genitive("Netto") == "Nettos"
    assert genitive("føtex") == "føtex'"
    assert genitive("REMA 1000") == "REMA 1000's"


def _client(hass: HomeAssistant, entry_id: str = "e1") -> StoreClient:
    return StoreClient(hass, async_get_clientsession(hass), entry_id, NETTO)


async def test_the_list(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """The shopping list is kept in Home Assistant."""
    client = _client(hass)
    assert await client.async_login() == 0
    assert client.has_prices is False
    assert await client.async_get_lists() == [{"id": 1, "name": "Indkøbsliste", "is_primary": True}]
    assert await client.async_get_primary_list_id(force=True) == 1
    shopping = await client.async_get_primary_list()
    assert shopping.items == []

    await client.async_add_to_list(shopping, amount=2, name="Mælk")
    await client.async_add_to_list(await client.async_get_primary_list(), amount=1, name="mælk ")
    item = await client.async_create_item(1, amount=0, name=" Kaffe ")
    assert item == {"id": 2, "name": "Kaffe", "amount": 1, "bought": False}
    with pytest.raises(ValueError):
        await client.async_create_item(1, product_id=20496)
    shopping = await client.async_get_primary_list()
    assert [(i.name, i.amount, i.product_id) for i in shopping.items] == [
        ("Mælk", 3, None),
        ("Kaffe", 1, None),
    ]

    assert (await client.async_update_item(1, 2, bought=True, name=" Kaffebønner", amount=4)) == {
        "id": 2,
        "name": "Kaffebønner",
        "amount": 4,
        "bought": True,
    }
    assert await client.async_update_item(1, 99, bought=True) == {}
    await client.async_delete_items(1, [])
    await client.async_delete_items(1, [1])

    # Kept on disk, and read again.
    again = _client(hass)
    await again.async_login()
    shopping = await again.async_get_list(1)
    assert [(i.id, i.name, i.bought) for i in shopping.items] == [(2, "Kaffebønner", True)]
    assert (await again.async_create_item(1, name="Te"))["id"] == 3
    assert hass_storage[f"{DOMAIN}.e1.list"]["data"]["next_id"] == 4


async def test_bad_stored_list(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Lines without an id or a name are left out."""
    hass_storage[f"{DOMAIN}.e1.list"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.e1.list",
        "data": {"items": [{"id": 5, "name": "Ost"}, {"id": "x", "name": "?"}, {"id": 6}, "nej"]},
    }
    client = _client(hass)
    shopping = await client.async_get_primary_list()
    assert [i.name for i in shopping.items] == ["Ost"]
    assert (await client.async_create_item(1, name="Brød"))["id"] == 6


async def test_avis_and_nothing_else(hass: HomeAssistant) -> None:
    """The shop's food aviser from Tjek; products, prices and recipes are REMA's."""
    client = _client(hass)
    with patch.object(
        RemaClient, "async_get_catalogs", AsyncMock(return_value=[CURRENT, TOYS, UPCOMING])
    ):
        assert await client.async_get_catalogs() == [CURRENT, UPCOMING]
    offers = await client.async_get_offer_products([replace(OFFERS[0], unlinked=True)])
    assert offers[0].product_ids == ()
    assert offers[0].product_names == ()
    assert offers[0].unlinked is False
    assert await client.async_search_products("mælk") == []
    assert await client.async_search_products_at("mælk", 5, [NOW, NOW]) == [[], []]
    assert await client.async_get_products([1]) == []
    assert await client.async_get_favorites() == []
    assert await client.async_get_nutrition([1]) == {}
    assert await client.async_get_recipes(page=1) == {}
    assert await client.async_get_recipe("lasagne") is None


@pytest.fixture
async def netto(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_panel: tuple[AsyncMock, MagicMock],
    freezer: Any,
) -> AsyncGenerator[MockConfigEntry]:
    """Middagsro set up for Netto, with a plan from sunday 18/10."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Copenhagen")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Middagsro – Netto",
        unique_id=f"store_{NETTO}",
        data={CONF_STORE: NETTO},
    )
    entry.add_to_hass(hass)
    store_data(hass_storage, entry.entry_id, plans=[make_plan("p", start="2026-10-18")])
    with (
        patch.object(RemaClient, "async_get_catalogs", AsyncMock(return_value=[CURRENT, UPCOMING])),
        patch.object(RemaClient, "async_get_offers", AsyncMock(return_value=OFFERS)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry


async def test_set_up_for_netto(
    hass: HomeAssistant, netto: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """No login; the panel is told the shop, and the REMA note isn't shown."""
    data = netto.runtime_data
    assert isinstance(data.client, StoreClient)
    assert data.planner.prices is False
    assert data.planner.shop == "Netto"
    assert data.store.prices is False
    assert data.offers.data.current == CURRENT

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/state"})
    state = (await client.receive_json())["result"]
    assert state["shop"]["id"] == NETTO
    assert state["shop"]["name"] == "Netto"
    assert state["shop"]["rema"] is False
    assert "REMA's opskrifter" in state["shop"]["rema_only"]
    assert state["notices"] == []

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), netto.entry_id)
    assert [d.model for d in devices] == ["Netto"]


async def test_list_also_on_another_todo_list(hass: HomeAssistant, netto: MockConfigEntry) -> None:
    """What is put on the list goes on the family's own to-do list too, when chosen."""
    data = netto.runtime_data
    calls: list[dict[str, Any]] = []
    failing = [False]

    async def add_item(call: ServiceCall) -> None:
        calls.append(dict(call.data))
        if failing[0]:
            raise HomeAssistantError("nede")

    hass.services.async_register("todo", "add_item", add_item)
    await data.shopping_list.async_add_items([{"name": "Mælk", "amount": 2}])
    assert calls == []  # none chosen

    data.store.settings["ha_todo_entity"] = "todo.familie"
    await data.shopping_list.async_add_items([{"name": "Mælk", "amount": 2}])
    assert calls == []  # not there

    hass.states.async_set("todo.familie", "0")
    await data.shopping_list.async_add_items([{"name": "Kaffe", "amount": 2}, {"name": "Te"}])
    assert [c["item"] for c in calls] == ["2 x Kaffe", "Te"]
    assert calls[0]["entity_id"] in ("todo.familie", ["todo.familie"])

    calls.clear()
    failing[0] = True
    await data.shopping_list.async_add_items([{"name": "Ost"}, {"name": "Brød"}])
    assert len(calls) == 1  # stops at the first error
    shopping = await data.client.async_get_primary_list()
    assert [(i.name, i.amount) for i in shopping.items][:2] == [("Mælk", 4), ("Kaffe", 2)]


def test_todo_setting() -> None:
    """Only a to-do entity id is kept."""
    assert clean_settings({"ha_todo_entity": "todo.familie"})["ha_todo_entity"] == "todo.familie"
    assert clean_settings({"ha_todo_entity": "light.stue"})["ha_todo_entity"] == ""
    assert clean_settings({})["ha_todo_entity"] == ""


async def test_items_without_prices(hass: HomeAssistant, netto: MockConfigEntry) -> None:
    """An offer is bought as the avis has it; everything else is free text without a price."""
    planner = netto.runtime_data.planner
    line: dict[str, Any] = {"name": "Hakket oksekød", "search": "hakket oksekød", "amount": 500,
                            "unit": "g", "category": "Kød"}  # fmt: skip
    await planner._async_match(line, None, OFFERS[0])
    assert line["product"] is None
    assert line["avis_item"]["price"] == 40.0
    assert line["cost"] == 40.0
    assert line["note"] == "Tilbud i Nettos avis"

    other = {"name": "Persille", "search": "persille", "amount": 1, "unit": "bundt"}
    await planner._async_match(other, None, OFFERS[1])  # an offer for something else
    assert (other["product"], other["cost"], other["note"]) == (None, None, None)

    must = {"name": "Letmælk", "search": "letmælk", "amount": 2, "unit": "stk", "must_have": True}
    await planner._async_match(must, None, None)
    assert (must["product"], must["note"]) == (None, None)


def test_prompt_for_another_shop() -> None:
    """The AI is told the shop, and that the budget is a guess."""
    kwargs: dict[str, Any] = {
        "settings": clean_settings({"budget": 900, "organic": "only"}),
        "dates": [date(2026, 10, 18)],
        "catalog": None,
        "offers": OFFERS,
        "favorites_due": [],
        "favorites_optional": [],
        "recent_dishes": [],
    }
    netto = mp.build_prompt(**kwargs, shop="Netto", prices=False)
    assert "Familien handler i Netto i Danmark." in netto
    assert "ca. 900 kr. (et skøn" in netto
    assert "UGENS TILBUD I NETTO" in netto
    assert "et søgeord til Nettos varesøgning" in netto
    assert "hvor Netto har dem" in netto
    rema = mp.build_prompt(**kwargs)
    assert "Familien handler i REMA 1000 i Danmark." in rema
    assert "under 900 kr. med REMA 1000-priser" in rema
    assert "et søgeord til REMA 1000's varesøgning" in rema
    assert "et skøn" not in rema


async def test_budget_without_prices(hass: HomeAssistant, netto: MockConfigEntry) -> None:
    """Only what the family books counts: the plans' prices are only the offers."""
    store = netto.runtime_data.store
    plan = store.plans[0]
    plan["shopping"][0]["sent"] = "2026-10-14T10:00:00+00:00"
    assert budget.planned(store, date(2026, 10, 1), date(2026, 10, 31)) == 0.0
    assert budget._month_lists(store, date(2026, 10, 1), date(2026, 10, 31)) == (0.0, 0.0)
    store.prices = True
    assert budget.planned(store, date(2026, 10, 1), date(2026, 10, 31)) > 0
    assert budget._month_lists(store, date(2026, 10, 1), date(2026, 10, 31))[1] > 0


async def test_watch_looks_in_the_shop(hass: HomeAssistant, netto: MockConfigEntry) -> None:
    """The family's own shop first, and not twice when it is also among the chains."""
    planner = netto.runtime_data.planner
    planner.store.watch = [{"key": "kaffe", "text": "kaffe"}]
    planner.store.settings["chains"] = [NETTO, "71c90"]
    asked: list[str] = []

    async def offers(dealer_id: str, force: bool = False) -> list[dict[str, Any]]:
        asked.append(dealer_id)
        return []

    with patch.object(planner.chains, "async_offers", side_effect=offers):
        deals = await watch.async_deals(planner)
    assert asked == [NETTO, "71c90"]
    assert deals[0]["deals"] == []


async def test_add_text_to_the_plan(
    hass: HomeAssistant, netto: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Something typed goes on the plan's list as free text."""
    client = await hass_ws_client(hass)
    msg_id = 0

    async def ws(**msg: Any) -> dict[str, Any]:
        nonlocal msg_id
        msg_id += 1
        await client.send_json({"id": msg_id, **msg})
        result: dict[str, Any] = await client.receive_json()
        return result

    msg = await ws(type="middagsro/plan/add", plan_id="p", name="  Kaffe   bønner ", amount=2)
    assert msg["success"], msg
    assert (msg["result"]["name"], msg["result"]["amount"], msg["result"]["cost"]) == (
        "Kaffe bønner",
        2,
        None,
    )
    assert msg["result"]["added"] is True
    assert not (await ws(type="middagsro/plan/add", plan_id="p", name=" "))["success"]
    assert not (await ws(type="middagsro/plan/add", plan_id="x", name="Te"))["success"]
    late = await ws(type="middagsro/plan/add", plan_id="p", name="Te", part="late")
    assert not late["success"]  # the plan has no later shopping day
    plan = netto.runtime_data.store.get_plan("p")
    assert plan is not None
    plan["shopping"][0]["buy_from"] = "2026-10-22"
    late = await ws(type="middagsro/plan/add", plan_id="p", name="Te", part="late")
    assert late["result"]["buy_from"] == "2026-10-22"
    with pytest.raises(HomeAssistantError):
        await pe.async_add_text(netto.runtime_data.planner, "p", "")


async def test_store_choice_notice(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """REMA families are told once that the shop can be chosen."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/state"})
    state = (await client.receive_json())["result"]
    assert state["notices"] == ["store_choice"]
    assert state["shop"] == {
        "id": REMA,
        "name": "REMA 1000",
        "rema": True,
        "prices": True,
        "rema_only": state["shop"]["rema_only"],
    }
    await client.send_json({"id": 2, "type": "middagsro/notice_seen", "notice": "store_choice"})
    assert (await client.receive_json())["success"]
    await client.send_json({"id": 3, "type": "middagsro/notice_seen", "notice": "store_choice"})
    assert (await client.receive_json())["success"]
    assert init_integration.runtime_data.store.seen == ["store_choice"]
    await client.send_json({"id": 4, "type": "middagsro/state"})
    assert (await client.receive_json())["result"]["notices"] == []
    await client.send_json({"id": 5, "type": "middagsro/notice_seen", "notice": "andet"})
    assert not (await client.receive_json())["success"]

    # Kept on disk.
    store = init_integration.runtime_data.store
    await store.async_load()
    assert store.seen == ["store_choice"]

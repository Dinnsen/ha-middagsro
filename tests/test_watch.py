"""Tests for the watch list: products and texts, their offers, and the notifications."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import watch as wt
from custom_components.middagsro.api import RemaError
from custom_components.middagsro.chains import REMA_ID, ChainError
from custom_components.middagsro.storage import clean_settings
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .conftest import NOW, make_product

NETTO = "9ba51"
LIDL = "71c90"


def offer(offer_id: str, heading: str, price: float, dealer: str, description: str = "",
          valid_to: str = "2026-10-23T21:59:59+00:00") -> dict[str, Any]:  # fmt: skip
    """An offer as ChainOffers has it."""
    return {
        "id": offer_id, "heading": heading, "description": description, "price": price,
        "pre_price": price + 10, "quantity": None, "valid_from": "2026-10-16T22:00:00+00:00",
        "valid_to": valid_to, "image": "https://img/x", "dealer_id": dealer,
    }  # fmt: skip


OFFERS = {
    REMA_ID: [
        offer("r1", "Merrild kaffe 400 g", 39, REMA_ID, "Flere varianter"),
        offer("old", "Merrild kaffe", 30, REMA_ID, valid_to="2026-10-01T00:00:00+00:00"),
    ],
    NETTO: [
        offer("n1", "Arla letmælk 1,5%", 9.95, NETTO, "1 liter"),
        offer("n2", "Arla letmælk 1,5%", 8.95, NETTO, "1 liter"),
        offer("n3", "Merrild kaffe", 45, NETTO, "500 g"),
    ],
}

MILK = make_product(20494, "LETMÆLK 1,5%", 9.0, underline="1 LTR.", normal_price=13.95,
                    is_advertised=True)  # fmt: skip
BUTTER = replace(
    make_product(2, "SMØR", 20.0, underline="250 GR."),
    upcoming_price=15.0,
    upcoming_from="2026-10-18T22:00:00+00:00",
    upcoming_is_advertised=True,
)
FLOUR = make_product(3, "HVEDEMEL", 12.0, underline="2 KG.")


async def fake_offers(dealer_id: str) -> list[dict[str, Any]]:
    if dealer_id == LIDL:
        raise ChainError("down")
    return OFFERS.get(dealer_id, [])


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """The chains the family uses."""
    return {"settings": {"chains": [NETTO, LIDL]}}


async def _watch_all(store: Any) -> None:
    for item in (
        {"product_id": MILK.id, "name": MILK.name, "underline": MILK.underline},
        {"product_id": BUTTER.id, "name": BUTTER.name},
        {"product_id": FLOUR.id, "name": FLOUR.name},
        {"product_id": 99, "name": "UDGÅET"},
        {"text": "  Merrild   kaffe "},
    ):
        assert await wt.async_toggle(store, item) is True


def test_items_and_lines() -> None:
    """Watched items, chain names and how an offer is told."""
    assert wt.clean_item({"text": "  Merrild  kaffe "})["key"] == "tmerrild kaffe"  # type: ignore[index]
    item = wt.clean_item({"id": 5, "name": "MÆLK", "image": "http://usikkert"})
    assert item is not None
    assert (item["key"], item["product_id"], item["image"]) == ("p5", 5, None)
    assert wt.clean_item({"product_id": -1, "text": "x"})["product_id"] is None  # type: ignore[index]
    assert wt.clean_item({"text": " "}) is None
    assert wt.clean_item("tekst") is None
    assert (wt.chain_name(REMA_ID), wt.chain_name(NETTO), wt.chain_name("x")) == (
        "REMA 1000",
        "Netto",
        "x",
    )
    line = wt.deal_line({"dealer_id": REMA_ID, "heading": "MÆLK", "price": 9, "normal_price": 13.95,
                         "valid_to": "2026-10-24T21:59:59+00:00"})  # fmt: skip
    assert line == "🛒 REMA 1000: MÆLK – 9,00 kr. (før 13,95 kr.) til 24/10"
    later = wt.deal_line({"dealer_id": NETTO, "heading": "Kaffe", "price": None,
                          "valid_from": "2099-01-01T12:00:00+00:00"})  # fmt: skip
    assert later == "🏷️ Netto: Kaffe fra 1/1"
    for value, kept in (("notify.mobile_app_x", "notify.mobile_app_x"),
                        ("persistent_notification", "persistent_notification"),
                        ("script.x", ""), (None, "")):  # fmt: skip
        assert clean_settings({"watch_notify": value})["watch_notify"] == kept


async def test_toggle_and_own_favorites(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A product or a text is watched and unwatched; own favourites are added and removed."""
    store = init_integration.runtime_data.store
    assert await wt.async_toggle(store, {"text": "Bleer"}) is True
    assert await wt.async_toggle(store, {"text": "bleer"}) is False
    assert store.watch == []
    with pytest.raises(ServiceValidationError) as err:
        await wt.async_toggle(store, {})
    assert err.value.translation_key == "watch_item_required"
    with patch.object(wt, "MAX_WATCH", 1):
        await wt.async_toggle(store, {"text": "a"})
        with pytest.raises(ServiceValidationError) as err:
            await wt.async_toggle(store, {"text": "b"})
    assert err.value.translation_key == "too_many_watched"

    own = await wt.async_own_favorite(store, {"id": 7, "name": "KAFFE"}, add=True)
    assert own == [{"id": 7, "name": "KAFFE", "underline": "", "image": None}]
    assert await wt.async_own_favorite(store, {"id": 7, "name": "KAFFE"}, add=False) == []
    with pytest.raises(ServiceValidationError):
        await wt.async_own_favorite(store, {"text": "kaffe"}, add=True)
    with patch.object(wt, "MAX_OWN_FAVORITES", 0), pytest.raises(ServiceValidationError):
        await wt.async_own_favorite(store, {"id": 8, "name": "TE"}, add=True)


async def test_deals(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """REMA's own offers (now and next week), the same kind elsewhere, and texts everywhere."""
    planner = init_integration.runtime_data.planner
    store = planner.store
    assert await wt.async_deals(planner) == []
    await _watch_all(store)
    mock_client.async_get_products = AsyncMock(return_value=[MILK, BUTTER, FLOUR])
    with patch.object(planner.chains, "async_offers", side_effect=fake_offers):
        items = {i["key"]: i for i in await wt.async_deals(planner)}
    milk = items["p20494"]["deals"]
    assert [(d["source"], d["dealer_id"], d["price"]) for d in milk] == [
        ("rema", REMA_ID, 9.0),
        ("chain", NETTO, 8.95),  # the cheapest of Netto's
    ]
    butter = items["p2"]["deals"]
    assert [(d["price"], d["valid_from"]) for d in butter] == [(15.0, "2026-10-18T22:00:00+00:00")]
    assert items["p3"]["deals"] == []
    assert items["p99"]["deals"] == []  # REMA doesn't have it any more
    coffee = items["tmerrild kaffe"]["deals"]
    assert [(d["source"], d["dealer_id"]) for d in coffee] == [
        ("rema_avis", REMA_ID),
        ("chain", NETTO),
    ]
    assert coffee[0]["offer"]["id"] == "r1"  # the old one has ended

    # REMA can't be reached: only the chains' offers.
    mock_client.async_get_products = AsyncMock(side_effect=RemaError("down"))
    with patch.object(planner.chains, "async_offers", side_effect=fake_offers):
        items = {i["key"]: i for i in await wt.async_deals(planner)}
    assert [d["source"] for d in items["p20494"]["deals"]] == ["chain"]


async def test_notifications(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """New offers are told once, to a notify service or in Home Assistant."""
    planner = init_integration.runtime_data.planner
    store = planner.store
    assert await wt.async_check(planner) == 0  # nothing watched
    await _watch_all(store)
    assert await wt.async_check(planner) == 0  # no notifications chosen
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("notify", "mobile_app_telefon", record)
    targets = wt.notify_targets(hass)
    assert targets[0]["id"] == "persistent_notification"
    assert {"id": "notify.mobile_app_telefon", "name": "📱 telefon"} in targets

    await store.async_set_settings({**store.settings, "watch_notify": "notify.mobile_app_telefon"})
    store.watch_sent["gammel"] = "2026-10-01T00:00:00+00:00"
    mock_client.async_get_products = AsyncMock(return_value=[MILK, BUTTER, FLOUR])
    with patch.object(planner.chains, "async_offers", side_effect=fake_offers):
        assert await wt.async_check(planner) == 3  # milk, butter, coffee
        assert await wt.async_check(planner) == 0  # told already
    assert "gammel" not in store.watch_sent
    milk = next(c for c in calls if "LETMÆLK" in c.data["title"])
    assert milk.data["title"] == "🔔 LETMÆLK 1,5% er på tilbud"
    assert milk.data["message"].splitlines()[0].startswith("🛒 REMA 1000: LETMÆLK 1,5% – 9,00 kr.")
    assert milk.data["data"]["url"] == "/middagsro"
    assert milk.data["data"]["image"] == "https://images.example/20494.webp"

    # In Home Assistant itself.
    store.watch_sent.clear()
    await store.async_set_settings({**store.settings, "watch_notify": "persistent_notification"})
    with (
        patch.object(planner.chains, "async_offers", side_effect=fake_offers),
        patch.object(wt.persistent_notification, "async_create") as create,
    ):
        assert await wt.async_check(planner) == 3
    ids = {c.kwargs["notification_id"] for c in create.call_args_list}
    assert ids == {"middagsro_watch_p20494", "middagsro_watch_p2", "middagsro_watch_tmerrild_kaffe"}

    # A notify service that is gone: nothing is told, and it is tried again later.
    store.watch_sent.clear()
    await store.async_set_settings({**store.settings, "watch_notify": "notify.findes_ikke"})
    with patch.object(planner.chains, "async_offers", side_effect=fake_offers):
        assert await wt.async_check(planner) == 0
    assert store.watch_sent == {}


async def test_checked_every_few_hours(
    hass: HomeAssistant, init_integration: MockConfigEntry, freezer: Any
) -> None:
    """The watch list is looked at regularly; an error doesn't stop it."""
    with patch(
        "custom_components.middagsro.async_watch_check", side_effect=RemaError("down")
    ) as check:
        freezer.move_to(NOW + timedelta(hours=3, minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert check.called


async def test_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """The panel's commands for the watch list and the own favourites."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/watch/toggle", "item": {"text": "Bleer"}})
    msg = await client.receive_json()
    assert msg["result"]["watched"] is True
    assert msg["result"]["watch"][0]["key"] == "tbleer"

    with patch.object(
        init_integration.runtime_data.planner.chains, "async_offers", side_effect=fake_offers
    ):
        await client.send_json({"id": 2, "type": "middagsro/watch"})
        msg = await client.receive_json()
    assert msg["result"]["items"][0]["text"] == "Bleer"
    assert msg["result"]["notify"] == ""

    await client.send_json({"id": 3, "type": "middagsro/watch/check"})
    assert (await client.receive_json())["result"] == {"told": 0}

    product = {"id": 70001, "name": "RUGBRØD", "underline": "1 KG."}
    await client.send_json({"id": 4, "type": "middagsro/favorites/own", "product": product})
    assert (await client.receive_json())["result"][0]["id"] == 70001

    # Own favourites come after the app's hearts, marked as own.
    mock_client.async_get_products = AsyncMock(return_value=[make_product(70001, "RUGBRØD", 18.0)])
    await client.send_json({"id": 5, "type": "middagsro/favorites"})
    products = (await client.receive_json())["result"]["products"]
    assert products[-1]["id"] == 70001
    assert products[-1]["own"] is True
    assert products[0]["own"] is False
    mock_client.async_get_products = AsyncMock(side_effect=RemaError("down"))
    await client.send_json({"id": 6, "type": "middagsro/favorites"})
    assert (await client.receive_json())["success"]

    await client.send_json({"id": 7, "type": "middagsro/state"})
    state = (await client.receive_json())["result"]
    assert state["own_favorites"][0]["id"] == 70001
    assert state["notify_targets"][0]["id"] == "persistent_notification"

    await client.send_json(
        {"id": 8, "type": "middagsro/favorites/own", "product": product, "add": False}
    )
    assert (await client.receive_json())["result"] == []

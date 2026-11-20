"""Tests for the other webshops' baskets (compare and transfer) and item images."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import baskets
from custom_components.middagsro.api import Product, RemaError
from custom_components.middagsro.bilka import BILKA_ID
from custom_components.middagsro.nemlig import NEMLIG_ID
from homeassistant.core import HomeAssistant

from .conftest import make_plan


def _product(pid: int, name: str, price: float | None, image: str | None = None) -> Product:
    return Product(
        id=pid,
        name=name,
        underline="1 stk",
        department=None,
        category=None,
        price=price,
        normal_price=price,
        compare_unit=None,
        compare_unit_price=None,
        is_advertised=False,
        is_campaign=False,
        price_valid_to=None,
        upcoming_price=None,
        upcoming_from=None,
        upcoming_is_advertised=False,
        is_organic=False,
        labels=[],
        image=image,
    )


class FakeCart:
    """A webshop basket: amounts set absolutely, confirmed by one read."""

    pickup_name = "Bilka Kolding"

    def __init__(self, have: dict[int, int] | None = None, lose: int | None = None) -> None:
        self.have = dict(have or {})
        self.lose = lose
        self.set: list[tuple[int, int]] = []

    async def async_list(self) -> Any:
        return SimpleNamespace(
            items=[SimpleNamespace(id=k, amount=v) for k, v in self.have.items()]
        )

    def amount(self, product_id: int, shopping_list: Any = None) -> int:
        return self.have.get(product_id, 0)

    async def async_set_amount(self, product_id: int, amount: int, *, verify: bool = True) -> None:
        self.set.append((product_id, amount))
        if product_id != self.lose:
            self.have[product_id] = amount

    async def async_confirm(self, targets: dict[int, int]) -> set[int]:
        return {pid for pid, amount in targets.items() if self.have.get(pid) == amount}


def _entry(entry_id: str, store: str, client: Any) -> Any:
    return SimpleNamespace(
        entry_id=entry_id, data={"store": store}, runtime_data=SimpleNamespace(client=client)
    )


def _webshop(results: dict[str, list[Product]], cart: Any = None, prices: bool = True) -> Any:
    async def search(query: str, limit: int = 24) -> list[Product]:
        if query == "boom":
            raise RemaError("nede")
        return results.get(query, [])

    return SimpleNamespace(
        has_prices=prices, cart=cart, async_search_products=AsyncMock(side_effect=search)
    )


def _hass(*entries: Any) -> Any:
    hass = MagicMock()
    hass.config_entries.async_loaded_entries.return_value = list(entries)
    return hass


PLAN = {
    "id": "p1",
    "shopping": [
        {"id": "l1", "name": "Mælk", "search": "mælk", "packages": 2, "cost": 25.9},
        {"id": "l2", "name": "Rugbrød", "cost": 20.0},
        {"id": "l3", "name": "Pizza", "cost": 30.0, "skipped": True},
        {"id": "l4", "name": "Tilbud", "cost": 10.0, "buy_at": "netto"},
        {"id": "l5", "name": "Fejl", "search": "boom"},
        {"id": "l6", "name": "", "search": ""},
    ],
}


async def test_compare_searches_the_other_webshops() -> None:
    """Each webshop gets the lines bought at REMA, priced with the account's prices."""
    rema = _entry("rema", "rema", MagicMock())
    cart = FakeCart()
    nemlig = _entry(
        "nem",
        NEMLIG_ID,
        _webshop(
            {
                "mælk": [_product(1, "Uden pris", None), _product(2, "Minimælk", 11.0, "m.png")],
                "Rugbrød": [_product(3, "Rugbrød", 18.5)],
            },
            cart,
        ),
    )
    bilka_local = _entry("bil", BILKA_ID, _webshop({}, None))
    no_prices = _entry("old", NEMLIG_ID, _webshop({}, None, prices=False))
    netto = _entry("net", "netto", _webshop({}))
    result = await baskets.async_compare(
        _hass(rema, nemlig, bilka_local, no_prices, netto), rema, PLAN
    )
    assert result["own"] == {
        "entry_id": "rema",
        "store": "rema",
        "name": "REMA 1000",
        "count": 4,
        "total": 45.9,
        "priced": 2,
    }
    assert [s["entry_id"] for s in result["shops"]] == ["nem", "bil"]
    shop = result["shops"][0]
    assert shop["name"] == "Nemlig.com" and shop["basket"] and shop["pickup"] == "Bilka Kolding"
    assert shop["total"] == 40.5  # 2 x 11 + 18.5
    assert shop["items"][0]["product"] == {
        "id": 2,
        "name": "Minimælk",
        "underline": "1 stk",
        "price": 11.0,
        "image": "m.png",
    }
    assert shop["missing"] == ["Fejl", ""]
    assert result["shops"][1]["basket"] is False and result["shops"][1]["total"] == 0


async def test_transfer_sets_at_least_the_amount() -> None:
    """Only what the basket lacks is set, so pressing twice adds nothing."""
    rema = _entry("rema", "rema", MagicMock())
    cart = FakeCart(have={5: 3}, lose=7)
    nemlig = _entry("nem", NEMLIG_ID, _webshop({}, cart))
    hass = _hass(rema, nemlig)
    result = await baskets.async_transfer(
        hass,
        rema,
        "nem",
        [
            {"product_id": 5, "packages": 2},
            {"product_id": 6, "packages": 1},
            {"product_id": 6, "packages": 1},
            {"product_id": 7},
            {"product_id": 0},
        ],
    )
    assert result == {"store": "Nemlig.com", "added": 1, "already": 1, "failed": [7]}
    assert cart.set == [(6, 2), (7, 1)]
    again = await baskets.async_transfer(hass, rema, "nem", [{"product_id": 6, "packages": 2}])
    assert again["added"] == 0 and again["already"] == 1
    nothing = await baskets.async_transfer(hass, rema, "nem", [])
    assert nothing == {"store": "Nemlig.com", "added": 0, "already": 0, "failed": []}


async def test_transfer_needs_a_basket() -> None:
    """A webshop without a login (or not installed) has no basket."""
    rema = _entry("rema", "rema", MagicMock())
    local = _entry("bil", BILKA_ID, _webshop({}, None))
    with pytest.raises(ValueError, match="ingen kurv"):
        await baskets.async_transfer(_hass(rema, local), rema, "bil", [{"product_id": 1}])
    with pytest.raises(ValueError, match="ingen kurv"):
        await baskets.async_transfer(_hass(rema), rema, "nope", [{"product_id": 1}])


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """One stored plan."""
    return {"plans": [make_plan()]}


async def _ws(client: Any, msg_id: int, **msg: Any) -> dict[str, Any]:
    await client.send_json({"id": msg_id, **msg})
    result: dict[str, Any] = await client.receive_json()
    return result


async def test_websocket_compare_transfer_and_images(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """The panel's commands: compare (no other webshop here), transfer, images."""
    client = await hass_ws_client(hass)
    msg = await _ws(client, 1, type="middagsro/baskets/compare", plan_id="plan-1")
    assert msg["success"]
    assert msg["result"]["shops"] == [] and msg["result"]["own"]["name"] == "REMA 1000"

    msg = await _ws(client, 2, type="middagsro/baskets/compare", plan_id="gone")
    assert not msg["success"]

    msg = await _ws(
        client,
        3,
        type="middagsro/baskets/transfer",
        target_entry_id="nope",
        items=[{"product_id": 1, "packages": 2}],
    )
    assert not msg["success"]
    assert "kurv" in msg["error"]["message"]

    mock_client.async_search_products.reset_mock(side_effect=True)
    mock_client.async_search_products.side_effect = [
        [_product(1, "BROCCOLI", 10.0, "b.png")],
        RemaError("nede"),
        [_product(2, "Uden billede", 5.0)],
    ]
    msg = await _ws(
        client,
        4,
        type="middagsro/items/images",
        names=["BROCCOLI", "FEJL", "INGEN", "BROCCOLI", " "],
    )
    assert msg["result"] == {"BROCCOLI": "b.png", "FEJL": None, "INGEN": None}
    # Kept: asked again, only the failed one is searched again.
    mock_client.async_search_products.side_effect = [[_product(3, "FEJL", 1.0, "f.png")]]
    msg = await _ws(client, 5, type="middagsro/items/images", names=["BROCCOLI", "FEJL"])
    assert msg["result"] == {"BROCCOLI": "b.png", "FEJL": "f.png"}
    # With products: the matched product, so a receipt line can go straight on the list.
    msg = await _ws(
        client, 6, type="middagsro/items/images", names=["BROCCOLI", "INGEN"], products=True
    )
    assert msg["result"] == {
        "BROCCOLI": {"id": 1, "name": "BROCCOLI", "image": "b.png", "price": 10.0},
        "INGEN": {"id": 2, "name": "Uden billede", "image": None, "price": 5.0},
    }

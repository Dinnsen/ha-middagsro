"""Account, store selection and retry-safe transfer to BilkaToGo."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.middagsro.api import (
    RemaAuthError,
    RemaConnectionError,
    ShoppingList,
    ShoppingListItem,
)
from custom_components.middagsro.bilka import BilkaError, BilkaSearch, to_product
from custom_components.middagsro.bilka_cart import API, CONF_PICKUP, IDENTITY, BilkaCart, cart_items
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.store_client import BILKA_ID, CONF_STORE, BilkaStoreClient
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import EMAIL, PASSWORD, make_plan

LOCATION = {"id": "21046", "name": "Bilka Odense", "sid": "1654", "zip": "5230", "facility": 3}
OTHER = {"id": "3192", "name": "Bilka Waves", "sid": "1653", "zip": "2670", "facility": 3}


def response(amount: int = 1) -> dict[str, Any]:
    """An actual cart has nested department groups and order lines."""
    return {
        "uid": 42,
        "lines": [
            {
                "headline": "Services",
                "lines": [
                    {
                        "orderlines": [
                            {"quantity": 1, "product": {"objectID": 81474, "name": "Pakkeservice"}}
                        ]
                    }
                ],
            },
            {
                "headline": "Emballage",
                "lines": [
                    {
                        "orderlines": [
                            {"quantity": 1, "product": {"objectID": 81987, "name": "Papirpose"}}
                        ]
                    }
                ],
            },
            {
                "headline": "Mejeri",
                "lines": [
                    {
                        "orderlines": [
                            {
                                "quantity": amount,
                                "product": {
                                    "objectID": 84120,
                                    "name": "Letmælk",
                                    "price": 1500,
                                    "storeData": {"1654": {"price": 1105}},
                                },
                            }
                        ]
                    }
                ],
            },
        ],
    }


def client(hass: HomeAssistant) -> BilkaCart:
    return BilkaCart(async_get_clientsession(hass), BilkaSearch(hass), EMAIL, PASSWORD, "21046")


def test_cart_products_and_local_prices(hass: HomeAssistant) -> None:
    """Checkout services must never be treated as groceries or removed by clear-list."""
    items = cart_items(response(), "1654")
    assert [(i.id, i.amount, i.price) for i in items] == [(84120, 1, 11.05)]
    assert cart_items(response(0), "1654") == []
    with pytest.raises(BilkaError):
        cart_items({"lines": [{"product": {}, "quantity": "invalid"}]}, "1654")
    search = BilkaSearch(hass)
    search._searches["old"] = (0, [])
    search.set_store("1654")
    assert search.store_id == "1654" and search._searches == {}
    product = to_product(
        {"id": 1, "name": "Mælk", "price": 1500, "storeData": {"1654": {"price": 1105}}}, "1654"
    )
    assert product and product.price == 11.05


async def test_login_and_lowercase_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The production aiohttp client preserves the exact header Bilka expects."""
    cart = client(hass)
    aioclient_mock.post(
        f"{IDENTITY}/accounts.login", json={"sessionInfo": {"cookieValue": "session"}}
    )
    aioclient_mock.post(f"{IDENTITY}/accounts.getJWT", json={"id_token": "access"})
    aioclient_mock.post(f"{API}/auth/LoginJWT", json={"uid": 42})
    with patch.object(cart, "_key", AsyncMock(return_value="public-key")):
        assert await cart.async_login() == 42
        assert await cart.async_login() == 42
    assert aioclient_mock.call_count == 3
    assert aioclient_mock.mock_calls[-1][3]["jwt_token"] == "access"
    assert "Jwt_token" not in aioclient_mock.mock_calls[-1][3]


@pytest.mark.parametrize(
    "login,jwt,auth",
    [
        ({"errorCode": 403042}, {}, {}),
        ({}, {}, {}),
        ({"sessionInfo": {"cookieValue": "session"}}, {"errorCode": 403}, {}),
        ({"sessionInfo": {"cookieValue": "session"}}, {"id_token": "access"}, {"uid": -1}),
    ],
)
async def test_login_rejections(hass: HomeAssistant, login: dict, jwt: dict, auth: dict) -> None:
    cart = client(hass)
    with (
        patch.object(cart, "_key", AsyncMock(return_value="public-key")),
        patch.object(
            cart,
            "_json",
            AsyncMock(side_effect=[login, jwt, auth]),
        ),
        pytest.raises(RemaAuthError),
    ):
        await cart.async_login()


async def test_key_discovery(hass: HomeAssistant) -> None:
    cart = client(hass)
    bundle = 'NUXT_ENV_GIGYA_API_KEY:"public-key",NUXT_ENV_GIGYA_BASE_URL:"https://accounts.eu1.gigya.com"'
    with patch.object(
        cart.search,
        "_async_text",
        AsyncMock(
            side_effect=[
                '<script src="/_nuxt/test.js"></script>',
                bundle,
            ]
        ),
    ) as read:
        assert await cart._key() == "public-key"
        assert await cart._key() == "public-key"
        assert read.call_count == 2
    cart._login_key = None
    with (
        patch.object(cart.search, "_async_text", AsyncMock(return_value="")),
        pytest.raises(BilkaError),
    ):
        await cart._key()


@pytest.mark.parametrize(
    "status,error", [(401, RemaAuthError), (403, RemaAuthError), (500, BilkaError)]
)
async def test_http_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int, error: type
) -> None:
    aioclient_mock.get(f"{API}/test", status=status)
    with pytest.raises(error):
        await client(hass)._json(f"{API}/test")


async def test_network_and_malformed_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    cart = client(hass)
    aioclient_mock.get(f"{API}/test", exc=aiohttp.ClientError("secret request details"))
    with pytest.raises(RemaConnectionError, match=r"^Could not read BilkaToGo$"):
        await cart._json(f"{API}/test")
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/test", json=[])
    with pytest.raises(BilkaError):
        await cart._json(f"{API}/test")


async def test_physical_stores_only_and_selection(hass: HomeAssistant) -> None:
    cart = client(hass)
    data = {"addresses": [LOCATION, {**OTHER, "facility": 8}], "activeAddress": OTHER}
    with patch.object(cart, "_shop", AsyncMock(return_value=data)):
        assert await cart.async_locations() == [
            {k: LOCATION[k] for k in ("id", "name", "sid", "zip")}
        ]
    with patch.object(
        cart,
        "_shop",
        AsyncMock(
            side_effect=[
                data,
                data,
                {"eid": -1},
                {**data, "activeAddress": LOCATION},
            ]
        ),
    ) as shop:
        await cart.async_select_location()
    assert cart.store_id == "1654" and cart.search.store_id == "1654"
    assert cart.pickup_name == "Bilka Odense"
    assert shop.call_args_list[2].args == ("SetDeliveryAddress",)
    cart.pickup = "unknown"
    with patch.object(cart, "_shop", AsyncMock(return_value=data)), pytest.raises(BilkaError):
        await cart.async_select_location()


async def test_changed_store_blocks_write(hass: HomeAssistant) -> None:
    cart = client(hass)
    with (
        patch.object(cart, "_shop", AsyncMock(return_value={"activeAddress": OTHER})) as shop,
        pytest.raises(BilkaError),
    ):
        await cart.async_set_amount(84120, 2)
    assert shop.call_count == 1


async def test_cart_and_absolute_quantity(hass: HomeAssistant) -> None:
    cart = client(hass)
    cart.user_id = 42
    cart.store_id = "1654"
    location = {"activeAddress": LOCATION}
    with patch.object(cart, "_shop", AsyncMock(side_effect=[location, response()])):
        shopping = await cart.async_list()
    assert shopping.items[0].amount == 1
    two = ShoppingList(1, "BilkaToGo", [ShoppingListItem(84120, "Letmælk", False, 2, 84120)])
    with (
        patch.object(cart, "async_list", AsyncMock(side_effect=[shopping, two])),
        patch.object(
            cart,
            "_shop",
            AsyncMock(return_value={"eid": -1}),
        ) as shop,
    ):
        await cart.async_set_amount(84120, 2)
    assert shop.call_args.kwargs["params"] == {"productId": 84120, "count": 2, "fullCart": 0}
    with (
        patch.object(cart, "async_list", AsyncMock(side_effect=[shopping, two])),
        patch.object(
            cart,
            "_shop",
            AsyncMock(side_effect=RemaConnectionError),
        ),
    ):
        await cart.async_set_amount(84120, 2)  # timed-out write already took effect
    with (
        patch.object(cart, "async_list", AsyncMock(return_value=shopping)),
        patch.object(
            cart,
            "_shop",
            AsyncMock(return_value={"eid": -1}),
        ),
        pytest.raises(BilkaError),
    ):
        await cart.async_set_amount(84120, 2)  # a success-shaped response is not enough


async def test_retry_after_reauthentication(hass: HomeAssistant) -> None:
    cart = client(hass)
    with (
        patch.object(cart, "async_login", AsyncMock(return_value=42)) as login,
        patch.object(
            cart,
            "_json",
            AsyncMock(side_effect=[RemaAuthError, {"uid": 42}]),
        ),
    ):
        assert await cart._shop("Cart") == {"uid": 42}
    assert login.call_count == 2
    assert login.call_args.kwargs == {"force": True}


async def test_transfer_receipt_survives_retry_and_reload(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """An uncertain write and HA reload cannot turn one plan transfer into two."""
    shop = BilkaStoreClient(hass, async_get_clientsession(hass), "test", EMAIL, PASSWORD, "21046")
    assert shop.cart
    shopping = ShoppingList(1, "BilkaToGo", [ShoppingListItem(84120, "Mælk", False, 1, 84120)])
    with (
        patch.object(shop.cart, "async_list", AsyncMock(return_value=shopping)),
        patch.object(
            shop.cart,
            "async_set_amount",
            AsyncMock(side_effect=RemaConnectionError),
        ),
        pytest.raises(RemaConnectionError),
    ):
        await shop.async_add_once(shopping, operation_id="plan:line:0", amount=1, product_id=84120)
    again = BilkaStoreClient(hass, async_get_clientsession(hass), "test", EMAIL, PASSWORD, "21046")
    assert again.cart
    with patch.object(again.cart, "async_set_amount", AsyncMock()) as write:
        await again.async_add_once(shopping, operation_id="plan:line:0", amount=1, product_id=84120)
        await again.async_add_once(shopping, operation_id="plan:line:0", amount=1, product_id=84120)
    write.assert_awaited_once_with(84120, 2)


async def test_unmatched_cart_item_rejected(hass: HomeAssistant) -> None:
    shop = BilkaStoreClient(hass, async_get_clientsession(hass), "test", EMAIL, PASSWORD, "21046")
    with pytest.raises(BilkaError):
        await shop.async_create_item(1, name="Mælk")
    with pytest.raises(BilkaError):
        await shop.async_update_item(1, 84120, bought=True)


async def test_bilka_config_and_pickup(hass: HomeAssistant, mock_panel: Any) -> None:
    """A chain choice leads to Bilka credentials and an explicit warehouse choice."""
    with (
        patch(
            "custom_components.middagsro.config_flow.BilkaCart.async_login",
            AsyncMock(return_value=42),
        ),
        patch(
            "custom_components.middagsro.config_flow.BilkaCart.async_locations",
            AsyncMock(return_value=[LOCATION]),
        ),
        patch("custom_components.middagsro.async_setup_entry", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STORE: BILKA_ID}
        )
        assert result["step_id"] == "bilka"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
        )
        assert result["step_id"] == "bilka_pickup"
        with pytest.raises(InvalidData):
            await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PICKUP: "bad"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PICKUP: "21046"}
        )
        assert result["data"][CONF_PICKUP] == "21046"
        assert result["data"]["bilka_price_store"] == "1654"


async def test_upgrade_local_bilka_entry(hass: HomeAssistant, mock_panel: Any) -> None:
    """An existing local Bilka setup gains remote login without a second entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=f"store_{BILKA_ID}", data={CONF_STORE: BILKA_ID}
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.middagsro.config_flow.BilkaCart.async_login",
            AsyncMock(return_value=42),
        ),
        patch(
            "custom_components.middagsro.config_flow.BilkaCart.async_locations",
            AsyncMock(return_value=[LOCATION]),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STORE: BILKA_ID}
        )
        assert result["step_id"] == "reconfigure_bilka"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PICKUP: "21046"}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PICKUP] == "21046"
    assert entry.unique_id == f"store_{BILKA_ID}"


async def test_plan_preflight_and_duplicate_send(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Matched products are sent once; missing products stay visible and unsent."""
    data = init_integration.runtime_data
    shop = BilkaStoreClient(hass, async_get_clientsession(hass), "remote", EMAIL, PASSWORD, "21046")
    assert shop.cart
    data.client = data.shopping_list.client = data.planner.client = shop
    remote: dict[int, int] = {}

    def read() -> ShoppingList:
        return ShoppingList(
            1,
            "BilkaToGo",
            [ShoppingListItem(pid, "Vare", False, n, pid) for pid, n in remote.items()],
        )

    plan = make_plan()
    plan["shopping"] = plan["shopping"][:2]
    plan["shopping"][0]["product"] = {"id": 84120, "name": "Mælk"}
    await data.store.async_add_plan(plan)
    with (
        patch.object(data.planner, "_async_refresh_lines", AsyncMock()),
        patch.object(
            shop.cart,
            "async_list",
            AsyncMock(side_effect=read),
        ),
        patch.object(
            shop.cart,
            "async_set_amount",
            AsyncMock(side_effect=lambda pid, n: remote.update({pid: n})),
        ) as write,
    ):
        await data.planner.async_send(plan["id"], "all")
        assert plan["shopping"][0].get("sent")
        assert not plan["shopping"][1].get("sent")
        assert [item["name"] for item in plan["missing_products"]] == ["Persille"]
        assert remote == {84120: 1}
        assert plan["status"] == "draft"
        await data.planner.async_send(plan["id"], "all")
        assert write.await_count == 1  # retry only sees the still-missing ingredient
        plan["shopping"][1]["product"] = {"id": 33407, "name": "Booster"}
        await data.planner.async_send(plan["id"], "all")
        await data.planner.async_send(plan["id"], "all")
        assert remote == {84120: 1, 33407: 1}
        assert write.await_count == 2
        assert all(line.get("sent") for line in plan["shopping"])
        await data.planner.async_restore_sent(plan["id"])
        await data.planner.async_send(plan["id"], "all")
        assert remote == {84120: 1, 33407: 2}  # Restore repeats only the latest successful batch


async def test_old_chain_product_is_rematched_before_transfer(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Changing chains cannot send an old REMA product id to BilkaToGo."""
    data = init_integration.runtime_data
    shop = BilkaStoreClient(hass, async_get_clientsession(hass), "remote", EMAIL, PASSWORD, "21046")
    assert shop.cart
    shop.cart.store_id = "1654"
    data.client = data.shopping_list.client = data.planner.client = shop
    data.planner.bilka = shop.bilka
    plan = make_plan()
    plan["shopping"] = plan["shopping"][:1]
    assert plan["shopping"][0]["product"]["id"] == 30001
    plan["bilka_rematch"] = True
    await data.store.async_add_plan(plan)

    async def match(line: dict[str, Any]) -> None:
        line["product"] = {"id": 84120, "name": "Bilka-vare"}

    with (
        patch.object(data.planner, "_async_match", AsyncMock(side_effect=match)),
        patch.object(
            data.planner,
            "_async_refresh_lines",
            AsyncMock(),
        ),
        patch.object(shop.cart, "async_list", AsyncMock(return_value=ShoppingList(1, "BilkaToGo"))),
        patch.object(
            shop.cart,
            "async_set_amount",
            AsyncMock(),
        ) as write,
    ):
        await data.planner.async_send(plan["id"], "all")
    write.assert_awaited_once_with(84120, 1)
    assert plan["shopping"][0]["bilka_price_store"] == "1654"

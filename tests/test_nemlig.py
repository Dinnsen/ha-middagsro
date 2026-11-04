"""Nemlig.com: login, prices, the offer page as the week's avis, and the basket."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.middagsro.api import RemaAuthError, RemaConnectionError, ShoppingList
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.nemlig import (
    NEMLIG_ID,
    SEARCH,
    SITE,
    NemligClient,
    NemligError,
    basket_items,
    offer_groups,
    to_offer,
    to_product,
    week_of,
)
from custom_components.middagsro.store_client import (
    CONF_STORE,
    NemligStoreClient,
    rema_only,
    store_name,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import EMAIL, PASSWORD

SETTINGS = {
    "DeliveryZoneId": 44,
    "TimeslotUtc": "2026110514-120-900",
    "CombinedProductsAndSitecoreTimestamp": "wQvG-4Y6-IDRfkXU6",
    "UserId": "2630735",
}
BASE = f"{SITE}/webapi/wQvG-4Y6-IDRfkXU6/2026110514-120-900/44/2630735"
MILK = {
    "Id": "701012",
    "Name": "Letmælk 1,5% øko.",
    "Category": "Køl",
    "Description": "1 l / Arla ØKO",
    "Price": 13.95,
    "UnitPriceCalc": 13.95,
    "UnitPriceLabel": "kr/l",
    "Labels": ["Øko (dansk)", "Discount"],
    "PrimaryImage": "https://nemlig.com/img.jpg",
    "ProductMainGroupName": "Mejeri",
    "ProductSubGroupName": "Letmælk",
    "Availability": {"IsDeliveryAvailable": True},
}
JERSEY = {
    "Id": "5062510",
    "Name": "Letmælk 25% jersey øko.",
    "Description": "1 l / Naturmælk",
    "Price": 17.26,
    "UnitPriceLabel": "kr/l",
    "Labels": [],
    "Campaign": {
        "MinQuantity": 3,
        "CampaignPrice": 48.0,
        "IntervalStart": "2026-11-01T23:00:00Z",
        "IntervalEnd": "2026-11-08T22:59:59Z",
    },
}
PAGE = {
    "Settings": SETTINGS,
    "content": [
        {"TemplateName": "productlistshowallspot", "Heading": "Ugens Priskup",
         "ProductGroupId": "19046154-e839-4d3c-ad7f-9b5e4c9f9a9a"},
        {"TemplateName": "productlistshowallspot", "Heading": "Favoritter på tilbud",
         "ProductGroupId": "2b70a03a-2696-4820-bb8b-39e7502d103c"},
        {"children": [{"TemplateName": "productlistshowallspot", "Heading": "Skarp pris",
                       "ProductGroupId": "106c6141-1fca-4a06-8b02-8c9df6219c5a"}]},
        {"TemplateName": "banner", "ProductGroupId": "not-a-group"},
    ],
}  # fmt: skip


def basket(amount: int = 1) -> dict[str, Any]:
    return {
        "Lines": [
            {"Id": "2301199", "Name": "Agurk", "Quantity": amount, "ItemPrice": 10.0,
             "Description": "1 stk."},
            {"Id": "0", "Name": "Pose", "Quantity": 1},
        ]
    }  # fmt: skip


def login_mocks(aioclient_mock: AiohttpClientMocker, uid: str = "2630735") -> None:
    aioclient_mock.get(f"{SITE}/", text="<html></html>")
    aioclient_mock.get(f"{SITE}/webapi/Token", json={"access_token": "token", "expires_in": 300})
    aioclient_mock.post(f"{SITE}/webapi/login", json={"RedirectUrl": "/", "MergeSuccessful": True})
    aioclient_mock.get(f"{SITE}/webapi/user/GetCurrentUser", json={"DebitorId": uid})


def client(hass: HomeAssistant) -> NemligClient:
    return NemligClient(async_get_clientsession(hass), EMAIL, PASSWORD)


def test_products_offers_and_basket() -> None:
    product = to_product(MILK)
    assert product is not None
    assert (product.id, product.price, product.underline) == (701012, 13.95, "1 L / ARLA ØKO")
    assert (product.department, product.category, product.compare_unit) == (
        "Mejeri",
        "Letmælk",
        "l",
    )
    assert product.is_organic and product.is_campaign and not product.is_advertised
    assert to_product({**MILK, "Availability": {"IsDeliveryAvailable": False}}) is None
    assert to_product({"Id": "x", "Name": "Mælk", "Price": 1}) is None
    assert to_product({"Id": "1", "Name": "Mælk", "Price": "?"}) is None
    start, end = week_of(datetime(2026, 11, 4, 12, tzinfo=UTC))
    assert (start.weekday(), start.hour, end.weekday()) == (0, 0, 6)
    offer = to_offer(JERSEY, start, end)
    assert offer is not None
    assert (offer.price, offer.quantity, offer.product_ids) == (48.0, "3 stk.", (5062510,))
    assert offer.description.startswith("3 for 48.00 kr.")
    assert offer.valid_to == "2026-11-08T22:59:59Z"
    plain = to_offer(MILK, start, end)
    assert plain is not None and plain.price == 13.95 and plain.valid_from == start.isoformat()
    assert to_offer({"Id": "1"}, start, end) is None
    items = basket_items(basket(2))
    assert [(i.id, i.amount, i.price) for i in items] == [(2301199, 2, 10.0)]
    assert basket_items({"Lines": ["x", {"Id": "1", "Quantity": 0}]}) == []
    with pytest.raises(NemligError):
        basket_items({"Lines": [{"Id": "1", "Quantity": "many"}]})
    groups = offer_groups(PAGE["content"])
    assert [h for h, _g in groups] == ["Ugens Priskup", "Skarp pris"]  # no favourites
    assert store_name(NEMLIG_ID) == "Nemlig.com"
    assert "REMA's opskrifter" in rema_only(NEMLIG_ID)
    assert not any("Priser på alle varer" in line for line in rema_only(NEMLIG_ID))


async def test_login_search_offers_and_basket(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    nemlig = client(hass)
    login_mocks(aioclient_mock)
    assert await nemlig.async_login() == 2630735
    assert await nemlig.async_login() == 2630735  # logged in already: only the token
    login = next(c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/webapi/login"))
    assert login[3]["Authorization"] == "Bearer token"

    aioclient_mock.get(f"{SITE}/tilbud", json=PAGE)
    aioclient_mock.get(
        f"{BASE}/Products/GetByProductGroupId",
        json={"Products": [JERSEY, MILK, JERSEY, "x", {"Id": "0"}]},
    )
    offers = await nemlig.async_offers()
    assert [o.id for o in offers] == ["nemlig-5062510", "nemlig-701012"]
    assert await nemlig.async_offers() is offers  # kept for an hour
    catalogs = await nemlig.async_catalogs()
    assert catalogs[0].label.startswith("Nemlig.com tilbud uge ")
    assert catalogs[0].offer_count == 2
    assert [p.id for p in nemlig.known([5062510, 1])] == [5062510]

    aioclient_mock.get(SEARCH, json={"Products": {"Products": [MILK, "x"]}})
    found = await nemlig.async_search("  Letmælk ", 5)
    assert [p.id for p in found] == [701012]
    assert await nemlig.async_search("letmælk", 5) == found  # cached
    assert await nemlig.async_search(" ") == []
    search = next(c for c in aioclient_mock.mock_calls if str(c[1]).startswith(SEARCH))
    assert search[1].query["deliveryZoneId"] == "44"

    aioclient_mock.get(f"{SITE}/webapi/basket/GetBasket", json=basket(1))
    aioclient_mock.post(f"{SITE}/webapi/basket/AddToBasket", json=basket(1))
    shopping = await nemlig.async_list()
    assert shopping.name == "Nemlig.com" and nemlig.amount(2301199) == 1
    await nemlig.async_set_amount(2301199, 1)
    assert any("AddToBasket" in str(c[1]) for c in aioclient_mock.mock_calls)
    with pytest.raises(NemligError):
        await nemlig.async_set_amount(2301199, 3)  # the basket still has 1
    await nemlig.async_set_amount(5, 2, verify=False)
    assert await nemlig.async_confirm({}) == set()
    nemlig._amounts.clear()
    assert nemlig.amount(2301199, ShoppingList(id=1, name="x", items=shopping.items)) == 1
    await nemlig.async_select_location()


async def test_login_rejected_and_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    nemlig = client(hass)
    aioclient_mock.get(f"{SITE}/", text="")
    aioclient_mock.get(f"{SITE}/webapi/Token", json={"access_token": "token"})
    aioclient_mock.post(f"{SITE}/webapi/login", status=400)
    with pytest.raises(RemaAuthError):
        await nemlig.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/", text="")
    aioclient_mock.get(f"{SITE}/webapi/Token", json={"access_token": "token"})
    aioclient_mock.post(f"{SITE}/webapi/login", json={"ErrorMessage": "Forkert"})
    with pytest.raises(RemaAuthError):
        await nemlig.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/", text="")
    aioclient_mock.get(f"{SITE}/webapi/Token", json={"access_token": "token"})
    aioclient_mock.post(f"{SITE}/webapi/login", json={"RedirectUrl": "/"})
    aioclient_mock.get(f"{SITE}/webapi/user/GetCurrentUser", json={})
    with pytest.raises(RemaAuthError):
        await nemlig.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/", text="")
    aioclient_mock.get(f"{SITE}/webapi/Token", json={})
    with pytest.raises(NemligError):
        await nemlig.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/", text="")
    aioclient_mock.get(f"{SITE}/webapi/Token", json={"access_token": "token"})
    aioclient_mock.post(f"{SITE}/webapi/login", status=500)
    with pytest.raises(NemligError):
        await nemlig.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/", exc=aiohttp.ClientError("secret"))
    with pytest.raises(RemaConnectionError):
        await nemlig.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/", status=302, headers={"Location": "https://nemlig.queue-it.net/"})
    with pytest.raises(NemligError, match="kø"):
        await nemlig.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/webapi/Token", status=302, headers={"Location": "/other"})
    with pytest.raises(NemligError, match="videre"):
        await nemlig._async_token(force=True)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{SITE}/webapi/Token", status=302, headers={"Location": "https://x.queue-it.net"}
    )
    with pytest.raises(NemligError, match="kø"):
        await nemlig._async_token(force=True)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/webapi/Token", exc=TimeoutError())
    with pytest.raises(RemaConnectionError):
        await nemlig._async_token(force=True)


async def test_session_ended_logs_in_again(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    nemlig = client(hass)
    login_mocks(aioclient_mock)
    aioclient_mock.get(f"{SITE}/webapi/basket/GetBasket", status=401)
    with pytest.raises(RemaAuthError):
        await nemlig.async_list()  # twice rejected
    logins = [c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/webapi/login")]
    assert len(logins) == 2
    aioclient_mock.clear_requests()
    login_mocks(aioclient_mock)
    aioclient_mock.get(f"{SITE}/webapi/basket/GetBasket", json=["not", "a", "basket"])
    with pytest.raises(NemligError):
        await nemlig.async_list()
    aioclient_mock.clear_requests()
    login_mocks(aioclient_mock)
    aioclient_mock.get(f"{SITE}/tilbud", json={"Settings": {}})
    with pytest.raises(NemligError):
        await nemlig.async_search("mælk")
    aioclient_mock.clear_requests()
    login_mocks(aioclient_mock)
    aioclient_mock.get(f"{SITE}/tilbud", json=PAGE)
    aioclient_mock.get(f"{BASE}/Products/GetByProductGroupId", status=500)
    assert await nemlig.async_offers() == []
    aioclient_mock.post(f"{SITE}/webapi/basket/AddToBasket", exc=TimeoutError())
    aioclient_mock.get(f"{SITE}/webapi/basket/GetBasket", json=basket(2))
    await nemlig.async_set_amount(2301199, 2)  # timed out, but the basket has it


async def test_many_products_are_forgotten(hass: HomeAssistant) -> None:
    nemlig = client(hass)
    for pid in range(1, 3002):
        product = to_product({"Id": str(pid), "Name": "Vare", "Price": 1})
        assert product is not None
        nemlig._remember(product)
    assert len(nemlig._products) < 3000


async def test_store_client(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    store = NemligStoreClient(hass, async_get_clientsession(hass), "e", EMAIL, PASSWORD)
    assert store.has_prices and store.cart is store.nemlig and store.dealer_id == NEMLIG_ID
    login_mocks(aioclient_mock)
    aioclient_mock.get(f"{SITE}/tilbud", json=PAGE)
    aioclient_mock.get(f"{BASE}/Products/GetByProductGroupId", json={"Products": [JERSEY]})
    assert await store.async_login() == 2630735
    catalogs = await store.async_get_catalogs()
    offers = await store.async_get_offers(catalogs[0].id)
    assert await store.async_get_offer_products(offers) == offers
    assert [p.id for p in await store.async_get_products([5062510])] == [5062510]
    aioclient_mock.post(f"{SITE}/webapi/basket/AddToBasket", json=basket(1))
    aioclient_mock.get(f"{SITE}/webapi/basket/GetBasket", json=basket(1))
    with pytest.raises(NemligError, match=r"Nemlig\.com-vare"):
        await store.async_create_item(1, amount=1, name="Agurk")
    assert await store.async_create_item(1, amount=1, product_id=2301199) == {"id": 2301199}


async def test_config_flow(hass: HomeAssistant, mock_panel: Any) -> None:
    with (
        patch(
            "custom_components.middagsro.config_flow.NemligClient.async_login",
            AsyncMock(return_value=2630735),
        ),
        patch("custom_components.middagsro.async_setup_entry", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STORE: NEMLIG_ID}
        )
        assert result["step_id"] == "nemlig"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: f" {EMAIL} ", CONF_PASSWORD: PASSWORD}
        )
        assert result["data"] == {
            CONF_STORE: NEMLIG_ID,
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: PASSWORD,
            "nemlig_user_id": 2630735,
        }
        # Only one Nemlig.com.
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STORE: NEMLIG_ID}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
        )
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [(RemaAuthError("x"), "invalid_auth"), (NemligError("x"), "cannot_connect"),
     (RuntimeError("x"), "unknown")],
)  # fmt: skip
async def test_config_flow_errors(
    hass: HomeAssistant, mock_panel: Any, error: Exception, expected: str
) -> None:
    with patch(
        "custom_components.middagsro.config_flow.NemligClient.async_login",
        AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STORE: NEMLIG_ID}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
        )
    assert result["errors"] == {"base": expected}


async def test_reconfigure_and_reauth(hass: HomeAssistant, mock_panel: Any) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="store_netto", data={CONF_STORE: "9ba51"})
    entry.add_to_hass(hass)
    login = AsyncMock(return_value=2630735)
    with (
        patch("custom_components.middagsro.config_flow.NemligClient.async_login", login),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STORE: NEMLIG_ID}
        )
        assert result["step_id"] == "reconfigure_nemlig"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
        )
        assert result["reason"] == "reconfigure_successful"
        assert entry.data[CONF_STORE] == NEMLIG_ID

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "nyt"}
        )
        assert result["reason"] == "reauth_successful"
        assert entry.data[CONF_PASSWORD] == "nyt"

        login.return_value = 1
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "andet"}
        )
        assert result["reason"] == "wrong_account"

        login.side_effect = RemaAuthError("x")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "forkert"}
        )
        assert result["errors"] == {"base": "invalid_auth"}


async def test_setup_entry_uses_nemlig(hass: HomeAssistant, mock_panel: Any) -> None:
    """A Nemlig entry gets the Nemlig client (its login failing: not ready)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="store_nemlig",
        data={CONF_STORE: NEMLIG_ID, CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    with patch.object(
        NemligStoreClient, "async_login", AsyncMock(side_effect=NemligError("nede"))
    ) as login:
        await hass.config_entries.async_setup(entry.entry_id)
    login.assert_awaited()
    assert entry.state.name == "SETUP_RETRY"

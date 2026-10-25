"""Tests for 2.8.0: Bilka ToGo's prices on every item."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import bilka, chains as ch
from custom_components.middagsro.api import RemaClient, RemaConnectionError
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.store_client import (
    CONF_STORE,
    REMA,
    REMA_ONLY,
    BilkaStoreClient,
    rema_only,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import CURRENT, NOW, OFFERS, UPCOMING, make_plan, make_product, store_data

SITE = "https://www.bilkatogo.dk"
ALGOLIA = f"https://APPID123-dsn.algolia.net/1/indexes/{bilka.INDEX}/query"
KEY = "0123456789abcdef0123456789abcdef"
BUNDLE = f'x={{NUXT_ENV_ALGOLIA_APP_ID:"APPID123",NUXT_ENV_ALGOLIA_SEARCH_API_KEY:"{KEY}"}}'

HIT = {
    "objectID": "146674",
    "id": 146674,
    "name": "Hakket oksekød 4-7% fedt",
    "brand": "Slagteren",
    "netcontent": "1000 g",
    "price": 12900,
    "sales_price": 10900,
    "categories": {"lvl0": ["Kød og fisk"], "lvl1": ["Kød og fisk > Oksekød"]},
    "targetOrganic": 0,
    "isInCurrentLeaflet": True,
    "images": ["https://digitalassets.sallinggroup.com/x.jpg"],
    "storeData": {"1653": {"unitsOfMeasurePriceUnit": "Kg.", "unitsOfMeasureShowPrice": 10900}},
}


def test_to_product() -> None:
    """A Bilka ToGo hit in the shape of REMA's products (prices are in øre)."""
    product = bilka.to_product(HIT)
    assert product is not None
    assert product.id == 146674
    assert product.name == "Hakket oksekød 4-7% fedt"
    assert product.underline == "1000 G / SLAGTEREN"
    assert (product.price, product.normal_price) == (109.0, 129.0)
    assert (product.compare_unit, product.compare_unit_price) == ("kg", 109.0)
    assert product.is_advertised and product.is_campaign
    assert product.department == "Kød og fisk"
    assert product.category == "Oksekød"
    assert product.image == "https://digitalassets.sallinggroup.com/x.jpg"
    assert not product.is_organic

    plain = bilka.to_product(
        {"id": "7", "name": "Letmælk øko", "price": 1405, "sales_price": 1405, "targetOrganic": 0}
    )
    assert plain is not None
    assert plain.is_organic
    assert not plain.is_campaign
    assert plain.underline is None
    assert plain.image is None
    assert bilka.to_product({"name": "Uden id", "price": 100}) is None
    assert bilka.to_product({"id": 1, "name": "Uden pris"}) is None
    assert bilka.to_product({"id": 1, "price": "x", "name": "Pris?"}) is None


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan from sunday 18/10 for the REMA entry."""
    return {"plans": [make_plan("plan-1", start="2026-10-18")]}


def _site(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(
        f"{SITE}/",
        text='<script defer src="/_nuxt/a.js"></script><script src="/_nuxt/b.js"></script>',
    )
    aioclient_mock.get(f"{SITE}/_nuxt/b.js", text="nothing here")
    aioclient_mock.get(f"{SITE}/_nuxt/a.js", text=BUNDLE)


async def test_search(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The key is read from the webshop's JavaScript, and searches are kept an hour."""
    _site(aioclient_mock)
    aioclient_mock.post(ALGOLIA, json={"hits": [HIT, {"name": "x"}, "nej"]})
    search = bilka.BilkaSearch(hass)
    found = await search.async_search("  Hakket   OKSEKØD ", 100)
    assert [p.id for p in found] == [146674]
    request = aioclient_mock.mock_calls[-1]
    assert request[2]["query"] == "hakket oksekød"
    assert request[2]["hitsPerPage"] == 40
    assert request[3]["x-algolia-api-key"] == KEY
    calls = aioclient_mock.call_count
    assert [p.id for p in await search.async_search("hakket oksekød", 100)] == [146674]
    assert aioclient_mock.call_count == calls  # kept
    assert await search.async_search(" ") == []
    assert [p.id for p in search.known([146674, 5])] == [146674]


async def test_new_key(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A key Algolia no longer takes is read again."""
    _site(aioclient_mock)
    answers = iter([401, 200])

    async def answer(method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        status = next(answers)
        return AiohttpClientMockResponse(
            method, url, status=status, json={"hits": [HIT]} if status == 200 else {}
        )

    aioclient_mock.post(ALGOLIA, side_effect=answer)
    found = await bilka.BilkaSearch(hass).async_search("oksekød")
    assert len(found) == 1
    assert sum(1 for c in aioclient_mock.mock_calls if str(c[1]) == f"{SITE}/") == 2


async def test_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """No key on the page, a search that fails, a webshop that is down."""
    aioclient_mock.get(f"{SITE}/", text='<script src="/_nuxt/b.js"></script>')
    aioclient_mock.get(f"{SITE}/_nuxt/b.js", text="nothing here")
    search = bilka.BilkaSearch(hass)
    with pytest.raises(bilka.BilkaError):
        await search.async_search("mælk")
    calls = aioclient_mock.call_count
    with pytest.raises(bilka.BilkaError):
        await search.async_search("mælk")  # not looked for again at once
    assert aioclient_mock.call_count == calls

    aioclient_mock.clear_requests()
    _site(aioclient_mock)
    aioclient_mock.post(ALGOLIA, status=500)
    search = bilka.BilkaSearch(hass)
    with pytest.raises(bilka.BilkaError):
        await search.async_search("mælk")

    aioclient_mock.clear_requests()
    _site(aioclient_mock)
    aioclient_mock.post(ALGOLIA, exc=aiohttp.ClientError("nede"))
    with pytest.raises(RemaConnectionError):
        await search.async_search("mælk")

    aioclient_mock.clear_requests()
    _site(aioclient_mock)
    aioclient_mock.post(ALGOLIA, status=403)
    with pytest.raises(bilka.BilkaError):
        await bilka.BilkaSearch(hass).async_search("mælk")

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SITE}/", status=503)
    with pytest.raises(bilka.BilkaError):
        await bilka.BilkaSearch(hass).async_search("mælk")


async def test_many_products(hass: HomeAssistant) -> None:
    """The products remembered are kept to a few thousand."""
    search = bilka.BilkaSearch(hass)
    hits = [{**HIT, "id": i} for i in range(bilka.MAX_PRODUCTS + 5)]
    with patch.object(search, "_async_query", AsyncMock(return_value=hits)):
        await search.async_search("alt")
    assert len(search._products) <= bilka.MAX_PRODUCTS
    assert search._searches == {}


def test_what_bilka_has() -> None:
    """Bilka has prices on every item; the other shops only their offers'."""
    assert rema_only(REMA) == []
    assert rema_only("9ba51") == list(REMA_ONLY)
    assert "REMA's opskrifter" in rema_only(bilka.BILKA_ID)
    assert not any("Priser" in line for line in rema_only(bilka.BILKA_ID))


async def test_bilka_store_client(hass: HomeAssistant) -> None:
    """Bilka as the shop: products and prices from its webshop."""
    client = BilkaStoreClient(hass, async_get_clientsession(hass), "e1")
    assert client.has_prices is True
    assert client.dealer_id == bilka.BILKA_ID
    product = make_product(1, "Spaghetti", 8.0, underline="500 G")
    with patch.object(client.bilka, "async_search", AsyncMock(return_value=[product])):
        assert await client.async_search_products("spaghetti") == [product]
        assert await client.async_search_products_at("spaghetti", 5, [NOW, NOW]) == [
            [product],
            [product],
        ]
    client.bilka._products[1] = product
    assert await client.async_get_products([1, 2]) == [product]


@pytest.fixture
async def bilka_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_panel: tuple[AsyncMock, MagicMock],
    freezer: Any,
) -> AsyncGenerator[MockConfigEntry]:
    """Middagsro set up for Bilka."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Copenhagen")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Middagsro – Bilka",
        unique_id=f"store_{bilka.BILKA_ID}",
        data={CONF_STORE: bilka.BILKA_ID},
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


async def test_set_up_for_bilka(
    hass: HomeAssistant, bilka_entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Bilka has prices: the planner matches products like with REMA 1000."""
    data = bilka_entry.runtime_data
    planner = data.planner
    assert isinstance(data.client, BilkaStoreClient)
    assert planner.prices is True
    assert planner.shop == "Bilka"
    assert planner.dealer_id == bilka.BILKA_ID
    assert planner.bilka is data.client.bilka
    assert not ch.wants_bilka(planner)  # the shop itself

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/state"})
    shop = (await client.receive_json())["result"]["shop"]
    assert (shop["name"], shop["rema"], shop["prices"]) == ("Bilka", False, True)
    assert "REMA's opskrifter" in shop["rema_only"]

    spaghetti = make_product(11, "Spaghetti", 8.0, underline="500 G / SALLING")
    line: dict[str, Any] = {"name": "Spaghetti", "search": "spaghetti", "amount": 500,
                            "unit": "g", "category": "Kolonial"}  # fmt: skip
    with patch.object(planner.bilka, "async_search", AsyncMock(return_value=[spaghetti])):
        await planner._async_match(line, None, None)
    assert line["product"]["id"] == 11
    assert line["cost"] == 8.0


async def test_compare_with_bilka(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """With Bilka among the chains, every item is compared with Bilka's price."""
    planner = init_integration.runtime_data.planner
    plan = planner.store.plans[0]
    line = plan["shopping"][0]
    line["product"] = {"id": 30001, "name": "SPAGHETTI", "underline": "500 GR.", "price": 12.0}
    line["search"] = "spaghetti"
    planner.store.settings["chains"] = [bilka.BILKA_ID]
    cheap = make_product(5, "Spaghetti", 8.0, underline="500 G / SALLING")
    organic = make_product(6, "Spaghetti øko", 9.0, underline="500 G", is_organic=True)
    assert ch.wants_bilka(planner)
    with (
        patch.object(planner.chains, "async_offers", AsyncMock(return_value=[])),
        patch.object(planner.bilka, "async_search", AsyncMock(return_value=[cheap, organic])),
    ):
        result = await ch.async_compare(planner, plan["id"])
    found = result["lines"][line["id"]]
    assert found["dealer_id"] == bilka.BILKA_ID
    assert found["heading"] == "Spaghetti"
    assert found["saving"] == 4.0
    assert result["chains"][bilka.BILKA_ID]["count"] == 1
    assert ch.bilka_entry(organic)["description"] == "500 G Økologisk"

    # Bilka can't be read: nothing from it.
    with (
        patch.object(planner.chains, "async_offers", AsyncMock(return_value=[])),
        patch.object(planner.bilka, "async_search", AsyncMock(side_effect=bilka.BilkaError("x"))),
    ):
        assert (await ch.async_compare(planner, plan["id"]))["lines"] == {}

    # Not among the chains: not searched.
    planner.store.settings["chains"] = []
    search = AsyncMock(return_value=[cheap])
    with patch.object(planner.bilka, "async_search", search):
        await ch.async_compare(planner, plan["id"])
    search.assert_not_called()


async def test_search_everywhere_with_bilka(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The price search shows Bilka's products, at their everyday price."""
    planner = init_integration.runtime_data.planner
    planner.store.settings["chains"] = [bilka.BILKA_ID]
    cheap = make_product(5, "Spaghetti", 8.0, underline="500 G", normal_price=10.0)
    other = make_product(6, "Lasagneplader", 15.0, underline="250 G")
    with (
        patch.object(planner.chains, "async_offers", AsyncMock(return_value=[])),
        patch.object(planner.bilka, "async_search", AsyncMock(return_value=[cheap, other])),
    ):
        result = await ch.async_search_everywhere(planner, "spaghetti")
    entries = [o for o in result["offers"] if o["dealer_id"] == bilka.BILKA_ID]
    assert [o["heading"] for o in entries] == ["Spaghetti"]
    assert entries[0]["full_price"] is True
    assert entries[0]["pre_price"] == 10.0
    assert entries[0]["unit_price"] == {"unit": "kg", "price": 16.0}

"""Tests for other chains' offers: their pages, cheaper items and the shops' own lists."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import chains as ch
from custom_components.middagsro.storage import clean_settings
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import make_plan, make_product

NETTO = "9ba51"
LIDL = "71c90"
RUN = {"run_from": "2026-10-16T22:00:00+0000", "run_till": "2026-10-23T21:59:59+0000"}


def tjek_offer(
    offer_id: str, heading: str, price: float, description: str = "", **extra: Any
) -> dict[str, Any]:
    """An offer as Tjek has it."""
    return {
        "id": offer_id,
        "heading": heading,
        "description": description,
        "pricing": {"price": price, "pre_price": None},
        "quantity": extra.pop("quantity", {}),
        "images": {"thumb": f"https://img/{offer_id}.jpg"},
        **RUN,
        **extra,
    }


CATALOGS = [
    {"id": "c-food", "label": "Netto uge 43", **RUN},
    {"id": "c-toys", "label": "Julekatalog", **RUN},
    {
        "id": "c-old",
        "label": "Uge 41",
        "run_from": "2026-10-01T00:00:00+0000",
        "run_till": "2026-10-08T00:00:00+0000",
    },
    "ikke en dict",
]
OFFERS = [
    tjek_offer("o1", "Hakket oksekød 8-12%", 25, "500 g. Dansk"),
    tjek_offer(
        "o2",
        "Danske frilandsæg",
        12,
        "6 stk.",
        quantity={"unit": {"symbol": "pcs"}, "size": {"from": 6, "to": 6}},
    ),
    tjek_offer("o3", "Spaghetti", 7.5, "500 g"),
    tjek_offer("o4", "Persille", 20, "Pr. bundt"),
    {"id": "o5", "heading": ""},
]


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan and the chains the family uses."""
    plan = make_plan("p", start="2026-10-18")
    plan["shopping"][0]["packages"] = 2
    plan["shopping"][0]["cost"] = 80.0
    plan["shopping"][0]["product"]["price"] = 40.0
    plan["shopping"][1]["product"] = {
        "id": 7,
        "name": "PERSILLE",
        "underline": "BUNDT",
        "price": 10.0,
    }
    plan["shopping"].append(
        {"id": "egg", "name": "Æg", "amount": 12, "unit": "stk", "packages": 1, "cost": 30.0,
         "product": {"id": 40002, "name": "FRILANDSÆG", "underline": "12 STK. / M/L", "price": 30.0}}
    )  # fmt: skip
    return {"plans": [plan], "settings": {"chains": [NETTO, "ukendt", NETTO]}}


class FakeTjek:
    """Answers ChainOffers._get like Tjek does."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail: set[str] = set()

    async def __call__(self, path: str, params: dict[str, Any]) -> Any:
        self.calls.append((path, params))
        if path in self.fail:
            raise ch.ChainError("down")
        if path == "/v2/dealers":
            return [{"id": NETTO, "color": "FFD950", "logo": "https://logo/netto"}, {"id": "x"}, 5]
        if path == "/v2/catalogs":
            return CATALOGS
        if path == "/v2/offers":
            page = OFFERS if params["catalog_ids"] == "c-food" else []
            return page[params["offset"] : params["offset"] + 100]
        raise AssertionError(path)


def test_helpers() -> None:
    """Food aviser, offers and when they run."""
    assert ch.is_food_catalog("Netto uge 43")
    assert not ch.is_food_catalog("Bilka Nonfood Uge 43")
    offer = ch.offer_dict(OFFERS[1], NETTO)
    assert offer["quantity"] == "6 stk."
    assert (offer["image"], offer["dealer_id"]) == ("https://img/o2.jpg", NETTO)
    assert ch.as_offer(offer).heading == "Danske frilandsæg"
    assert ch.runs_on(offer, date(2026, 10, 20))
    assert not ch.runs_on(offer, date(2026, 10, 25))
    assert ch.runs_on({"valid_from": None, "valid_to": None}, date(2026, 1, 1))
    assert clean_settings({"chains": [NETTO, LIDL, NETTO, "x", 5]})["chains"] == [NETTO, LIDL]


def test_cheaper() -> None:
    """Only the same kind of item, in the same size, and enough cheaper."""
    offers = [ch.offer_dict(o, NETTO) for o in OFFERS[:4]]
    day = date(2026, 10, 20)
    beef = {
        "packages": 2,
        "product": {"name": "HK. OKSEKØD 8-12%", "underline": "500 GR. / DANSK", "price": 40.0},
    }
    found = ch.cheaper_offer(beef, offers, day)
    assert found is not None
    assert (found["offer_id"], found["saving"]) == ("o1", 30.0)
    # 6 eggs for 12 kr. is 24 kr. for REMA's 12.
    eggs = {"packages": 1, "product": {"name": "FRILANDSÆG", "underline": "12 STK.", "price": 30.0}}
    assert ch.cheaper_offer(eggs, offers, day)["per_package"] == 24.0  # type: ignore[index]
    assert (
        ch.cheaper_offer({**eggs, "product": {**eggs["product"], "price": 24.5}}, offers, day)
        is None
    )
    pasta = {"product": {"name": "SPAGHETTI", "underline": "500 GR.", "price": 8.0}}
    assert ch.cheaper_offer(pasta, offers, day) is None  # 50 øre is not worth it
    assert ch.cheaper_offer(beef, offers, date(2026, 11, 1)) is None  # over by then
    assert ch.cheaper_offer({**beef, "buy_at": NETTO}, offers, day) is None
    assert ch.cheaper_offer({"product": {"name": "", "price": 5}}, offers, day) is None
    assert ch.cheaper_offer({"product": None}, offers, day) is None
    organic = {
        "product": {
            "name": "HK. OKSEKØD 8-12%",
            "underline": "500 GR.",
            "price": 60.0,
            "is_organic": True,
        }
    }
    assert ch.cheaper_offer(organic, offers, day) is None
    no_price = [{**offers[0], "price": None}]
    assert ch.cheaper_offer(beef, no_price, day) is None


async def test_reading_tjek(hass: HomeAssistant) -> None:
    """Logos, a chain's food offers, and caching."""
    chains = ch.ChainOffers(hass)
    fake = FakeTjek()
    with patch.object(chains, "_get", new=fake):
        dealers = await chains.async_dealers()
        assert dealers[NETTO] == {
            "id": NETTO,
            "name": "Netto",
            "color": "#FFD950",
            "logo": "https://logo/netto",
        }
        assert dealers[LIDL]["logo"] is None
        assert await chains.async_dealers() is dealers  # cached
        offers = await chains.async_offers(NETTO)
        assert [o["id"] for o in offers] == ["o1", "o2", "o3", "o4"]
        assert offers[0]["catalog"] == "Netto uge 43"
        assert await chains.async_offers(NETTO) is offers
        catalogs = [c for c in fake.calls if c[0] == "/v2/catalogs"]
        assert catalogs[0][1]["r_radius"] == 30000  # near home
        with pytest.raises(ServiceValidationError):
            await chains.async_offers("ukendt")
        fake.fail.add("/v2/dealers")
        fresh = ch.ChainOffers(hass)
    with patch.object(fresh, "_get", new=fake):
        assert (await fresh.async_dealers())[NETTO]["logo"] is None  # names only
    hass.config.latitude = hass.config.longitude = 0
    assert ch.ChainOffers(hass)._near() == {}


async def test_paging(hass: HomeAssistant) -> None:
    """A big avis is read 100 offers at a time."""
    chains = ch.ChainOffers(hass)
    many = [tjek_offer(f"m{i}", f"Vare {i}", 10) for i in range(150)]

    async def get(path: str, params: dict[str, Any]) -> Any:
        if path == "/v2/catalogs":
            return [{"id": "big", "label": "Uge 43", **RUN}]
        return many[params["offset"] : params["offset"] + 100]

    with patch.object(chains, "_get", new=get):
        assert len(await chains.async_offers(NETTO, force=True)) == 150


async def test_get(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Tjek's public API; errors as ChainError."""
    chains = ch.ChainOffers(hass)
    aioclient_mock.get(f"{ch.TJEK}/v2/dealers", json=[{"id": NETTO}])
    aioclient_mock.get(f"{ch.TJEK}/v2/catalogs", status=500)
    aioclient_mock.get(f"{ch.TJEK}/v2/offers", exc=aiohttp.ClientError("down"))
    assert await chains._get("/v2/dealers", {"dealer_ids": NETTO}) == [{"id": NETTO}]
    for path in ("/v2/catalogs", "/v2/offers"):
        with pytest.raises(ch.ChainError):
            await chains._get(path, {})


async def test_plan_and_lists(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Cheaper items in the plan, moving them to the shop's list, ticking off and clearing."""
    planner = init_integration.runtime_data.planner
    store = planner.store
    assert store.settings["chains"] == [NETTO]
    with patch.object(planner.chains, "_get", new=FakeTjek()):
        result = await ch.async_compare(planner, "p")
        products = await ch.async_compare_products(
            planner,
            [{"id": 7, "name": "PERSILLE", "underline": "BUNDT", "price": 30.0}, {"name": "x"}, 5],
            date(2026, 10, 20),
        )
    plan = store.get_plan("p")
    assert plan is not None
    beef = plan["shopping"][0]["id"]
    assert set(result["lines"]) == {beef, "egg"}
    assert result["chains"][NETTO]["count"] == 2
    assert result["chains"][NETTO]["saving"] == 36.0
    assert list(products) == ["7"]
    with pytest.raises(ServiceValidationError):
        await ch.async_compare(planner, "nope")

    # Buy the beef at Netto: not on the REMA list, Netto's price.
    plan = await ch.async_move_line(planner, "p", beef, NETTO, 25.0, "Hakket oksekød 8-12%")
    line = plan["shopping"][0]
    assert (line["buy_at"], line["cost"], line["bought"]) == (NETTO, 50.0, False)
    with patch.object(planner, "_add_items") as add:
        await planner.async_send("p")
    sent = add.call_args.args[0]
    assert all(item.get("product_id") != 30001 for item in sent)
    with patch.object(planner.chains, "_get", new=FakeTjek()):
        assert beef not in (await ch.async_compare(planner, "p"))["lines"]

    plan = await ch.async_chain_line(planner, "p", beef, packages=3)
    assert plan["shopping"][0]["cost"] == 75.0
    plan = await ch.async_chain_line(planner, "p", beef, bought=True)
    # An offer from Netto's page, straight onto Netto's list.
    plan = await ch.async_add_offer(
        planner,
        "p",
        {"dealer_id": NETTO, "heading": "Kaffe", "price": "39", "description": "400 g"},
    )
    coffee = plan["shopping"][-1]
    assert (coffee["buy_at"], coffee["cost"], coffee["chain_only"]) == (NETTO, 39.0, True)
    plan = await ch.async_add_offer(
        planner, "p", {"dealer_id": NETTO, "heading": "Te", "price": "x"}
    )
    assert plan["shopping"][-1]["cost"] == 0
    with pytest.raises(ServiceValidationError):
        await ch.async_add_offer(planner, "p", {"dealer_id": "x", "heading": "Kaffe"})
    plan = await ch.async_chain_line(planner, "p", coffee["id"], packages=2)
    assert plan["shopping"][-2]["cost"] == 78.0
    # The basket is emptied: the bought beef leaves the plan.
    plan = await ch.async_clear_chain(planner, "p", NETTO)
    assert beef not in {line["id"] for line in plan["shopping"]}
    # Back to REMA, and deleting.
    plan = await ch.async_move_line(planner, "p", "egg", NETTO, None, None)
    assert plan["shopping"][-3]["cost"] == 30.0
    plan = await ch.async_move_line(planner, "p", "egg", None)
    egg = next(line for line in plan["shopping"] if line["id"] == "egg")
    assert "buy_at" not in egg
    assert egg["cost"] == 30.0
    plan = await ch.async_move_line(planner, "p", coffee["id"], None)  # only Netto has it
    assert coffee["id"] not in {line["id"] for line in plan["shopping"]}
    tea = plan["shopping"][-1]["id"]
    plan = await ch.async_chain_line(planner, "p", tea, delete=True)
    assert tea not in {line["id"] for line in plan["shopping"]}
    with pytest.raises(ServiceValidationError):
        await ch.async_chain_line(planner, "p", "egg", bought=True)  # not on a shop's list
    with pytest.raises(ServiceValidationError):
        await ch.async_chain_line(planner, "p", "nope")
    for call in (
        ch.async_move_line(planner, "nope", "egg", NETTO),
        ch.async_move_line(planner, "p", "egg", "ukendt"),
        ch.async_add_offer(planner, "nope", {}),
        ch.async_chain_line(planner, "nope", "egg"),
        ch.async_clear_chain(planner, "nope", NETTO),
    ):
        with pytest.raises(ServiceValidationError):
            await call


async def test_compare_when_tjek_is_down(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Nothing is cheaper when the offers can't be read."""
    planner = init_integration.runtime_data.planner
    fake = FakeTjek()
    fake.fail.add("/v2/catalogs")
    with patch.object(planner.chains, "_get", new=fake):
        assert (await ch.async_compare(planner, "p"))["lines"] == {}
        assert (
            await ch.async_compare_products(
                planner, [{"id": 1, "name": "X", "price": 5}], date(2026, 10, 20)
            )
            == {}
        )


async def test_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """The panel's commands for other chains."""
    planner = init_integration.runtime_data.planner
    client = await hass_ws_client(hass)

    async def ws(msg_id: int, **msg: Any) -> dict[str, Any]:
        await client.send_json({"id": msg_id, **msg})
        result: dict[str, Any] = await client.receive_json()
        return result

    fake = FakeTjek()
    with patch.object(planner.chains, "_get", new=fake):
        chains = (await ws(1, type="middagsro/chains"))["result"]["chains"]
        assert [c["name"] for c in chains[:2]] == ["REMA 1000", "Netto"]
        offers = (await ws(2, type="middagsro/chains/offers", dealer_id=NETTO))["result"]
        assert len(offers["offers"]) == 4
        compare = (await ws(3, type="middagsro/chains/compare", plan_id="p"))["result"]
        assert compare["chains"][NETTO]["count"] == 2
        found = await ws(
            4,
            type="middagsro/chains/products",
            products=[{"id": 7, "name": "PERSILLE", "underline": "BUNDT", "price": 30}],
            date="2026-10-20",
        )
        assert list(found["result"]["products"]) == ["7"]
        fake.fail.add("/v2/catalogs")
        failed = await ws(5, type="middagsro/chains/offers", dealer_id=LIDL, force=True)
        assert failed["error"]["code"] == "middagsro_error"
    moved = await ws(
        6,
        type="middagsro/chains/move",
        plan_id="p",
        line_id="egg",
        dealer_id=NETTO,
        price=24,
        heading="Æg",
    )
    assert moved["result"]["shopping"][-1]["buy_at"] == NETTO
    ticked = await ws(7, type="middagsro/chains/line", plan_id="p", line_id="egg", bought=True)
    assert ticked["result"]["shopping"][-1]["bought"]
    added = await ws(
        8,
        type="middagsro/chains/add",
        plan_id="p",
        offer={"dealer_id": NETTO, "heading": "Kaffe", "price": 39},
    )
    assert added["result"]["shopping"][-1]["name"] == "Kaffe"
    cleared = await ws(9, type="middagsro/chains/clear", plan_id="p", dealer_id=NETTO)
    assert "egg" not in {line["id"] for line in cleared["result"]["shopping"]}


def test_unit_prices_and_words() -> None:
    """Prices per kg, litre or piece, and search words inside longer words."""
    assert ch.product_unit_price({"underline": "500 GR.", "price": 35}) == {
        "unit": "kg",
        "price": 70.0,
    }
    assert ch.product_unit_price({"underline": "1 LTR.", "price": 10}) == {
        "unit": "l",
        "price": 10.0,
    }
    assert ch.product_unit_price({"underline": "10 STK.", "price": 30}) == {
        "unit": "stk",
        "price": 3.0,
    }
    assert ch.product_unit_price({"underline": "BUNDT", "price": 10}) is None
    assert ch.product_unit_price({"underline": "1 PK", "price": 10}) is None
    eggs = ch.offer_dict(OFFERS[1], NETTO)
    assert ch.offer_unit_price(eggs) == {"unit": "stk", "price": 2.0}
    assert ch.offer_unit_price({**eggs, "price": None}) is None
    assert ch.offer_unit_price(ch.offer_dict(OFFERS[3], NETTO)) is None  # "Pr. bundt"
    assert ch.query_words("Let mælk") == ["let", "mælk"]
    assert ch.text_has(["mælk"], "Arla Letmælk 1 l")
    assert not ch.text_has(["mælk"], "Smør")
    assert not ch.text_has([], "Smør")


async def test_search_everywhere(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """REMA's products and the chains' offers for a search, the cheapest marked."""
    planner = init_integration.runtime_data.planner
    fake = FakeTjek()
    with patch.object(planner.chains, "_get", new=fake):
        found = await ch.async_search_everywhere(planner, "frilandsæg")
        assert [p["name"] for p in found["products"]] == ["FRILANDSÆG"]
        assert found["products"][0]["unit_price"] == {"unit": "stk", "price": 3.2}
        assert [o["id"] for o in found["offers"]] == ["o2"]
        assert found["best"] == {
            "source": "chain",
            "id": "o2",
            "unit_price": {"unit": "stk", "price": 2.0},
        }
        assert (await ch.async_search_everywhere(planner, " "))["best"] is None
        persille = await ch.async_search_everywhere(planner, "persille")
        assert persille["best"] is None  # no sizes to compare
        assert [o["id"] for o in persille["offers"]] == ["o4"]
        fake.fail.add("/v2/catalogs")
        planner.chains._offers.clear()
        assert (await ch.async_search_everywhere(planner, "frilandsæg"))["offers"] == []
    # REMA's own avis can be read too.
    with patch.object(planner.chains, "_get", new=FakeTjek()):
        assert len(await planner.chains.async_offers(ch.REMA_ID)) == 4


async def test_search_everywhere_finds_the_kind_asked_for(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Near misses from REMA's search are left out, and only the very kind can be cheapest."""
    planner = init_integration.runtime_data.planner
    beef = make_product(1, "HK. OKSEKØD 8-12%", 20.0, underline="500 GR. / REMA 1000")
    lean = make_product(2, "HK. OKSEKØD 4-7%", 5.0, underline="500 GR. / REMA 1000")
    green = make_product(3, "HK. OKSEKØD, 35% GRØNT", 6.0, underline="500 GR. / REMA 1000")
    pork = make_product(4, "HK. GRISEKØD 8-12%", 10.0, underline="500 GR. / REMA 1000")
    mock_client.async_search_products = AsyncMock(return_value=[pork, green, lean, beef])
    with patch.object(planner.chains, "_get", new=FakeTjek()):
        found = await ch.async_search_everywhere(planner, "HK. OKSEKØD 8-12%")
    assert [p["id"] for p in found["products"]] == [1, 3, 2]
    assert found["best"] == {"source": "rema", "id": 1, "unit_price": {"unit": "kg", "price": 40.0}}
    # Nothing fits every word: REMA's results are all shown.
    mock_client.async_search_products = AsyncMock(return_value=[pork])
    with patch.object(planner.chains, "_get", new=FakeTjek()):
        found = await ch.async_search_everywhere(planner, "kalvekød")
    assert [p["id"] for p in found["products"]] == [4]
    assert found["best"] is None
    assert ch.query_fit("dansk", "Dansk smør") == (True, True)
    assert ch.query_fit("", "Smør") == (False, False)


async def test_rema_offers_on_the_list(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An offer from REMA's avis goes on the plan's list as REMA's product, or as text."""
    planner = init_integration.runtime_data.planner
    offer = ch.offer_dict(OFFERS[0], ch.REMA_ID)
    product = make_product(30001, "HK. OKSEKØD 8-12%", 35.0, underline="500 GR. / DANSK")
    mock_client.async_get_products.return_value = [product]
    mock_client.async_get_offer_products.side_effect = lambda offers: [
        replace(offers[0], product_ids=(30001,))
    ]
    result = await ch.async_add_rema_offer(planner, offer, "p")
    assert result == {"added_to": "plan", "name": "HK. OKSEKØD 8-12%"}
    with patch.object(planner, "_add_items") as add:
        assert (await ch.async_add_rema_offer(planner, offer, None))["added_to"] == "rema_list"
    assert add.call_args.args[0] == [{"product_id": 30001, "amount": 1}]
    # Not in REMA's webshop (a partivare): the avis's text.
    mock_client.async_get_offer_products.side_effect = lambda offers: offers
    result = await ch.async_add_rema_offer(planner, {**offer, "price": 25}, "p")
    plan = planner.store.get_plan("p")
    assert plan is not None
    assert (plan["shopping"][-1]["name"], plan["shopping"][-1]["cost"]) == (
        "Hakket oksekød 8-12%",
        25.0,
    )
    with patch.object(planner, "_add_items") as add:
        await ch.async_add_rema_offer(planner, offer, None)
    assert add.call_args.args[0] == [{"name": "Hakket oksekød 8-12%", "amount": 1}]
    with pytest.raises(ServiceValidationError):
        await ch.async_add_rema_offer(planner, {"heading": ""}, "p")


async def test_search_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """The panel's commands for the search and REMA's offers."""
    planner = init_integration.runtime_data.planner
    client = await hass_ws_client(hass)
    with patch.object(planner.chains, "_get", new=FakeTjek()):
        await client.send_json(
            {"id": 1, "type": "middagsro/search/everywhere", "query": "frilandsæg"}
        )
        msg = await client.receive_json()
        assert msg["result"]["best"]["id"] == "o2"
        await client.send_json(
            {"id": 2, "type": "middagsro/chains/offers", "dealer_id": ch.REMA_ID}
        )
        assert len((await client.receive_json())["result"]["offers"]) == 4
    offer = ch.offer_dict(OFFERS[2], ch.REMA_ID)
    await client.send_json(
        {"id": 3, "type": "middagsro/chains/rema_add", "offer": offer, "plan_id": "p"}
    )
    assert (await client.receive_json())["result"] == {"added_to": "plan", "name": "Spaghetti"}

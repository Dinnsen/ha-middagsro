"""The week's dinners from the avis: ready recipes priced with its offers (candidates.py)."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import candidates as cd, rema_catalog as rc
from custom_components.middagsro.api import Offer, RemaError
from custom_components.middagsro.recipes import clean_recipe
from homeassistant.core import HomeAssistant

from .conftest import CATALOGUE
from .test_rema_recipes import ENTITY, NOW

START = date(2026, 10, 19)


def offer(
    heading: str, price: float | None, quantity: str = "1 kg", description: str | None = None
) -> Offer:
    return Offer(
        id=heading,
        heading=heading,
        description=description,
        price=price,
        pre_price=None,
        quantity=quantity,
        valid_from=None,
        valid_to=None,
    )


def test_what_an_offer_is() -> None:
    """The kinds an offer stands in for; not what is made from them, nor flavours."""
    assert cd.heading_kinds("REMA 1000 Hakket dansk oksekød 15-18%") == {"hakket oksekød"}
    assert cd.heading_kinds("REMA 1000 Laksefileter, rødspættefileter eller mørksejfilet") >= {
        "laks",
        "mørksejfilet",
    }
    assert cd.heading_kinds("Peka Brunede kartofler") == set()
    assert cd.heading_kinds("Glyngøre Tun i vand, olie eller tomat") == set()
    assert cd.heading_kinds("Andebryst eller andelår") == set()  # not one to swap
    kinds = cd.offer_kinds(
        [
            offer("Kartofler", 12, "2 kg"),
            offer("Kartofler", 9),
            offer("Rød peber", None),
            offer("Coca-Cola, Fanta eller Tuborg Squash", 3, "33 cl", "33 cl. Ex. pant"),
            offer("Squash", 5, quantity="ca. et stykke"),  # no size to compare by
        ]
    )
    assert set(kinds) == {"kartofler"}
    best = cd.swap_price({"underline": "2 KG. / DANMARK"}, kinds["kartofler"])
    assert best is not None and (best[0].price, best[1]) == (12, 12.0)  # 6 kr. a kg, not 9
    assert cd.swap_price({"underline": "10 STK."}, kinds["kartofler"]) is None
    assert cd.swap_price({}, kinds["kartofler"]) is None
    assert cd.offer_size(offer("Æg", 18, "10 stk.")) == ("stk", 10)
    assert cd.is_dinner(["Aftensmad", "Frokost"]) and cd.is_dinner(["Kødfri"])
    assert not cd.is_dinner(["Frokost", "Kødfri"])


def test_price_a_recipe() -> None:
    """On offer by its own product, or by an offer of its kind when it may be swapped."""
    offers = cd.offer_kinds([offer("REMA 1000 Dansk kyllingebrystfilet tilsat lage", 30, "450 g")])
    prices = {1: (40.0, True), 2: (45.0, False), 3: (9.0, False)}
    ingredients = [
        {"name": "hakket oksekød", "product": {"id": 1}},
        {"name": "kyllingebryst", "product": {"id": 2, "underline": "600 GR. / DANSK"}},
        {"name": "spaghetti", "product": {"id": 3}},
        {"name": "salt"},
    ]
    price = cd.price_recipe(ingredients, prices, offers, ["salt"])
    assert price == {
        "cost": 89.0,  # 600 g at the offer's 30 kr. for 450 g
        "saving": 5.0,
        "on_offer": ["hakket oksekød", "kyllingebryst"],
        "swaps": [
            {
                "item": "kyllingebryst",
                "offer": "REMA 1000 Dansk kyllingebrystfilet tilsat lage",
                "price": 40.0,
            }
        ],
    }
    veggie = [{"name": "vegetariske kyllingebryst", "product": {"id": 2, "underline": "600 GR."}}]
    assert cd.price_recipe(veggie, prices, offers, [])["swaps"] == []  # no meat for it
    ingredients[1]["exact"] = True  # always that product: no swap
    assert cd.price_recipe(ingredients, prices, offers, ["salt"])["swaps"] == []
    # A product without a price takes the offer's, with nothing saved.
    unknown = cd.price_recipe(
        [{"name": "kyllingebryst", "product": {"id": 9, "underline": "450 GR."}}], {}, offers, []
    )
    assert (unknown["cost"], unknown["saving"]) == (30.0, 0.0)


def _own(name: str, *ingredients: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return clean_recipe({"name": name, "ingredients": list(ingredients), **extra})


async def test_the_weeks_dinners(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Ready recipes, the family's and REMA's, ranked; what the rules leave out is counted."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    await store.async_set_settings({**store.settings, "avoid": ["fish"]})
    beef = {"name": "hakket oksekød", "product": {"id": 30001}}  # on offer
    store.recipes = [
        _own("Spaghetti bolognese", beef, {"name": "spaghetti", "product": {"id": 60002}},
             {"name": "salt"}, servings=8),
        _own("Kyllingegryde",
             {"name": "kyllingebryst", "product": {"id": 30002, "underline": "600 GR. / DANSK"}}),
        _own("Laks i ovn", {"name": "laksefilet", "product": {"id": 99}}),
        _own("Pasta med smør", {"name": "spaghetti", "product": {"id": 60002}},
             rema_slug="dobbelt"),
        _own("Suppe", {"name": "porrer"}),
        _own("Lasagne", beef),
        _own("Rødbedesuppe med feta", {"name": "rødbeder"}, rating="dislike"),
    ]  # fmt: skip
    store.recent_dishes = lambda *_: ["Lasagne"]  # type: ignore[method-assign]
    entry = rc.entry_from(ENTITY, 0, NOW)
    disliked = rc.entry_from(
        {**ENTITY, "fields": {**ENTITY["fields"], "slug": "x", "title": "Rødbedesuppe med feta"}},
        1,
        NOW,
    )
    double = copy.deepcopy(entry)
    assert entry is not None and disliked is not None and double is not None
    double["slug"] = "dobbelt"
    unready = copy.deepcopy(entry)
    unready["slug"] = "y"
    unready["recipe"]["ingredients"].append({"name": "galangarod", "amount": "1 stk"})
    planner.rema_catalog.recipes = {e["slug"]: e for e in (entry, disliked, double, unready)}
    planner._async_offers = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            None,
            [
                offer("REMA 1000 Dansk kyllingebrystfilet tilsat lage", 34.95, "600 g"),
                offer("Karolines Køkken Piskefløde 36%", 10, "400 g"),
            ],
        )
    )
    mock_client.async_get_products = AsyncMock(
        side_effect=lambda ids, at=None: [p for p in CATALOGUE if p.id in ids]
    )
    result = await cd.async_candidates(planner, START)
    names = [c["name"] for c in result["candidates"]]
    assert names == ["Spaghetti bolognese", "Kyllingegryde", "Kylling i cremet svampesauce med ris"]
    first, chicken, rema = result["candidates"]
    assert (first["per_person"], first["on_offer"], first["source"]) == (
        6.12,
        ["hakket oksekød"],
        "collection",
    )
    assert chicken["swaps"][0]["item"] == "kyllingebryst" and chicken["saving"] == 10.05
    assert (rema["source"], rema["slug"], rema["cost"], rema["saving"]) == (
        "rema",
        "kylling-i-cremet-svampesauce-med-ris",
        45.0,
        2.0,
    )
    assert result["without_offers"] == 1  # Pasta med smør
    assert result["left_out"] == {"rules": 1, "recent": 1, "disliked": 1, "not_ready": 3}
    offers_first = await cd.async_candidates(planner, START, "offers")
    assert offers_first["candidates"][0]["name"] == "Kyllingegryde"

    # REMA not answering: the family's recipes are priced by the offers alone.
    mock_client.async_get_products = AsyncMock(side_effect=RemaError("nede"))
    result = await cd.async_candidates(planner, START)
    assert "Kyllingegryde" in [c["name"] for c in result["candidates"]]

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "middagsro/candidates", "sort": "offers"})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"]["candidates"]

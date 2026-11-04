"""A recipe's ingredients linked to the shop's products (linking.py)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import linking as lk
from custom_components.middagsro.api import RemaError
from custom_components.middagsro.recipes import clean_recipe
from homeassistant.core import HomeAssistant

PANTRY = "salt, peber, olie, smør"


def _recipe(*ingredients: dict[str, Any]) -> dict[str, Any]:
    return {"name": "Ret", "ingredients": list(ingredients)}


def test_kinds_and_what_is_bought() -> None:
    """An ingredient's kind; salt, oil, water, headings and what the family always
    has aren't bought."""
    assert lk.kind_of("2 fed hvidløg, pressede") == "hvidløg"
    assert lk.kind_of("Vand") is None
    assert lk.kind_of("Til sovsen:") is None
    pantry = ["salt", "olie"]
    assert lk.is_bought({"name": "hakket oksekød"}, pantry)
    assert not lk.is_bought({"name": "olivenolie"}, pantry)
    assert not lk.is_bought({"name": "Salt"}, pantry)
    assert not lk.is_bought({"name": "galangarod", "basic": True}, pantry)
    assert not lk.is_bought({"name": " "}, pantry)


def test_status() -> None:
    """Ready when every item that is bought has a product."""
    recipe = _recipe(
        {"name": "spaghetti", "product": {"id": 60002}},
        {"name": "hakket oksekød"},
        {"name": "salt"},
        {"name": "galangarod", "basic": True},
    )
    status = lk.links(recipe, PANTRY)
    assert (status["ready"], status["missing"]) == (False, 1)
    assert [r["bought"] for r in status["ingredients"]] == [True, True, False, False]
    row = status["ingredients"][1]
    assert (bool(row["kind"]), row["bought"], row["linked"]) == (True, True, False)
    recipe["ingredients"][1]["product"] = {"id": 30001}
    assert lk.links(recipe, PANTRY)["ready"] is True
    assert lk.links(_recipe(), PANTRY)["ready"] is False


def test_exact_is_kept() -> None:
    recipe = clean_recipe(_recipe({"name": "fettuccine spinat", "exact": 1, "product": {"id": 9}}))
    assert recipe["ingredients"][0]["exact"] is True
    assert "exact" not in clean_recipe(_recipe({"name": "pasta"}))["ingredients"][0]


async def test_suggestions(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Products for what has none: the matcher's pick and how sure it is."""
    planner = init_integration.runtime_data.planner
    recipe = _recipe(
        {"name": "hakket oksekød", "amount": "500 g"},
        {"name": "spaghetti", "product": {"id": 60002}},
        {"name": "salt"},
        {"name": "galangarod"},
        {"name": ""},
    )
    result = await lk.async_suggest(planner, recipe)
    assert result["available"] is True
    assert result["missing"] == 2
    by_index = {s["index"]: s for s in result["suggestions"]}
    assert set(by_index) == {0, 3}
    assert by_index[0]["product"]["id"] == 30001
    assert by_index[0]["confidence"] in ("high", "medium")
    assert by_index[3]["product"] is None
    assert planner._search_cache is None  # only while suggesting

    # REMA not answering: no suggestion for that item.
    mock_client.async_search_products = AsyncMock(side_effect=RemaError("nede"))
    planner._async_match = AsyncMock(side_effect=RemaError("nede"))  # type: ignore[method-assign]
    assert (await lk.async_suggest(planner, recipe))["suggestions"] == []
    # A shop without products: nothing to suggest.
    shop = planner.client
    planner.client = MagicMock(has_prices=False)
    result = await lk.async_suggest(planner, recipe)
    assert (result["available"], result["suggestions"]) == (False, [])
    planner.client = shop


async def test_websocket_and_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The panel's check, with and without suggestions, and the collection's badges."""
    store = init_integration.runtime_data.store
    client = await hass_ws_client(hass)
    rows = [{"name": "hakket oksekød", "amount": "500 g"}, {"name": ""}, "ikke en række"]
    await client.send_json(
        {"id": 1, "type": "middagsro/recipes/links", "recipe": {"ingredients": rows}}
    )
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"]["missing"] == 1
    assert len(msg["result"]["ingredients"]) == 3  # row for row
    await client.send_json(
        {
            "id": 2,
            "type": "middagsro/recipes/links",
            "recipe": {"ingredients": rows},
            "suggest": True,
        }
    )
    msg = await client.receive_json()
    assert msg["result"]["suggestions"][0]["product"]["id"] == 30001

    store.recipes = [
        clean_recipe(
            _recipe({"name": "hakket oksekød", "product": {"id": 30001}}, {"name": "salt"})
        ),
        clean_recipe({"name": "Suppe", "ingredients": [{"name": "porrer"}, {"name": "kartofler"}]}),
    ]
    await client.send_json({"id": 3, "type": "middagsro/state"})
    recipes = (await client.receive_json())["result"]["recipes"]
    assert [(r["ready"], r["missing"]) for r in recipes] == [(True, 0), (False, 2)]

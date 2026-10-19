"""Tests for REMA 1000's own recipes: cards, the collection and the plan."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import planedit as pe, recipes as rc, rema_recipes as rr
from custom_components.middagsro.api import RemaApiError
from custom_components.middagsro.storage import clean_settings
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import make_plan

NOW = datetime(2026, 10, 19, 18, 0, tzinfo=UTC)


def product(item_id: int, name: str, price: float, *, offer: bool = False) -> dict[str, Any]:
    """A REMA product as the recipe API has it: on offer this week, normal price later."""
    prices = [
        {"price": price, "is_advertised": offer, "starting_at": "2026-10-18T00:00:00+00:00",
         "ending_at": "2026-10-24T00:00:00+00:00"},
        {"price": price + 3, "is_advertised": False, "starting_at": "2026-10-25T00:00:00+00:00",
         "ending_at": "2099-12-31T00:00:00+00:00"},
        "ikke en pris",
    ]  # fmt: skip
    return {"id": item_id, "name": name, "underline": "400 GR. / REMA 1000", "prices": prices}


def ingredient(name: str, amount: Any, unit: str | None, active: dict[str, Any] | None,
               *, basic: bool = False, excluded: bool = False) -> dict[str, Any]:  # fmt: skip
    """An ingredient linked to a REMA product."""
    digital = {
        "id": 1,
        "title": name.upper(),
        "is_basic_ingredient": basic,
        "active_product": active,
    }
    return {"ingredient": name, "amountOfContent": amount, "unitOfContent": unit,
            "digitalProduct": digital, "isExcludedFromShoppingList": excluded}  # fmt: skip


ENTITY: dict[str, Any] = {
    "id": "r1",
    "type": "recipe",
    "fields": {
        "title": "Kylling i cremet svampesauce med ris",
        "slug": "kylling-i-cremet-svampesauce-med-ris",
        "image": {"url": "https://images.ctfassets.net/x/kylling.jpg"},
        "tags": [{"id": "6mjo9YHow8fdXyG4LhmHoK", "fields": {"title": "Aftensmad"}}, "x"],
        "customForm": {
            "servings": {"type": "person", "amount": 4},
            "totalTime": 30,
            "ingredientGroups": [
                {
                    "name": "",
                    "ingredients": [
                        ingredient(
                            "kyllingeinderfilet",
                            300,
                            "g",
                            product(404, "KYLLINGEINDERFILET", 35, offer=True),
                        ),
                        ingredient("piskefløde", 2.5, "dl", product(505, "PISKEFLØDE 38%", 12)),
                        ingredient(
                            "olivenolie", None, None, product(606, "OLIVENOLIE", 40), basic=True
                        ),
                        ingredient("vand", 1, "l", None, excluded=True),
                        ingredient("", 1, "stk", None),
                        "ikke en ingrediens",
                    ],
                },
            ],
            "preparationGroups": [
                {"steps": [{"step": "Kog risene."}, {"step": "  "}, {"step": "Steg kyllingen."}]}
            ],
            "preparationTextBefore": "Denne opskrift indeholder udvalgte varer fra avis uge 42",
            "preparationTextAfter": "Server med frisk persille.",
        },
    },
}
VEGGIE: dict[str, Any] = {
    "fields": {
        "title": "Shakshuka",
        "slug": "shakshuka",
        "tags": [{"id": rr.VEGETARIAN_TAG, "fields": {"title": "Kødfri"}}],
        "customForm": {},
    }
}


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan to put a recipe on."""
    return {"plans": [make_plan("p", start="2026-10-18")], "settings": clean_settings({})}


def test_amounts_images_and_prices() -> None:
    """Danish amounts, smaller photos and today's price of a product."""
    assert rr.amount_text(250, "g") == "250 g"
    assert rr.amount_text(0.75, "stk") == "0,75 stk"
    assert rr.amount_text(2, None) == "2"
    assert rr.amount_text(None, "g") == rr.amount_text("x", "g") == rr.amount_text(0, "g") == ""
    assert rr.image_url({"url": "https://img/a.jpg"}, 480) == "https://img/a.jpg?w=480&fm=webp&q=80"
    assert rr.image_url({"url": "http://img/a.jpg"}) is None
    assert rr.image_url(None) is None
    assert rr.current_price(product(1, "X", 10, offer=True), NOW) == (10.0, True)
    later = datetime(2026, 11, 1, tzinfo=UTC)
    assert rr.current_price(product(1, "X", 10, offer=True), later) == (13.0, False)
    assert rr.current_price({"prices": [{"price": "?", "is_advertised": True}]}, NOW) == (
        None,
        True,
    )
    assert rr.current_price({}, NOW) == (None, False)


def test_card_and_recipe() -> None:
    """A recipe card, and the recipe in the collection's shape with REMA's products."""
    card = rr.summary(ENTITY, NOW)
    assert card == {
        "slug": "kylling-i-cremet-svampesauce-med-ris",
        "title": "Kylling i cremet svampesauce med ris",
        "image": "https://images.ctfassets.net/x/kylling.jpg?w=480&fm=webp&q=80",
        "servings": 4,
        "total_minutes": 30,
        "tags": ["Aftensmad"],
        "vegetarian": False,
        "ingredients": 4,
        "on_offer": 1,  # the oil is a basic item, the water isn't bought
        "cost": 47.0,
    }
    assert rr.summary({"fields": {"slug": "x"}}, NOW) is None
    veggie = rr.summary(VEGGIE, NOW)
    assert veggie is not None
    assert (veggie["vegetarian"], veggie["servings"], veggie["image"]) == (True, None, None)

    recipe = rr.to_recipe(ENTITY)
    assert recipe["id"] is None
    assert (recipe["source"], recipe["rema_slug"], recipe["servings"]) == (
        "rema",
        "kylling-i-cremet-svampesauce-med-ris",
        4,
    )
    assert recipe["image"].endswith("?w=800&fm=webp&q=80")
    assert recipe["ingredients"] == [
        {"name": "kyllingeinderfilet", "amount": "300 g",
         "product": {"id": 404, "name": "KYLLINGEINDERFILET", "underline": "400 GR. / REMA 1000"}},
        {"name": "piskefløde", "amount": "2,5 dl",
         "product": {"id": 505, "name": "PISKEFLØDE 38%", "underline": "400 GR. / REMA 1000"}},
        {"name": "olivenolie", "amount": "",
         "product": {"id": 606, "name": "OLIVENOLIE", "underline": "400 GR. / REMA 1000"}, "basic": True},
        {"name": "vand", "amount": "1 l"},
    ]  # fmt: skip
    assert [s["text"] for s in recipe["steps"]] == ["Kog risene.", "Steg kyllingen."]
    assert recipe["tip"] == "Server med frisk persille."  # last week's avis is left out
    assert rr.to_recipe(VEGGIE)["type"] == "vegetar"
    assert rc.ingredient_texts(recipe)[2] == (
        "olivenolie (REMA-vare: OLIVENOLIE 400 GR. / REMA 1000) (basisvare)"
    )


async def test_list_and_get(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Pages of recipe cards are read once a while; one recipe by its slug."""
    planner = init_integration.runtime_data.planner
    page = {
        "data": [ENTITY, VEGGIE, "x"],
        "meta": {"pagination": {"current_page": 2, "last_page": 9, "total": 170}},
    }
    mock_client.async_get_recipes = AsyncMock(return_value=page)
    result = await planner.rema_recipes.async_list(rr.TAGS[1]["id"], "newest", 2)
    assert [r["slug"] for r in result["recipes"]] == [
        "kylling-i-cremet-svampesauce-med-ris",
        "shakshuka",
    ]
    assert (result["page"], result["last_page"], result["total"]) == (2, 9, 170)
    mock_client.async_get_recipes.assert_awaited_once_with(
        tag=rr.TAGS[1]["id"], page=2, per_page=rr.PER_PAGE, sort="-created_at"
    )
    await planner.rema_recipes.async_list(rr.TAGS[1]["id"], "newest", 2)
    assert mock_client.async_get_recipes.await_count == 1  # cached
    with pytest.raises(ServiceValidationError) as err:
        await planner.rema_recipes.async_list("ukendt")
    assert err.value.translation_key == "rema_recipes_failed"
    mock_client.async_get_recipes = AsyncMock(side_effect=RemaApiError("HTTP 500", 500))
    with pytest.raises(ServiceValidationError):
        await planner.rema_recipes.async_list()
    # Many pages: the cache starts over.
    mock_client.async_get_recipes = AsyncMock(return_value={})
    for number in range(1, 64):
        assert (await planner.rema_recipes.async_list(None, "popular", number))["recipes"] == []

    mock_client.async_get_recipe = AsyncMock(return_value=ENTITY)
    recipe = await planner.rema_recipes.async_get("kylling-i-cremet-svampesauce-med-ris")
    assert recipe["name"] == "Kylling i cremet svampesauce med ris"
    mock_client.async_get_recipe = AsyncMock(return_value=None)
    for slug in ("findes-ikke", " "):
        with pytest.raises(ServiceValidationError) as err:
            await planner.rema_recipes.async_get(slug)
        assert err.value.translation_key == "recipe_not_found"
    mock_client.async_get_recipe = AsyncMock(side_effect=RemaApiError("HTTP 500", 500))
    with pytest.raises(ServiceValidationError):
        await planner.rema_recipes.async_get("x")


async def test_collection_keeps_rema_links(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A REMA recipe keeps its products and photo, and saving it again updates the same one."""
    store = init_integration.runtime_data.store
    saved = await rc.async_save_recipe(store, {**rr.to_recipe(ENTITY), "rating": "like"})
    assert saved["ingredients"][0]["product"]["id"] == 404
    assert saved["image"].startswith("https://")
    again = await rc.async_save_recipe(store, rr.to_recipe(ENTITY))
    assert again["id"] == saved["id"]
    assert again["rating"] == "like"  # its rating stays
    assert len([r for r in store.recipes if r.get("rema_slug")]) == 1
    odd = rc.clean_recipe(
        {
            "name": "X",
            "image": "http://usikker",
            "ingredients": [{"name": "salt", "product": {"id": "1"}}],
        }
    )
    assert "image" not in odd
    assert odd["ingredients"] == [{"name": "salt", "amount": ""}]


def test_swap_prompt_names_rema_products() -> None:
    """The AI is told to search for the very product a REMA recipe is made for."""
    plan = make_plan("p", start="2026-10-18")
    kwargs: dict[str, Any] = {
        "settings": clean_settings({}),
        "plan": plan,
        "day": plan["days"][0],
        "dish": "Kylling",
        "offer_lines": [],
        "known_uses": True,
    }
    with_products = pe.build_swap_items_prompt(
        **kwargs, ingredients=rc.ingredient_texts(rr.to_recipe(ENTITY))
    )
    assert "brug den vares navn som søgeord" in with_products
    plain = pe.build_swap_items_prompt(**kwargs, ingredients=["600 g laks"])
    assert "brug den vares navn som søgeord" not in plain


async def test_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """The panel's commands: cards, one recipe, and a recipe on the plan."""
    client = await hass_ws_client(hass)
    mock_client.async_get_recipes = AsyncMock(return_value={"data": [ENTITY]})
    await client.send_json({"id": 1, "type": "middagsro/rema_recipes/list"})
    msg = await client.receive_json()
    assert msg["result"]["recipes"][0]["on_offer"] == 1
    assert msg["result"]["tags"][0]["title"] == "Avisopskrifter"

    mock_client.async_get_recipe = AsyncMock(return_value=ENTITY)
    await client.send_json({"id": 2, "type": "middagsro/rema_recipes/get", "slug": "kylling"})
    assert (await client.receive_json())["result"][
        "rema_slug"
    ] == "kylling-i-cremet-svampesauce-med-ris"

    with patch(
        "custom_components.middagsro.websocket.async_swap_dish", return_value={"id": "p"}
    ) as swap:
        await client.send_json(
            {
                "id": 3,
                "type": "middagsro/rema_recipes/plan",
                "slug": "kylling",
                "plan_id": "p",
                "date": "2026-10-19",
            }
        )
        msg = await client.receive_json()
    assert msg["result"] == {"id": "p"}
    option = swap.call_args.args[3]
    store = init_integration.runtime_data.store
    assert option["recipe_id"] == store.recipes[0]["id"]
    assert store.recipes[0]["rema_slug"] == "kylling-i-cremet-svampesauce-med-ris"

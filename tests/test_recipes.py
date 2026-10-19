"""Tests for the recipe collection: ratings, links, the plan and Overrask os."""

from __future__ import annotations

from datetime import date
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import mealplan as mp, planedit as pe, recipes as rc
from custom_components.middagsro.storage import clean_settings
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import make_plan
from .test_planedit import RECIPE, FakeAI

PAGE = """<html><head>
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
  {"@type": "WebPage", "name": "Side"},
  {"@type": ["Recipe"], "name": "Kylling i karry &amp; ris",
   "recipeYield": ["4 personer", "4"], "totalTime": "PT1H5M", "prepTime": "PT20M",
   "recipeCategory": "Aftensmad", "description": "<p>Mild og god</p>",
   "recipeIngredient": ["600 g kyllingebryst", "2 spsk karry", "1 ½ dl fløde", "salt", ""],
   "recipeInstructions": [
     {"@type": "HowToSection", "itemListElement": [{"@type": "HowToStep", "text": "Skær kyllingen."}]},
     {"@type": "HowToStep", "name": "Steg den."}, "Server med ris.", 5]}
]}</script>
<script type="application/ld+json">{ikke json</script>
</head><body>Kylling</body></html>"""


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan and a small collection."""
    plan = make_plan("p", start="2026-10-18")
    sunday, monday, tuesday = plan["days"]
    sunday["uses"] = ["Hakket oksekød", "Spaghetti"]
    monday["uses"] = []
    tuesday["uses"] = ["Persille"]
    return {
        "plans": [plan],
        "recipes": [
            rc.clean_recipe(
                {"name": "Laks med spinat", "rating": "like", "favorite": True,
                 "ingredients": ["600 g laksefilet", "250 g spinat"], "steps": ["Bag laksen."]}
            ) | {"id": "laks"},
            rc.clean_recipe({"name": "Fiskefrikadeller", "rating": "dislike"}) | {"id": "fisk"},
            rc.clean_recipe({"name": "Boller i karry", "rating": "like"}) | {"id": "boller"},
            {"no": "id"},
        ],
    }  # fmt: skip


def test_ingredients_and_recipes() -> None:
    """Amounts are split from the names; a recipe is cleaned."""
    assert rc.split_ingredient("2 dl fløde") == {"amount": "2 dl", "name": "fløde"}
    assert rc.split_ingredient("ca. 1-2 spsk  olie") == {"amount": "ca. 1-2 spsk", "name": "olie"}
    assert rc.split_ingredient("½ citron") == {"amount": "½", "name": "citron"}
    assert rc.split_ingredient("salt og peber") == {"amount": "", "name": "salt og peber"}
    recipe = rc.clean_recipe(
        {
            "name": " Pasta ",
            "type": "Vegetar",
            "servings": "x",
            "total_minutes": "25",
            "favorite": True,
            "rating": "dislike",
            "ingredients": [{"name": "pasta", "amount": "500 g"}, {"name": ""}, 5, "1 løg"],
            "steps": [{"text": "Kog.", "minutes": "8"}, {"text": ""}, "Server.", 3],
        }
    )
    assert recipe["name"] == "Pasta"
    assert (recipe["type"], recipe["servings"], recipe["total_minutes"]) == ("vegetar", 4, 25)
    assert (recipe["rating"], recipe["favorite"]) == ("like", True)  # a favourite is liked
    assert recipe["ingredients"] == [
        {"name": "pasta", "amount": "500 g"},
        {"name": "løg", "amount": "1"},
    ]
    assert recipe["steps"] == [{"text": "Kog.", "minutes": 8}, {"text": "Server.", "minutes": 0}]
    assert rc.clean_recipe({"rating": "meh"}, recipe)["rating"] == "like"
    with pytest.raises(ServiceValidationError):
        rc.clean_recipe({"name": " "})


def test_ratings() -> None:
    """Pressing again takes it back; the other one replaces it."""
    recipe: dict[str, Any] = {"rating": None, "favorite": False}
    rc.apply_rating(recipe, "favorite")
    assert (recipe["rating"], recipe["favorite"]) == ("like", True)
    rc.apply_rating(recipe, "favorite")
    assert (recipe["rating"], recipe["favorite"]) == ("like", False)
    rc.apply_rating(recipe, "favorite")
    rc.apply_rating(recipe, "dislike")
    assert (recipe["rating"], recipe["favorite"]) == ("dislike", False)
    rc.apply_rating(recipe, "dislike")
    assert recipe["rating"] is None
    rc.apply_rating(recipe, "like")
    assert recipe["rating"] == "like"
    recipe["favorite"] = True
    rc.apply_rating(recipe, "like")
    assert (recipe["rating"], recipe["favorite"]) == (None, False)
    with pytest.raises(ServiceValidationError):
        rc.apply_rating(recipe, "love")


def test_recipe_pages() -> None:
    """schema.org recipe data, and the page's text for the AI."""
    found = rc.parse_recipe_page(PAGE)
    assert found is not None
    assert found["name"] == "Kylling i karry & ris"
    assert (found["servings"], found["total_minutes"], found["active_minutes"]) == (4, 65, 20)
    assert found["ingredients"][:3] == ["600 g kyllingebryst", "2 spsk karry", "1 ½ dl fløde"]
    assert found["steps"] == ["Skær kyllingen.", "Steg den.", "Server med ris."]
    assert found["tip"] == "Mild og god"
    assert rc.parse_recipe_page("<html>ingen opskrift</html>") is None
    veggie = PAGE.replace('"recipeCategory": "Aftensmad"', '"suitableForDiet": "VegetarianDiet"')
    assert rc.parse_recipe_page(veggie)["type"] == "vegetar"  # type: ignore[index]
    text_steps = PAGE.replace(
        '"recipeInstructions": [', '"recipeInstructions": "Skær.\\nSteg.", "x": ['
    )
    assert rc.parse_recipe_page(text_steps)["steps"] == ["Skær.", "Steg."]  # type: ignore[index]
    assert rc._servings(None) == 4
    assert rc._iso_minutes("P1DT2H") == 1560
    assert rc._iso_minutes("ca. en time") == 0
    assert rc.page_text("<style>x</style><p>Hej &amp; velkommen</p>") == "Hej & velkommen"
    assert "SIDENS TEKST" in rc.build_extract_prompt("tekst")


async def test_collection(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Save, find, rate and delete; the AI's lists of liked and disliked dishes."""
    store = init_integration.runtime_data.store
    assert [r["id"] for r in store.recipes] == ["laks", "fisk", "boller"]
    new = await rc.async_save_recipe(store, {"name": "Pizza", "ingredients": ["1 dej"]})
    assert store.recipes[0] is new
    assert rc.find_by_name(store, "  PIZZA ") is new
    changed = await rc.async_save_recipe(store, {"id": new["id"], "name": "Pizza bianca"})
    assert changed is new
    assert new["ingredients"] == [{"name": "dej", "amount": "1"}]  # kept
    with pytest.raises(ServiceValidationError):
        await rc.async_save_recipe(store, {"id": "nope", "name": "x"})
    assert (await rc.async_rate(store, new["id"], "favorite"))["favorite"]
    with pytest.raises(ServiceValidationError):
        await rc.async_rate(store, "nope", "like")
    assert [r["name"] for r in rc.prompt_recipes(store)] == [
        "Pizza bianca",
        "Laks med spinat",
        "Boller i karry",
    ]
    assert [r["name"] for r in rc.prompt_recipes(store, ["laks med spinat"])][1] == "Boller i karry"
    assert rc.disliked_names(store) == ["Fiskefrikadeller"]
    assert rc.ingredient_texts(store.recipes[1]) == ["600 g laksefilet", "250 g spinat"]
    await rc.async_delete_recipe(store, new["id"])
    with pytest.raises(ServiceValidationError):
        await rc.async_delete_recipe(store, new["id"])
    with patch.object(rc, "MAX_RECIPES", 3), pytest.raises(ServiceValidationError):
        await rc.async_save_recipe(store, {"name": "En for mange"})
    assert rc.find_recipe(store, None) is None


async def test_rating_the_plan(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A dinner in the plan goes in the collection with its recipe when it is rated."""
    planner = init_integration.runtime_data.planner
    store = planner.store
    # Monday is leftovers of sunday's spaghetti: the spaghetti is rated.
    recipe = await rc.async_rate_day(planner, "p", "2026-10-19", "like")
    assert recipe["name"] == "Spaghetti bolognese"
    assert recipe["ingredients"] == [{"name": "hakket oksekød", "amount": "500 g"}]
    assert (recipe["source"], recipe["times_planned"]) == ("plan", 1)
    plan = store.get_plan("p")
    assert plan is not None
    assert plan["days"][0]["recipe_id"] == recipe["id"]
    assert rc.day_rating(store, plan["days"][0]) == {
        "recipe_id": recipe["id"],
        "rating": "like",
        "favorite": False,
    }
    again = await rc.async_rate_day(planner, "p", "2026-10-18", "favorite")
    assert again is recipe
    assert recipe["favorite"]
    # A recipe saved by hand without ingredients gets the plan's.
    await rc.async_save_recipe(store, {"name": "Kyllingewok med broccoli"})
    wok = await rc.async_rate_day(planner, "p", "2026-10-20", "dislike")
    assert wok["ingredients"]
    assert rc.day_rating(store, {"dish": "Ukendt"})["rating"] is None
    with pytest.raises(ServiceValidationError):
        await rc.async_rate_day(planner, "p", "2026-01-01", "like")
    with pytest.raises(ServiceValidationError):
        await rc.async_rate_day(planner, "p", "2026-10-18", "love")
    with pytest.raises(ServiceValidationError):
        await rc.async_rate_day(planner, "nope", "2026-10-18", "like")
    plan["days"][2]["dish"] = "Noget nyt"
    plan["days"][2]["recipe_id"] = None
    with pytest.raises(ServiceValidationError):
        await rc.async_rate_day(planner, "p", "2026-10-20", "love")
    plan["days"][2]["dish"] = ""
    with pytest.raises(ServiceValidationError):
        await rc.async_rate_day(planner, "p", "2026-10-20", "like")


async def test_links(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    ai_task: str,
) -> None:
    """A recipe is read from a link (with the AI when the page has no recipe data)."""
    planner = init_integration.runtime_data.planner
    aioclient_mock.get("https://opskrift.dk/karry", text=PAGE)
    aioclient_mock.get("https://opskrift.dk/blog", text="<p>Bland 2 dl fløde med karry</p>")
    aioclient_mock.get("https://opskrift.dk/tom", text="<p>Intet</p>")
    aioclient_mock.get("https://opskrift.dk/væk", status=404)
    aioclient_mock.get("https://opskrift.dk/nede", exc=TimeoutError())

    async def public(hass: HomeAssistant, host: str) -> None:
        return None

    with patch.object(rc, "_check_public", new=public):
        recipe = await rc.async_import(planner, "https://opskrift.dk/karry")
        assert recipe["id"] is None
        assert (recipe["name"], recipe["source"]) == ("Kylling i karry & ris", "link")
        assert recipe["ingredients"][2] == {"amount": "1 ½ dl", "name": "fløde"}
        assert planner.store.recipes[0]["id"] == "laks"  # not saved

        ai = FakeAI()
        ai.answers["recipe"] = {"name": "Karrysauce", "ingredients": [{"name": "fløde"}]}
        with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
            assert (await rc.async_import(planner, "https://opskrift.dk/blog"))[
                "name"
            ] == "Karrysauce"
            assert "Bland 2 dl fløde" in ai.prompts["Middagsro opskrift fra link"][0]
            ai.answers["recipe"] = {"name": None}
            with pytest.raises(ServiceValidationError):
                await rc.async_import(planner, "https://opskrift.dk/tom")

        async def broken(hass: HomeAssistant, **kwargs: Any) -> Any:
            raise HomeAssistantError("busy")

        with (
            patch("homeassistant.components.ai_task.async_generate_data", new=broken),
            pytest.raises(ServiceValidationError),
        ):
            await rc.async_import(planner, "https://opskrift.dk/tom")
        for url in ("https://opskrift.dk/væk", "https://opskrift.dk/nede", "ftp://x/y", "nope"):
            with pytest.raises(ServiceValidationError):
                await rc.async_import(planner, url)
        hass.states.async_remove("ai_task.assistant")
        await planner.store.async_set_settings({})
        with pytest.raises(ServiceValidationError):
            await rc.async_import(planner, "https://opskrift.dk/tom")


async def test_only_pages_on_the_internet(hass: HomeAssistant) -> None:
    """Home Assistant itself and the home network can't be read through a link."""

    async def lookup(address: str) -> Any:
        async def getaddrinfo(host: str, port: Any, **kwargs: Any) -> list[Any]:
            if host == "fejl":
                raise OSError("no such host")
            return [(2, 1, 6, "", (address, 0))]

        return getaddrinfo

    with patch.object(hass.loop, "getaddrinfo", new=await lookup("93.184.216.34")):
        await rc._check_public(hass, "example.com")
    for address in ("127.0.0.1", "192.168.1.10", "10.0.0.2", "::1"):
        with (
            patch.object(hass.loop, "getaddrinfo", new=await lookup(address)),
            pytest.raises(ServiceValidationError),
        ):
            await rc._check_public(hass, "homeassistant.local")
    with (
        patch.object(hass.loop, "getaddrinfo", new=await lookup("1.1.1.1")),
        pytest.raises(ServiceValidationError),
    ):
        await rc._check_public(hass, "fejl")


async def test_plans_use_the_collection(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """Liked dishes are offered to the AI, disliked ones are avoided, and Overrask os."""
    planner = init_integration.runtime_data.planner
    prompt = mp.build_prompt(
        settings=clean_settings({"disliked_dishes": ["Leverpostej"]}),
        dates=[date(2026, 10, 25)],
        catalog=None,
        offers=[],
        favorites_due=[{"id": "f1", "text": "Lasagne"}],
        favorites_optional=[],
        recent_dishes=[],
        own=rc.prompt_recipes(planner.store),
        disliked=rc.disliked_names(planner.store),
    )
    assert "FAMILIENS OPSKRIFTSSAMLING" in prompt
    assert "laks | ❤️ Laks med spinat | 600 g laksefilet, 250 g spinat" in prompt
    assert "Leverpostej; Fiskefrikadeller" in prompt
    surprise = mp.build_prompt(
        settings=clean_settings({}),
        dates=[date(2026, 10, 25)],
        catalog=None,
        offers=[],
        favorites_due=[{"id": "f1", "text": "Lasagne"}],
        favorites_optional=[{"id": "f2", "text": "Pizza"}],
        recent_dishes=[],
        own=rc.prompt_recipes(planner.store),
        surprise=True,
    )
    assert "OVERRASK FAMILIEN" in surprise
    assert "OPSKRIFTSSAMLING" not in surprise
    assert "Lasagne" not in surprise

    answer = {
        "days": [
            {"date": "2026-10-25", "dish": "Laks med spinat", "recipe_id": "laks"},
            {"date": "2026-10-26", "dish": "Kyllingewok", "recipe_id": "findes-ikke"},
        ],
        "shopping": [],
    }
    prompts: list[str] = []

    async def fake(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        if kwargs["task_name"] == "REMA 1000 madplan":
            prompts.append(kwargs["instructions"])
            return SimpleNamespace(data=json.loads(json.dumps(answer)))
        return SimpleNamespace(data=RECIPE)

    await planner.store.async_set_settings({"days": 2})
    with patch("homeassistant.components.ai_task.async_generate_data", new=fake):
        plan = await planner.async_generate(date(2026, 10, 25))
        first, second = plan["days"]
        assert first["recipe_id"] == "laks"
        assert first["steps"] == [{"text": "Bag laksen.", "minutes": 0}]
        assert second["recipe_id"] is None
        assert second["steps"][0]["text"] == "Steg kyllingen."
        assert rc.find_recipe(planner.store, "laks")["times_planned"] == 1  # type: ignore[index]
        assert not plan["surprise"]

        planner.async_start_generation(date(2026, 10, 25), surprise=True)
        await planner._task
    assert "OVERRASK FAMILIEN" in prompts[-1]
    latest = planner.store.latest_plan
    assert latest is not None
    assert latest["surprise"]
    assert latest["days"][0]["recipe_id"] is None  # not offered when surprising


async def test_swap_and_plan_from_the_collection(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """Swap suggestions can be the family's recipes, and a recipe can be put on a day."""
    planner = init_integration.runtime_data.planner
    options = {
        "options": [
            {"dish": "Laks med spinat", "recipe_id": "laks"},
            {"dish": "Pizza", "recipe_id": "findes-ikke"},
        ]
    }
    ai = FakeAI(options=options, items={"add": [], "uses": []})
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        result = await pe.async_swap_options(planner, "p", "2026-10-20")
        assert [o["recipe_id"] for o in result["options"]] == ["laks", None]
        swap_prompt = ai.prompts["REMA 1000 andre retter"][0]
        assert "laks | ❤️ Laks med spinat" in swap_prompt
        assert "Fiskefrikadeller" in swap_prompt  # thumbs down: not suggested
        plan = await pe.async_swap_dish(planner, "p", "2026-10-20", result["options"][0])
        assert (
            "Familiens egen opskrift bruger: 600 g laksefilet" in ai.prompts["REMA 1000 ny ret"][0]
        )
        tuesday = plan["days"][2]
        assert (tuesday["recipe_id"], tuesday["steps"][0]["text"]) == ("laks", "Bag laksen.")
        assert rc.find_recipe(planner.store, "laks")["times_planned"] == 1  # type: ignore[index]
        plan = await pe.async_swap_dish(
            planner, "p", "2026-10-20", {"dish": "X", "recipe_id": "væk"}
        )
        assert plan["days"][2]["recipe_id"] is None
        # Deleting the dish forgets its recipe.
        plan["days"][2]["recipe_id"] = "laks"
        plan = await pe.async_clear_day(planner, "p", "2026-10-20")
        assert plan["days"][2]["recipe_id"] is None


async def test_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """The panel's commands for the collection."""
    client = await hass_ws_client(hass)

    async def ws(msg_id: int, **msg: Any) -> dict[str, Any]:
        await client.send_json({"id": msg_id, **msg})
        result: dict[str, Any] = await client.receive_json()
        return result

    state = (await ws(1, type="middagsro/state"))["result"]
    assert [r["id"] for r in state["recipes"]] == ["laks", "fisk", "boller"]
    assert "ingredients" not in state["recipes"][0]
    assert state["recipes"][0]["ingredient_names"] == ["laksefilet", "spinat"]
    got = await ws(2, type="middagsro/recipes/get", recipe_id="laks")
    assert got["result"]["steps"] == [{"text": "Bag laksen.", "minutes": 0}]
    assert not (await ws(3, type="middagsro/recipes/get", recipe_id="nope"))["success"]
    saved = await ws(4, type="middagsro/recipes/save", recipe={"name": "Tacos", "rating": "like"})
    tacos = saved["result"]["id"]
    assert saved["result"]["rating"] == "like"
    rated = await ws(5, type="middagsro/recipes/rate", recipe_id=tacos, action="dislike")
    assert rated["result"]["rating"] == "dislike"
    day = await ws(
        6, type="middagsro/recipes/rate_day", plan_id="p", date="2026-10-18", action="like"
    )
    assert day["result"]["name"] == "Spaghetti bolognese"
    assert (await ws(7, type="middagsro/recipes/delete", recipe_id=tacos))["success"]
    with patch.object(rc, "async_fetch_page", return_value=PAGE):
        imported = await ws(8, type="middagsro/recipes/import", url="https://opskrift.dk/karry")
    assert imported["result"]["name"] == "Kylling i karry & ris"

    ai = FakeAI(items={"add": [], "uses": []})
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        planned = await ws(
            9, type="middagsro/recipes/plan", recipe_id="laks", plan_id="p", date="2026-10-20"
        )
    assert planned["result"]["days"][2]["dish"] == "Laks med spinat"
    missing = await ws(
        10, type="middagsro/recipes/plan", recipe_id="x", plan_id="p", date="2026-10-20"
    )
    assert missing["error"]["code"] == "middagsro_error"

    planner = init_integration.runtime_data.planner
    with patch.object(planner, "async_start_generation") as start:
        assert (await ws(11, type="middagsro/generate", surprise=True))["success"]
    assert start.call_args.kwargs["surprise"] is True

"""Tests for Mealie: the family's recipes, saving recipes and Mealie's calendar."""

from __future__ import annotations

from datetime import date
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.rema1000 import mealie as ml, mealplan as mp, planedit as pe
from custom_components.rema1000.storage import clean_settings
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import make_plan
from .test_planedit import RECIPE, FakeAI

URL = "http://mealie.local:9000"
LAKS = {
    "id": "r-laks",
    "slug": "laks-med-spinat",
    "name": "Laks med spinat",
    "description": "Familiens favorit",
    "recipeServings": 4,
    "totalTime": "35 minutter",
    "prepTime": "PT20M",
    "recipeIngredient": [
        {"display": "600 g laksefilet"},
        {"originalText": "250 g spinat"},
        {"note": "1 citron"},
        {"food": {"name": "salt"}},
        {"food": None},
        "peber",
    ],
    "recipeInstructions": [{"text": "Bag laksen."}, {"text": " "}, "x"],
}


@pytest.fixture
def mealie(hass: HomeAssistant) -> MockConfigEntry:
    """Mealie set up in Home Assistant."""
    entry = MockConfigEntry(
        domain="mealie",
        data={"host": f"{URL}/", "api_token": "token", "verify_ssl": False},
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    return entry


def test_reading_recipes() -> None:
    """Mealie's recipes in the planner's shape."""
    assert ml._minutes("PT1H15M") == 75
    assert ml._minutes("1 time 15 minutter") == 75
    assert ml._minutes("35 min") == 35
    assert ml._minutes("40") == 40
    assert ml._minutes(None) == 0
    recipe = ml.clean_recipe(LAKS)
    assert recipe["ingredients"] == [
        "600 g laksefilet",
        "250 g spinat",
        "1 citron",
        "salt",
        "peber",
    ]
    assert recipe["steps"] == ["Bag laksen."]
    assert (recipe["total_minutes"], recipe["active_minutes"], recipe["servings"]) == (35, 20, 4)


async def test_without_mealie(hass: HomeAssistant) -> None:
    """Nothing to talk to."""
    link = ml.MealieLink(hass)
    assert not link.available
    assert link.url is None
    assert link.recipe_url("x") is None
    with pytest.raises(ml.MealieError):
        await link.async_summaries()


class FakeMealie:
    """Answers MealieLink._request like Mealie's API does."""

    def __init__(self, routes: dict[tuple[str, str], Any]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def __call__(self, method: str, path: str, **kwargs: Any) -> Any:
        self.calls.append((method, path, kwargs))
        key = (method, path)
        if path == "/api/recipes" and method == "GET":
            key = (method, f"{path}?{kwargs['params']['page']}")
        answer = self.routes.get(key, ml.MealieError(f"{method} {path} 404"))
        if isinstance(answer, Exception):
            raise answer
        return answer

    def bodies(self, method: str, path: str) -> list[Any]:
        return [k.get("json") for m, p, k in self.calls if (m, p) == (method, path)]


async def test_request(
    hass: HomeAssistant, mealie: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Mealie's API: a token, JSON back, errors as MealieError."""
    link = ml.MealieLink(hass)
    assert link.available
    assert link.url == URL
    aioclient_mock.get(f"{URL}/api/users/self", json={"groupSlug": "familien"})
    aioclient_mock.delete(f"{URL}/api/households/mealplans/1", status=204)
    aioclient_mock.get(f"{URL}/api/recipes/nope", status=404, text="not found")
    aioclient_mock.get(f"{URL}/api/recipes/down", exc=aiohttp.ClientError("down"))
    aioclient_mock.get(f"{URL}/api/recipes/slow", exc=TimeoutError())
    assert await link.async_group() == "familien"
    assert await link.async_group() == "familien"  # asked once
    assert link.recipe_url("x") == f"{URL}/g/familien/r/x"
    assert await link._request("DELETE", "/api/households/mealplans/1") is None
    for slug in ("nope", "down", "slow"):
        with pytest.raises(ml.MealieError):
            await link._request("GET", f"/api/recipes/{slug}")
    other = ml.MealieLink(hass)
    with patch.object(other, "_request", side_effect=ml.MealieError("x")):
        assert await other.async_group() == "home"


async def test_mealie_api(hass: HomeAssistant, mealie: MockConfigEntry) -> None:
    """Recipes, saving a recipe and the calendar."""
    link = ml.MealieLink(hass)
    fake = FakeMealie(
        {
            ("GET", "/api/recipes?1"): {
                "items": [{"slug": "laks-med-spinat", "name": "Laks"}, {"name": "x"}],
                "total_pages": 2,
            },
            ("GET", "/api/recipes?2"): {
                "items": [{"slug": "tomt", "name": "Tom"}],
                "total_pages": 2,
            },
            ("GET", "/api/recipes/laks-med-spinat"): LAKS,
            ("POST", "/api/recipes"): "kyllingewok",
            ("PATCH", "/api/recipes/kyllingewok"): {"id": "r-wok"},
            ("GET", "/api/users/self"): {"groupSlug": "familien"},
            ("DELETE", "/api/households/mealplans/7"): None,
            ("DELETE", "/api/households/mealplans/9"): None,
            ("POST", "/api/households/mealplans"): {"id": 11},
        }
    )
    with patch.object(link, "_request", new=fake):
        summaries = await link.async_summaries()
        assert [s["slug"] for s in summaries] == ["laks-med-spinat", "tomt"]
        assert await link.async_summaries() is summaries  # cached
        recipes = await link.async_prompt_recipes(["Tom"])
        assert [r["name"] for r in recipes] == ["Laks med spinat"]
        assert [r["slug"] for r in await link.async_prompt_recipes()] == ["laks-med-spinat"]
        with patch.object(ml, "PROMPT_RECIPES", 1):
            assert len(await link.async_prompt_recipes()) <= 1

        # Saving one of the plan's recipes.
        day = {
            "dish": "Kyllingewok",
            "servings": 4,
            "total_minutes": 25,
            "active_minutes": 20,
            "tip": "Brug wokpande.",
            "ingredients": [
                {"name": "kyllingebryst", "amount": "600 g"},
                {"name": "", "amount": ""},
            ],
            "steps": [{"text": "Steg kyllingen."}, {"text": ""}],
        }
        saved = await link.async_save_recipe(day)
        assert saved == {
            "slug": "kyllingewok",
            "id": "r-wok",
            "url": f"{URL}/g/familien/r/kyllingewok",
        }
        body = fake.bodies("PATCH", "/api/recipes/kyllingewok")[0]
        assert [i["note"] for i in body["recipeIngredient"]] == ["600 g kyllingebryst"]
        assert [s["text"] for s in body["recipeInstructions"]] == ["Steg kyllingen."]
        assert body["description"] == "Fra REMA 1000-madplanen i Home Assistant. Brug wokpande."
        assert body["totalTime"] == "25 minutter"
        with pytest.raises(ml.MealieError):
            await link.async_save_recipe({"dish": " "})
        fake.routes["POST", "/api/recipes"] = '""'
        with pytest.raises(ml.MealieError):
            await link.async_save_recipe({"dish": "Suppe"})

        # The calendar: old entries out, recipes by id, other dinners as notes.
        plan = {
            "days": [
                {"date": "2026-10-19", "dish": "Laks med spinat", "mealie": "laks-med-spinat",
                 "mealie_entry": 7},
                {"date": "2026-10-20", "dish": "Kyllingewok", "mealie": "tomt", "mealie_entry": 8},
                {"date": "2026-10-21", "dish": ""},
            ],
            "skipped_entries": [9, 10],
        }  # fmt: skip
        assert await link.async_sync_calendar(plan) == 2
    posted = fake.bodies("POST", "/api/households/mealplans")
    assert posted[0] == {"date": "2026-10-19", "entryType": "dinner", "recipeId": "r-laks"}
    assert posted[1] == {
        "date": "2026-10-20",
        "entryType": "dinner",
        "title": "Kyllingewok",
        "text": "Fra REMA 1000-madplanen",
    }  # its recipe can't be read: a note
    assert [d.get("mealie_entry") for d in plan["days"]] == [11, 11, None]
    assert "skipped_entries" not in plan
    assert plan["mealie_synced"] == date.today().isoformat()


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan whose dishes say which items they use."""
    plan = make_plan("p", start="2026-10-18")
    sunday, monday, tuesday = plan["days"]
    sunday["uses"] = ["Hakket oksekød", "Spaghetti"]
    monday["uses"] = []
    tuesday["uses"] = ["Persille"]
    return {"plans": [plan], "settings": {"mealie_recipes": True, "mealie_calendar": True}}


def _recipes() -> list[dict[str, Any]]:
    return [ml.clean_recipe(LAKS)]


async def test_plans_start_from_mealie(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mealie: MockConfigEntry,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """The AI is shown the family's recipes; a dish built on one gets its recipe."""
    planner = init_integration.runtime_data.planner
    prompt = mp.build_prompt(
        settings=clean_settings({}),
        dates=[date(2026, 10, 18)],
        catalog=None,
        offers=[],
        favorites_due=[],
        favorites_optional=[],
        recent_dishes=[],
        mealie=_recipes(),
    )
    assert "FAMILIENS OPSKRIFTER I MEALIE" in prompt
    assert "laks-med-spinat | Laks med spinat | 600 g laksefilet, 250 g spinat" in prompt

    answer = {
        "days": [
            {"date": "2026-10-25", "dish": "Laks med spinat", "mealie": "laks-med-spinat"},
            {"date": "2026-10-26", "dish": "Kyllingewok", "mealie": "findes-ikke"},
        ],
        "shopping": [],
    }
    prompts: list[str] = []

    async def fake(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        if kwargs["task_name"] == "REMA 1000 madplan":
            prompts.append(kwargs["instructions"])
            return SimpleNamespace(data=json.loads(json.dumps(answer)))
        return SimpleNamespace(data=RECIPE)

    await planner.store.async_set_settings(
        {"days": 2, "mealie_recipes": True, "mealie_calendar": True}
    )
    with (
        patch.object(planner.mealie, "async_prompt_recipes", return_value=_recipes()),
        patch.object(planner.mealie, "async_recipe", return_value=ml.clean_recipe(LAKS)),
        patch.object(planner.mealie, "async_sync_calendar", return_value=2) as sync,
        patch("homeassistant.components.ai_task.async_generate_data", new=fake),
    ):
        plan = await planner.async_generate(date(2026, 10, 25))
    assert "FAMILIENS OPSKRIFTER I MEALIE" in prompts[0]
    first, second = plan["days"]
    assert first["mealie"] == "laks-med-spinat"
    assert first["ingredients"][0] == {"name": "600 g laksefilet", "amount": ""}
    assert first["steps"] == [{"text": "Bag laksen.", "minutes": 0}]
    assert (first["total_minutes"], first["active_minutes"]) == (35, 20)
    assert second["mealie"] is None  # not one of theirs: the AI writes the recipe
    assert second["steps"] == [{"text": "Steg kyllingen.", "minutes": 10}]
    sync.assert_called_once()

    # Mealie down: the AI does it all, and the plan is still made.
    with (
        patch.object(planner.mealie, "async_prompt_recipes", side_effect=ml.MealieError("down")),
        patch.object(planner.mealie, "async_sync_calendar", side_effect=ml.MealieError("down")),
        patch("homeassistant.components.ai_task.async_generate_data", new=fake),
    ):
        plan = await planner.async_generate(date(2026, 10, 25))
    assert [d["mealie"] for d in plan["days"]] == [None, None]
    assert "FAMILIENS OPSKRIFTER I MEALIE" not in prompts[-1]

    # A recipe that can't be read, or is empty, is written by the AI instead.
    day = {"date": "2026-10-25", "dish": "Laks", "mealie": "laks-med-spinat"}
    with patch.object(planner.mealie, "async_recipe", side_effect=ml.MealieError("down")):
        assert not await planner._async_mealie_recipe(day)
    empty = {**_recipes()[0], "ingredients": [], "steps": []}
    with patch.object(planner.mealie, "async_recipe", return_value=empty):
        assert not await planner._async_mealie_recipe(day)


async def test_swap_with_mealie(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mealie: MockConfigEntry,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """Swap suggestions can be the family's recipes; the new dish's items follow its recipe."""
    planner = init_integration.runtime_data.planner
    options = {
        "options": [
            {"dish": "Laks med spinat", "mealie": "laks-med-spinat"},
            {"dish": "Pizza", "mealie": "findes-ikke"},
        ]
    }
    ai = FakeAI(options=options, items={"add": [], "uses": []})
    summaries = [{"slug": "laks-med-spinat", "name": "Laks med spinat"}, {"slug": "x"}]
    with (
        patch.object(planner.mealie, "async_summaries", return_value=summaries),
        patch.object(planner.mealie, "async_recipe", return_value=ml.clean_recipe(LAKS)),
        patch.object(planner.mealie, "async_sync_calendar", return_value=3) as sync,
        patch("homeassistant.components.ai_task.async_generate_data", new=ai),
    ):
        result = await pe.async_swap_options(planner, "p", "2026-10-20")
        assert [o["mealie"] for o in result["options"]] == ["laks-med-spinat", None]
        assert "laks-med-spinat | Laks med spinat" in ai.prompts["REMA 1000 andre retter"][0]
        plan = await pe.async_swap_dish(planner, "p", "2026-10-20", result["options"][0])
    tuesday = plan["days"][2]
    assert (tuesday["mealie"], tuesday["steps"][0]["text"]) == ("laks-med-spinat", "Bag laksen.")
    assert (
        "Familiens opskrift (fra Mealie) bruger: 600 g laksefilet"
        in ai.prompts["REMA 1000 ny ret"][0]
    )
    sync.assert_called()

    # Mealie down: suggestions without its recipes, and the AI's own recipe.
    with (
        patch.object(planner.mealie, "async_summaries", side_effect=ml.MealieError("down")),
        patch.object(planner.mealie, "async_recipe", side_effect=ml.MealieError("down")),
        patch.object(planner.mealie, "async_sync_calendar", return_value=3),
        patch("homeassistant.components.ai_task.async_generate_data", new=ai),
    ):
        result = await pe.async_swap_options(planner, "p", "2026-10-18")
        assert all(o["mealie"] is None for o in result["options"])
        plan = await pe.async_swap_dish(
            planner, "p", "2026-10-18", {"dish": "Laks", "mealie": "laks-med-spinat"}
        )

    # Skipping a day takes its dinner out of Mealie's calendar too.
    plan["days"][1]["mealie_entry"] = 5
    with patch.object(planner.mealie, "async_sync_calendar", return_value=1):
        plan = await pe.async_clear_day(planner, "p", "2026-10-19", skip=True)
    assert plan["skipped_entries"] == [5]


async def test_mealie_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mealie: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Saving a recipe, filling the calendar, and Mealie in the panel's state."""
    planner = init_integration.runtime_data.planner
    client = await hass_ws_client(hass)

    async def ws(msg_id: int, **msg: Any) -> dict[str, Any]:
        await client.send_json({"id": msg_id, **msg})
        result: dict[str, Any] = await client.receive_json()
        return result

    state = await ws(1, type="rema1000/state")
    assert state["result"]["mealie"] == {"available": True, "url": URL}
    saved = {
        "slug": "spaghetti-bolognese",
        "id": "r1",
        "url": f"{URL}/g/home/r/spaghetti-bolognese",
    }
    with (
        patch.object(planner.mealie, "async_save_recipe", return_value=saved),
        patch.object(planner.mealie, "async_sync_calendar", return_value=3) as sync,
    ):
        result = await ws(2, type="rema1000/mealie/save", plan_id="p", date="2026-10-19")
        assert result["result"] == saved
        assert planner.store.get_plan("p")["days"][0]["mealie"] == "spaghetti-bolognese"
        assert (await ws(3, type="rema1000/mealie/sync", plan_id="p"))["result"] == {"count": 3}
        assert sync.call_count == 2
    missing = await ws(4, type="rema1000/mealie/save", plan_id="p", date="2026-01-01")
    assert missing["error"]["code"] == "rema1000_error"
    missing = await ws(5, type="rema1000/mealie/sync", plan_id="x")
    assert missing["error"]["code"] == "rema1000_error"
    with patch.object(planner.mealie, "async_sync_calendar", side_effect=ml.MealieError("down")):
        failed = await ws(6, type="rema1000/mealie/sync", plan_id="p")
        assert failed["error"]["code"] == "rema1000_error"
    # Switched off: nothing is sent unless asked.
    await planner.store.async_set_settings({"mealie_calendar": False})
    assert await planner.async_mealie_sync(planner.store.get_plan("p")) == 0
    assert issubclass(ml.MealieError, HomeAssistantError)

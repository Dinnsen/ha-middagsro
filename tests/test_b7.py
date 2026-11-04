"""2.14.0b7: ready by the family's pantry, their own links on REMA's recipes,
kinds of days, and favourites and dislikes as recipes."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import dishes as ds, mealplan as mp, rema_catalog as rc
from custom_components.middagsro.recipes import clean_recipe, prompt_recipes
from custom_components.middagsro.storage import RemaPlanStore, clean_settings
from homeassistant.core import HomeAssistant

from .test_mealplan import SETTINGS, START, FakeAI, _generate, ai_answer
from .test_rema_recipes import ENTITY, NOW, ingredient

WEEK = [START.fromordinal(START.toordinal() + i) for i in range(7)]  # sunday 18/10 ...


def _entity_with(name: str, product: dict[str, Any] | None) -> dict[str, Any]:
    entity = copy.deepcopy(ENTITY)
    entity["fields"]["customForm"]["ingredientGroups"][0]["ingredients"].append(
        ingredient(name, 1, "spsk", product)
    )
    return entity


async def test_ready_by_the_pantry_and_own_links(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Risvineddike without a product is no missing item when eddike is in the
    pantry; a product the family links (Gem) is kept on REMA's recipe."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    catalog = planner.rema_catalog
    vinegar = rc.entry_from(_entity_with("risvineddike", None), 0, NOW)
    galanga = rc.entry_from({**_entity_with("galangarod", None), "id": "g"}, 1, NOW)
    assert vinegar is not None and galanga is not None
    galanga["slug"] = "thai"
    assert vinegar["ready"] is False  # REMA's own view
    catalog.recipes = {vinegar["slug"]: vinegar, "thai": galanga}
    catalog.swept = NOW.isoformat()
    assert catalog.is_ready(vinegar)  # eddike is in the pantry
    assert not catalog.is_ready(galanga)
    assert catalog.status()["ready"] == 1
    page = catalog.page(None, 1, None)
    assert page is not None
    assert [r["ready"] for r in page["recipes"]] == [True, False]

    client = await hass_ws_client(hass)
    rows = catalog.recipe("thai")["ingredients"]
    rows[-1]["product"] = {"id": 77, "name": "GALANGA", "underline": "1 STK."}
    await client.send_json(
        {"id": 1, "type": "middagsro/rema_recipes/save_links", "slug": "thai", "ingredients": rows}
    )
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"] == {"ready": True}
    assert catalog.recipe("thai")["ingredients"][-1]["product"]["id"] == 77
    again = rc.RemaRecipeCatalog(hass, init_integration.entry_id, mock_client)
    await again.async_load()
    assert again.links["thai"]["galangarod"]["product"]["id"] == 77
    await client.send_json(
        {"id": 2, "type": "middagsro/rema_recipes/save_links", "slug": "nope", "ingredients": []}
    )
    assert not (await client.receive_json())["success"]

    # Taken back to REMA's own: nothing of the family's is kept.
    await catalog.async_save_links("thai", galanga["recipe"]["ingredients"])
    assert "thai" not in catalog.links
    await catalog.async_save_links("findes-ikke", [])

    # Gem i samlingen: in the collection, and on REMA's recipe too.
    recipe = catalog.recipe("thai")
    recipe["rema_slug"] = "thai"
    recipe["ingredients"][-1].update(product={"id": 78, "name": "G", "underline": ""}, exact=True)
    await client.send_json({"id": 3, "type": "middagsro/recipes/save", "recipe": recipe})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert any(r.get("rema_slug") == "thai" for r in store.recipes)
    assert catalog.links["thai"]["galangarod"]["exact"] is True


def test_kinds_of_days() -> None:
    """A fixed day's kind (saved before kinds by its words), and a week's own choices."""
    assert ds.fixed_kind({"text": "Rester"}) == "rest"
    assert ds.fixed_kind({"text": "Rugbrødsdag (kun denne ene dag med rugbrød)"}) == "rye"
    assert ds.fixed_kind({"text": "Pizza"}) == "fixed"
    assert ds.fixed_kind({"kind": "veg", "text": "x"}) == "veg"
    settings = clean_settings(
        {
            "fixed_days": [
                {"weekday": 3, "text": "Rester"},
                {"weekday": 4, "kind": "fixed", "text": "Pizza"},
                {"weekday": 5, "kind": "fixed", "text": " "},  # a dish without a name
                {"weekday": 0, "kind": "veg", "text": "noget"},
                "ikke en dag",
            ]
        }
    )
    assert settings["fixed_days"] == [
        {"weekday": 3, "kind": "rest", "text": "Rester"},
        {"weekday": 4, "kind": "fixed", "text": "Pizza"},
        {"weekday": 0, "kind": "veg", "text": "Vegetardag"},
    ]
    kinds = ds.plan_day_kinds(
        settings,
        WEEK,
        {
            "2026-10-22": {"kind": "rye"},  # thursday: rye bread instead of leftovers
            "2026-10-23": {"kind": "fixed", "text": ""},  # no dish named: the AI chooses
            "2026-10-18": {"kind": "nonsense"},
        },
    )
    assert kinds["2026-10-22"] == {"kind": "rye", "text": "Rugbrødsdag"}
    assert kinds["2026-10-23"]["kind"] == "ai"
    assert kinds["2026-10-19"] == {"kind": "veg", "text": "Vegetardag"}  # monday from settings
    assert kinds["2026-10-18"]["kind"] == "ai"
    dated = {"fixed_days": [{"date": "2026-10-19", "weekday": 0, "kind": "veg", "text": ""}]}
    assert ds.veg_dates(dated, WEEK) == [date(2026, 10, 19)]
    assert ds.fixed_on(dated["fixed_days"][0], date(2026, 10, 26)) is False  # only that date
    plan = {"days": [{"date": "2026-10-19", "weekday": "mandag", "dish": "Bøf", "type": "normal"}]}
    problems = ds.check_plan(
        plan, {**clean_settings({}), **dated, "leftover_days": 0}, recent=[], due_ids=set()
    )
    assert any("vegetarret" in p for p in problems)
    prompt = mp.build_prompt(
        settings={**clean_settings({}), **dated},
        dates=WEEK,
        catalog=None,
        offers=[],
        favorites_due=[],
        favorites_optional=[],
        recent_dishes=[],
    )
    assert "mandag 2026-10-19: en vegetarret" in prompt


async def test_plan_with_rye_and_skip_days(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """A rye bread day is written on the plan with nothing bought; a skipped day is skipped."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    await store.async_set_settings({**store.settings, "recipe_planner": False, "fixed_days": []})
    days = {"2026-10-21": {"kind": "rye"}, "2026-10-24": {"kind": "skip"}}
    dates = [d for d in WEEK if d.isoformat() not in days]
    ai = FakeAI(ai_answer(dates, []))
    await _generate(planner, ai, day_kinds=days)
    plan = store.latest_plan
    assert plan is not None
    rye = next(d for d in plan["days"] if d["date"] == "2026-10-21")
    assert (rye["dish"], rye["type"]) == ("Rugbrødsdag", "egen")
    assert plan["skipped"] == ["2026-10-24"]
    assert plan["day_kinds"]["2026-10-21"]["kind"] == "rye"


async def test_favourites_and_dislikes_become_recipes(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Saved before they were recipes: favourites keep their id and how often,
    and the dishes they don't like are 👎 recipes."""
    hass_storage["middagsro.e.mealplans"] = {
        "version": 1,
        "minor_version": 1,
        "key": "middagsro.e.mealplans",
        "data": {
            "settings": {**SETTINGS, "disliked_dishes": ["Fiskefrikadeller"]},
            "favorites": [
                {"id": "fav1", "text": "Lasagne", "frequency": "weekly", "last_used": "2026-10-04"},
                {"id": "fav2", "text": "Tacos", "frequency": "nonsense", "last_used": None},
                "ikke en favorit",
            ],
            "recipes": [clean_recipe({"name": "Tacos", "ingredients": ["tortillas"]})],
        },
    }
    store = RemaPlanStore(hass, "e")
    await store.async_load()
    assert sorted((f["id"], f["text"], f["frequency"]) for f in store.favorites) == [
        ("fav1", "Lasagne", "weekly"),
        ("fav2", "Tacos", "inspiration"),
    ]
    tacos = next(r for r in store.recipes if r["name"] == "Tacos")
    assert tacos["favorite"] and tacos["ingredients"]  # the recipe they had
    fish = next(r for r in store.recipes if r["name"] == "Fiskefrikadeller")
    assert fish["rating"] == "dislike" and not fish["favorite"]
    assert store.settings["disliked_dishes"] == ["Fiskefrikadeller"]
    store.favorites = [{"id": "fav3", "text": "Pizza", "frequency": "monthly"}]
    assert ("fav3", "Pizza", "monthly") in [
        (f["id"], f["text"], f["frequency"]) for f in store.favorites
    ]
    assert "Tacos" in [r["name"] for r in prompt_recipes(store)]

    # A plan with a favourite marks when it was last used.
    plan = {
        "id": "p",
        "start_date": "2026-10-18",
        "days": [{"favorite_id": "fav2"}],
        "shopping": [],
    }
    await store.async_add_plan(plan)
    assert next(f for f in store.favorites if f["id"] == "fav2")["last_used"] == "2026-10-18"

    # Loaded again: nothing is added twice.
    again = RemaPlanStore(hass, "e")
    await store.async_save()
    await again.async_load()
    assert len(again.recipes) == len(store.recipes)
    await again.async_set_settings({**again.settings, "disliked_dishes": ["Leverpostej"]})
    assert "Leverpostej" in again.settings["disliked_dishes"]
    assert any(r["name"] == "Leverpostej" and r["rating"] == "dislike" for r in again.recipes)


def test_frequency_on_a_favourite_recipe() -> None:
    recipe = clean_recipe({"name": "Lasagne", "favorite": True, "frequency": "monthly"})
    assert recipe["frequency"] == "monthly"
    assert "frequency" not in clean_recipe({"name": "Lasagne", "frequency": "monthly"})
    kept = clean_recipe({"name": "Lasagne"}, {**recipe, "fav_id": "f1"})
    assert (kept["frequency"], kept["fav_id"]) == ("monthly", "f1")

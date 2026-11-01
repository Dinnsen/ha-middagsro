"""REMA's recipes kept in Home Assistant (rema_catalog.py)."""

from __future__ import annotations

import asyncio
import contextlib
import copy
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.middagsro import rema_catalog as rc, rema_recipes as rr
from custom_components.middagsro.api import RemaApiError
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .test_rema_recipes import ENTITY, NOW, VEGGIE, ingredient


def _entity(
    slug: str, title: str, *, tag: str = "6mjo9YHow8fdXyG4LhmHoK", linked: bool = True
) -> dict[str, Any]:
    entity = copy.deepcopy(ENTITY)
    entity["fields"].update(slug=slug, title=title)
    entity["fields"]["tags"] = [{"id": tag, "fields": {"title": "Aftensmad"}}]
    if not linked:
        entity["fields"]["customForm"]["ingredientGroups"][0]["ingredients"].append(
            ingredient("galangarod", 1, "stk", None)
        )
    return entity


def _pages(by_tag: dict[str, list[list[dict[str, Any]]]]) -> AsyncMock:
    async def recipes(*, tag: str, page: int, per_page: int, sort: str, **_: Any) -> dict[str, Any]:
        pages = by_tag.get(tag, [[]])
        return {"data": pages[page - 1], "meta": {"pagination": {"last_page": len(pages)}}}

    return AsyncMock(side_effect=recipes)


def test_what_is_kept_of_a_recipe() -> None:
    """A recipe is kept with its products and their prices, and is ready when every
    item that is bought has a product; its card is the one REMA's page gives."""
    entry = rc.entry_from(ENTITY, 3, NOW)
    assert entry is not None
    assert (entry["slug"], entry["rank"], entry["ready"], entry["servings"]) == (
        "kylling-i-cremet-svampesauce-med-ris", 3, True, 4,
    )  # fmt: skip
    assert set(entry["prices"]) == {"404", "505"}  # not the oil (basic) nor the water
    assert entry["recipe"]["ingredients"][0]["product"]["id"] == 404
    assert "id" not in entry["recipe"]
    assert rc.card(entry, NOW) == rr.summary(ENTITY, NOW)
    unlinked = rc.entry_from(_entity("x", "Thaisuppe", linked=False), 0, NOW)
    assert unlinked is not None
    assert unlinked["ready"] is False
    assert rr.summary(_entity("x", "Thaisuppe", linked=False), NOW)["ready"] is False
    assert rc.entry_from({"fields": {"slug": "y"}}, 0, NOW) is None
    assert rc.entry_from(VEGGIE, 0, NOW)["ready"] is False  # no ingredients at all


async def test_sweep_reads_every_dinner_once(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Every category is read page by page; a recipe in two is kept once; a recipe
    REMA took down is gone after the next read; what was read is saved."""
    planner = init_integration.runtime_data.planner
    catalog = planner.rema_catalog
    catalog.pause = 0
    assert catalog.due()
    assert catalog.page(None, 1, None) is None  # not read yet
    lasagne, chili, soup = (
        _entity("lasagne", "Lasagne"),
        _entity("chili", "Chili con carne"),
        _entity("suppe", "Thaisuppe", linked=False),
    )
    mock_client.async_get_recipes = _pages({
        rc.SWEEP_TAGS[0]: [[lasagne, "x"], [chili]],
        rc.SWEEP_TAGS[3]: [[soup, lasagne]],
    })  # fmt: skip
    await catalog.async_sweep()
    assert list(catalog.recipes) == ["lasagne", "chili", "suppe"]
    assert catalog.status() == {
        "count": 3, "ready": 2, "swept": catalog.swept, "running": False, "pages": 6,
    }  # fmt: skip
    assert not catalog.due()
    assert catalog.due(dt_util.utcnow() + timedelta(days=8))

    again = rc.RemaRecipeCatalog(hass, init_integration.entry_id, mock_client)
    await again.async_load()
    assert list(again.recipes) == ["lasagne", "chili", "suppe"]
    assert again.complete

    mock_client.async_get_recipes = _pages({rc.SWEEP_TAGS[0]: [[chili]]})
    await catalog.async_sweep()
    assert list(catalog.recipes) == ["chili"]

    # REMA can't be reached: what was read stays.
    mock_client.async_get_recipes = AsyncMock(side_effect=RemaApiError("HTTP 500", 500))
    swept = catalog.swept
    await catalog.async_sweep()
    assert (list(catalog.recipes), catalog.swept, catalog.running) == (["chili"], swept, False)
    # Nothing at all: nothing changes either.
    mock_client.async_get_recipes = _pages({})
    await catalog.async_sweep()
    assert list(catalog.recipes) == ["chili"]


async def test_pages_from_the_catalogue(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Once every recipe is read, REMA's page in the panel is answered here: by
    popularity, by category, by words in the title or the ingredients."""
    planner = init_integration.runtime_data.planner
    catalog = planner.rema_catalog
    catalog.pause = 0
    fish = _entity("laks", "Ovnbagt laks", tag="7yfezsL41ufC4kYdHXjN8d")
    mock_client.async_get_recipes = _pages({
        rc.SWEEP_TAGS[0]: [[_entity(f"ret-{i}", f"Ret {i}") for i in range(25)]],
        rc.SWEEP_TAGS[4]: [[fish]],
    })  # fmt: skip
    await catalog.async_sweep()
    mock_client.async_get_recipes.reset_mock()

    first = await planner.rema_recipes.async_list(None, "popular", 1)
    assert [r["slug"] for r in first["recipes"]][:2] == ["ret-0", "ret-1"]
    assert (first["page"], first["last_page"], first["total"]) == (1, 2, 26)
    assert first["catalog"]["count"] == 26
    assert first["recipes"][0]["ready"] is True
    second = await planner.rema_recipes.async_list(None, "popular", 2)
    assert [r["slug"] for r in second["recipes"]] == [*(f"ret-{i}" for i in range(20, 25)), "laks"]
    tagged = await planner.rema_recipes.async_list("7yfezsL41ufC4kYdHXjN8d", "popular", 1)
    assert [r["slug"] for r in tagged["recipes"]] == ["laks"]
    found = await planner.rema_recipes.async_list(None, "popular", 1, "laks")
    assert [r["slug"] for r in found["recipes"]] == ["laks"]
    found = await planner.rema_recipes.async_list(None, "popular", 1, "piskefløde ret")
    assert found["total"] == 25  # an ingredient and a word of the title
    assert not mock_client.async_get_recipes.called

    # The newest, and a category the catalogue doesn't read, are asked of REMA.
    mock_client.async_get_recipes = AsyncMock(return_value={})
    await planner.rema_recipes.async_list(None, "newest", 1)
    await planner.rema_recipes.async_list(rr.TAGS[10]["id"], "popular", 1)
    assert mock_client.async_get_recipes.await_count == 2

    # One recipe: from the catalogue, a copy (saving it doesn't change the catalogue).
    mock_client.async_get_recipe = AsyncMock(return_value=None)
    recipe = await planner.rema_recipes.async_get("laks")
    assert (recipe["name"], recipe["id"]) == ("Ovnbagt laks", None)
    recipe["name"] = "Min laks"
    assert catalog.recipe("laks")["name"] == "Ovnbagt laks"
    assert not mock_client.async_get_recipe.called
    assert catalog.recipe("findes-ikke") is None


async def test_read_now_and_then(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A while after start, and twice a day, the recipes are read when they are due;
    not for another shop; stopped on unload."""
    planner = init_integration.runtime_data.planner
    catalog = planner.rema_catalog
    catalog.async_stop()
    catalog.pause = 0
    mock_client.has_prices = True
    mock_client.async_get_recipes = _pages({rc.SWEEP_TAGS[0]: [[_entity("lasagne", "Lasagne")]]})
    catalog.async_start()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=rc.FIRST_CHECK + 1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert list(catalog.recipes) == ["lasagne"]
    calls = mock_client.async_get_recipes.await_count
    async_fire_time_changed(hass, dt_util.utcnow() + rc.CHECK_EVERY + timedelta(seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_client.async_get_recipes.await_count == calls  # not due yet
    catalog.async_stop()

    other = rc.RemaRecipeCatalog(hass, "other", MagicMock(has_prices=False))
    other.async_start()
    assert not other._unsubs

    # Unloaded in the middle of a read: the read stops.
    slow = rc.RemaRecipeCatalog(hass, "slow", mock_client)
    mock_client.async_get_recipes = _pages({rc.SWEEP_TAGS[0]: [[], []]})
    slow.async_start()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=rc.FIRST_CHECK + 1))
    await hass.async_block_till_done()
    task = slow._task
    assert task is not None
    for _ in range(5):
        await asyncio.sleep(0)
    assert slow.running  # waiting a minute before the next page
    slow.async_stop()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert not slow.running
    assert not slow._unsubs

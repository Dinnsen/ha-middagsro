"""Tests for 2.4.0: moving dishes, chosen dishes, day wishes, no-leftover days,
one item to the REMA list, better recipes and product matching."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import dishes, mealplan as mp, planedit as pe
from custom_components.middagsro.mealie import MealieError
from custom_components.middagsro.storage import clean_settings
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import make_plan, make_product

DATES = [
    "2026-10-18",
    "2026-10-19",
    "2026-10-20",
    "2026-10-21",
    "2026-10-22",
    "2026-10-23",
    "2026-10-24",
]


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan from sunday 18/10 (the clock says wednesday 14/10)."""
    plan = make_plan("p", start="2026-10-18")
    for i, line in enumerate(plan["shopping"]):
        line["id"] = f"l{i}"
    return {"plans": [plan]}


async def _ws(client: Any, msg_id: int, **msg: Any) -> dict[str, Any]:
    await client.send_json({"id": msg_id, **msg})
    result: dict[str, Any] = await client.receive_json()
    return result


# ------------------------------------------------------------------ matching


def test_head_word() -> None:
    """The thing a search is about is its last word before "med", "uden" ..."""
    assert mp.head_word("grønne bønner") == "bønner"
    assert mp.head_word("Laksefilet med skind") == "laksefilet"
    assert mp.head_word("hakket oksekød 8-12%") == "oksekød"
    assert mp.head_word("salt og peber") == "salt"
    assert mp.head_word("") is None


async def test_green_beans_are_not_grapes(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Only "grønne" fits: grapes are never beans, so the line becomes free text."""
    planner = init_integration.runtime_data.planner
    line = {"name": "Grønne bønner", "search": "grønne bønner", "amount": 400, "unit": "g"}
    grapes = make_product(1, "STENFRI GRØNNE DRUER", 25, underline="400 GR.", department="Frugt")
    beans = make_product(2, "BØNNER", 12, underline="400 GR.", department="Frugt")
    assert planner._candidates(line, [grapes], "grønne bønner")[0] == []
    found, _ = planner._candidates(line, [grapes, beans], "grønne bønner")
    assert [p.id for p in found] == [2]
    # A typed line needs every word.
    typed = {**line, "prefer": "relevance"}
    assert planner._candidates(typed, [beans], "grønne bønner")[0] == []


# ------------------------------------------------------------------ recipes


def test_recipe_problems() -> None:
    """Vague ingredients, too few steps and meatballs formed of fried mince."""
    good = {
        "ingredients": [{"name": "hakket kylling", "amount": "500 g"}],
        "steps": [{"text": "Form boller af farsen."}, {"text": "Brun kødbollerne."}],
    }
    assert mp.recipe_problems(good) == []
    assert mp.recipe_problems("tekst") == ["Svaret var ikke en opskrift."]
    bad = {
        "ingredients": [{"name": "Krydderier", "amount": "50 g"}, "x"],
        "steps": [
            "Tilsæt hakket kylling til panden og steg den gennem.",
            {"text": "Form små kødboller af blandingen."},
        ],
    }
    problems = mp.recipe_problems(bad)
    assert len(problems) == 2
    assert "Krydderier" in problems[0]
    assert "rå fars" in problems[1]
    assert mp.recipe_problems({"steps": ["Kog."]}) == [
        "Der er for få trin: skriv hele fremgangsmåden."
    ]


async def test_recipe_put_right(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """A recipe with faults is asked for once more; the better one is kept."""
    planner = init_integration.runtime_data.planner
    plan = init_integration.runtime_data.store.plans[0]
    day = plan["days"][2]
    vague = {
        "ingredients": [{"name": "krydderier", "amount": "2 tsk"}],
        "steps": ["Steg.", "Spis."],
    }
    fine = {
        "ingredients": [{"name": "karrypulver", "amount": "2 tsk"}],
        "steps": ["Steg.", "Spis."],
    }
    answers = [vague, fine]
    prompts: list[str] = []

    async def ai(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        prompts.append(kwargs["instructions"])
        return SimpleNamespace(data=answers.pop(0))

    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        await planner._async_recipe(day, plan)
    assert day["ingredients"][0]["name"] == "karrypulver"
    assert "ret dem" in prompts[1]
    assert "Hvert krydderi står for sig" in prompts[0]

    # Not better the second time, or the AI fails: the first is kept.
    for second in (vague, HomeAssistantError("busy")):
        queue: list[Any] = [vague, second]

        async def ai2(hass: HomeAssistant, queue: list[Any] = queue, **kwargs: Any) -> Any:
            answer = queue.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return SimpleNamespace(data=answer)

        with patch("homeassistant.components.ai_task.async_generate_data", new=ai2):
            await planner._async_recipe(day, plan)
        assert day["ingredients"][0]["name"] == "krydderier"


async def test_recipe_extras(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """What an AI recipe uses and the list hasn't goes on it - a few a day."""
    planner = init_integration.runtime_data.planner
    plan = init_integration.runtime_data.store.plans[0]
    sunday = plan["days"][0]
    sunday["ingredients"] = [
        {"name": "hakket oksekød", "amount": "500 g"},  # on the list
        {"name": "salt", "amount": "1 tsk"},  # a basic item
        {"name": "frisk timian", "amount": "1 bundt"},
        {"name": "tomatpuré", "amount": "2 spsk"},
        {"name": "oregano", "amount": "1 tsk"},
        {"name": "gulerod", "amount": "2 stk"},
        {"name": "rødvin", "amount": "1 dl"},  # the fifth: too many
        {"name": "", "amount": ""},
    ]
    plan["days"][2]["recipe_id"] = "own"  # the family's own recipe: as it is
    before = len(plan["shopping"])
    await planner._async_recipe_extras(plan, [], None, None)
    added = [line["name"] for line in plan["shopping"][before:]]
    assert added == ["Frisk timian", "Tomatpuré", "Oregano", "Gulerod"]
    assert "Gulerod" in sunday["uses"]
    await planner._async_recipe_extras(plan, [], None, None)  # the rest the next time
    assert [line["name"] for line in plan["shopping"][before:]][4:] == ["Rødvin"]


# ------------------------------------------------------------------ wishes and settings


def test_day_wishes_and_check() -> None:
    """A dish asked for on a weekday must be that day's dinner."""
    assert dishes.day_wishes("Frikadeller på onsdag. Fløde inden tirsdag", DATES) == {
        "2026-10-21": "Frikadeller"
    }
    assert dishes.day_wishes("torsdagen: tacos, lasagne lørdag", DATES) == {
        "2026-10-22": "tacos",
        "2026-10-24": "lasagne",
    }
    assert dishes.day_wishes("mandag og tirsdag pasta", DATES) == {}  # two days: unclear
    assert dishes.day_wishes("vi vil gerne have onsdag", DATES) == {}  # no dish
    assert dishes.day_wishes("pizza fredag", DATES[:3]) == {}  # not in the plan

    plan = make_plan("p", start="2026-10-18")
    settings = clean_settings({"leftover_days": 1, "fixed_days": [], "no_leftover_weekdays": ["0"]})
    problems = dishes.check_plan(
        plan,
        settings,
        recent=[],
        due_ids=set(),
        wishes={"2026-10-20": "Frikadeller", "2026-10-18": "Spaghetti bolognese"},
    )
    assert any('ønsket "Frikadeller"' in p for p in problems)
    assert not any("Spaghetti" in p and "ønsket" in p for p in problems)
    assert any("vil ikke have rester om mandagen" in p for p in problems)  # monday 19/10


def test_no_leftover_weekdays_setting_and_prompt() -> None:
    """Weekdays without leftovers are cleaned and told to the AI."""
    settings = clean_settings({"no_leftover_weekdays": ["5", 6, "x", 9, "6"]})
    assert settings["no_leftover_weekdays"] == ["5", "6"]
    assert clean_settings({"no_leftover_weekdays": "lørdag"})["no_leftover_weekdays"] == []
    assert mp.no_leftover_weekdays(settings) == {5, 6}
    dates = [mp.date.fromisoformat(d) for d in DATES]
    prompt = mp.build_prompt(
        settings=settings,
        dates=dates,
        catalog=None,
        offers=[],
        favorites_due=[],
        favorites_optional=[],
        recent_dishes=[],
        wishes={"2026-10-21": "Frikadeller"},
    )
    assert "Rester må ALDRIG ligge på: lørdag, søndag" in prompt
    assert "onsdag 2026-10-21: Frikadeller" in prompt
    assert "hakkebøffer" in prompt  # the meat a dish is made of


# ------------------------------------------------------------------ moving a dish


async def test_move_day(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Dinners change places; leftovers never before the food is made."""
    store = init_integration.runtime_data.store
    client = await hass_ws_client(hass)
    plan = store.plans[0]
    # sunday: spaghetti (double portion), monday: its leftovers, tuesday: wok.
    msg = await _ws(client, 1, type="middagsro/day/move", plan_id="p", date="2026-10-19",
                    direction="up")  # fmt: skip
    assert not msg["success"]  # the leftovers would come before the spaghetti
    assert [d["dish"] for d in store.plans[0]["days"]] == [
        "Spaghetti bolognese",
        "Rester af spaghetti bolognese",
        "Kyllingewok med broccoli",
    ]
    # Leftovers down a day: still after the spaghetti, which they keep pointing at.
    msg = await _ws(client, 2, type="middagsro/day/move", plan_id="p", date="2026-10-19",
                    direction="down")  # fmt: skip
    assert msg["success"]
    days = store.plans[0]["days"]
    assert [d["dish"] for d in days] == [
        "Spaghetti bolognese",
        "Kyllingewok med broccoli",
        "Rester af spaghetti bolognese",
    ]
    assert days[2]["uses_leftovers_from"] == "2026-10-18"
    assert [d["date"] for d in days] == ["2026-10-18", "2026-10-19", "2026-10-20"]
    # The spaghetti a day later: its leftovers follow it.
    msg = await _ws(client, 3, type="middagsro/day/move", plan_id="p", date="2026-10-18",
                    direction="down")  # fmt: skip
    assert msg["success"]
    days = store.plans[0]["days"]
    assert days[1]["dish"] == "Spaghetti bolognese"
    assert days[2]["uses_leftovers_from"] == "2026-10-19"
    planner = init_integration.runtime_data.planner
    for direction, date, key in (
        ("up", "2026-10-18", "move_edge"),
        ("down", "2026-10-20", "move_edge"),
        ("down", "2026-10-19", "move_leftovers"),  # leftovers before the spaghetti
    ):
        with pytest.raises(ServiceValidationError) as err:
            await pe.async_move_day(planner, "p", date, direction)
        assert err.value.translation_key == key
    assert store.plans[0]["days"][1]["dish"] == "Spaghetti bolognese"  # as it was
    # A dish built on an offer from monday can't come before monday.
    plan = store.plans[0]
    plan["days"][1]["uses"] = ["Persille"]
    plan["shopping"][1]["buy_from"] = "2026-10-19"
    with pytest.raises(ServiceValidationError) as err:
        await pe.async_move_day(planner, "p", "2026-10-19", "up")
    assert err.value.translation_key == "move_offer"


async def test_move_past_day(
    hass: HomeAssistant, init_integration: MockConfigEntry, freezer: Any
) -> None:
    """Days that have passed stay as they were."""
    freezer.move_to("2026-10-19T10:00:00+00:00")
    with pytest.raises(ServiceValidationError) as err:
        await pe.async_move_day(init_integration.runtime_data.planner, "p", "2026-10-19", "up")
    assert err.value.translation_key == "move_past"


# ------------------------------------------------------------------ one item to REMA


async def test_send_one_line(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """One item straight to the REMA list; the rest is sent as before."""
    client = await hass_ws_client(hass)
    store = init_integration.runtime_data.store
    msg = await _ws(client, 1, type="middagsro/send", plan_id="p", line_id="l0")
    assert msg["success"]
    assert mock_client.async_add_to_list.await_count == 1
    lines = store.plans[0]["shopping"]
    assert lines[0]["sent"] and not lines[1].get("sent")
    assert store.plans[0]["last_sent"]["ids"] == ["l0"]
    assert store.plans[0]["status"] != "sent"
    msg = await _ws(client, 2, type="middagsro/send", plan_id="p", line_id="l0")
    assert not msg["success"]  # sent already


# ------------------------------------------------------------------ choosing dishes


async def test_put_picks(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The dishes the family chose are put on their days with their own recipes."""
    planner = init_integration.runtime_data.planner
    plan = init_integration.runtime_data.store.plans[0]
    rema = {"name": "Kylling i karry", "type": "normal", "ingredients": [], "steps": []}
    swapped: list[tuple[str, dict[str, Any]]] = []

    async def swap(planner: Any, plan_id: str, day: str, option: dict[str, Any]) -> dict[str, Any]:
        swapped.append((day, option))
        if option["dish"] == "Fejler":
            raise HomeAssistantError("AI'en svarede ikke")
        return plan

    with (
        patch.object(pe, "async_swap_dish", side_effect=swap),
        patch.object(planner.rema_recipes, "async_get", AsyncMock(return_value=rema)),
    ):
        await planner._async_put_picks(
            plan,
            {
                "2026-10-18": {"dish": "Lasagne", "source": "collection", "recipe_id": "r1"},
                "2026-10-19": {"dish": "Karry", "source": "rema", "slug": "kylling-i-karry"},
                "2026-10-20": {"dish": "Mormors boller", "source": "mealie", "slug": "boller"},
                "2026-10-21": {"dish": "Fejler"},
            },
        )
    assert swapped[0] == ("2026-10-18", {"dish": "Lasagne", "type": "normal", "recipe_id": "r1"})
    assert swapped[1][1]["dish"] == "Kylling i karry"
    assert swapped[1][1]["recipe_id"]  # saved in the collection
    assert swapped[2][1] == {"dish": "Mormors boller", "type": "normal", "mealie": "boller"}
    assert len(swapped) == 4


async def test_generate_with_picks(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The panel sends the chosen dishes with the plan."""
    client = await hass_ws_client(hass)
    planner = init_integration.runtime_data.planner
    picks = {"2026-10-21": {"dish": "Frikadeller", "source": "collection", "recipe_id": "r1"}}
    with patch.object(planner, "async_start_generation") as start:
        msg = await _ws(client, 1, type="middagsro/generate", start_date="2026-10-18", picks=picks)
    assert msg["success"]
    assert start.call_args.kwargs["picks"] == picks


async def test_mealie_recipes(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The family's Mealie recipes to choose from."""
    client = await hass_ws_client(hass)
    mealie = init_integration.runtime_data.planner.mealie
    with patch.object(
        mealie,
        "async_summaries",
        AsyncMock(return_value=[{"slug": "a", "name": "Boller"}, {"slug": "b"}]),
    ):
        msg = await _ws(client, 1, type="middagsro/mealie/recipes")
    assert msg["result"] == {
        "recipes": [{"slug": "a", "name": "Boller"}, {"slug": "b", "name": "b"}]
    }
    with patch.object(mealie, "async_summaries", AsyncMock(side_effect=MealieError("nede"))):
        msg = await _ws(client, 2, type="middagsro/mealie/recipes")
    assert not msg["success"]


async def test_generation_keeps_the_picks(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """The AI is told the chosen dish, and the plan is checked for it."""
    planner = init_integration.runtime_data.planner
    seen: dict[str, Any] = {}

    async def generate(start: Any, skip: Any = None, **kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        await asyncio.sleep(0)
        return {"id": "x"}

    with patch.object(planner, "async_generate", side_effect=generate):
        planner.async_start_generation(
            mp.date(2026, 10, 18), picks={"2026-10-21": {"dish": "Frikadeller"}}
        )
        await planner._task
    assert seen["picks"] == {"2026-10-21": {"dish": "Frikadeller"}}


# ------------------------------------------------------------------ 2.4.1


async def test_mixed_meat_offer_is_beef_for_beef(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """An offer on minced beef, pork-veal or chicken: "hakket oksekød" is the beef."""
    from custom_components.middagsro.api import Offer  # noqa: PLC0415

    planner = init_integration.runtime_data.planner
    offer = Offer(
        id="o0",
        heading="Hakket dansk oksekød, grise- og kalvekød eller kyllingekød",
        description=None,
        price=29.0,
        pre_price=None,
        quantity="400 g",
        valid_from=None,
        valid_to=None,
        product_ids=(1, 2),
    )
    pork = make_product(1, "HK. GRIS & KALV 4-7%", 29, underline="400 GR.")
    beef = make_product(2, "HK. OKSEKØD 8-12%", 29, underline="400 GR.")
    line = {"name": "Hakket dansk oksekød", "search": "Hakket oksekød", "amount": 2, "unit": "pk"}
    assert planner._candidates(line, [pork], "Hakket oksekød", offer=offer)[0] == []
    found, _ = planner._candidates(line, [pork, beef], "Hakket oksekød", offer=offer)
    assert [p.id for p in found] == [2]


async def test_move_in_a_plan_that_was_a_little_wrong(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """What was wrong before the move doesn't stop it; the error is in Danish."""
    store = init_integration.runtime_data.store
    plan = store.plans[0]
    # The AI put a dish on tuesday with an item from a wednesday offer.
    plan["days"][2]["uses"] = ["Persille"]
    plan["shopping"][1]["buy_from"] = "2026-10-21"
    client = await hass_ws_client(hass)
    msg = await _ws(client, 1, type="middagsro/day/move", plan_id="p", date="2026-10-19",
                    direction="down")  # fmt: skip
    assert msg["success"]
    msg = await _ws(client, 2, type="middagsro/day/move", plan_id="p", date="2026-10-18",
                    direction="down")  # fmt: skip
    assert msg["success"]  # spaghetti on monday, its leftovers on tuesday
    msg = await _ws(client, 3, type="middagsro/day/move", plan_id="p", date="2026-10-20",
                    direction="up")  # fmt: skip
    assert msg["error"]["message"] == "Rester kan ikke ligge før den dag, maden laves"

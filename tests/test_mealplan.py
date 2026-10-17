"""Tests for meal plans: prompts, AI answers, product matching and sending."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rema1000 import mealplan as mp
from custom_components.rema1000.api import Offer, RemaError
from custom_components.rema1000.const import DOMAIN
from custom_components.rema1000.storage import clean_settings
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir

from .conftest import CATALOGUE, CURRENT, OFFERS, UPCOMING, fake_search, make_plan, make_product

START = date(2026, 10, 18)  # Sunday, the day the next avis starts
SKIP = date(2026, 10, 21)

# ----------------------------------------------------------------- functions


def test_dates() -> None:
    """Start days, plan days and dates from the panel."""
    assert mp.next_start(date(2026, 10, 14), 6) == START
    assert mp.next_start(START, 6) == START
    assert mp.plan_dates(START, 3, {START + timedelta(days=1)}) == [
        START,
        START + timedelta(days=2),
    ]
    assert mp.parse_date(None) is None
    assert mp.parse_date("2026-10-18T00:00:00") == START
    # Named after the week of the plan's monday, like REMA's avis.
    assert mp.plan_title(mp.plan_dates(START, 7)) == "Madplan uge 43"
    assert mp.plan_week([date(2026, 10, 17)]) == 42
    with pytest.raises(ServiceValidationError):
        mp.parse_date("18/10")


def test_units_and_packages() -> None:
    """Package sizes are read from REMA's underline."""
    assert mp.to_base(2, None) is None
    assert mp.to_base(2, "spande") is None
    assert mp.to_base(1.5, "kg") == ("g", 1500)
    assert mp.package_size(None) is None
    assert mp.package_size("4 X 1,5 L / COCA-COLA") == ("ml", 6000)
    assert mp.package_size("500 GR. / DANSK") == ("g", 500)
    assert mp.package_size("ASSORTERET") is None
    beef = make_product(1, "OKSEKØD", 40, underline="500 GR.")
    assert mp.packages_needed(None, "g", beef) == 1
    assert mp.packages_needed(1000, "g", beef) == 2
    assert mp.packages_needed(1000, "g", make_product(2, "X", 1, underline="4 X 250 G")) == 1
    assert mp.packages_needed(3, "dåser", beef) == 3
    assert mp.packages_needed(3, "stk", make_product(3, "AVOCADO", 8)) == 3
    assert mp.packages_needed(8, "stk", make_product(4, "PITA", 15, underline="375 GR.")) == 1
    assert mp.packages_needed(2, "spande", beef) == 1


def test_words() -> None:
    """Search terms and how well a name fits."""
    assert mp.search_queries({"search": "kyllingefars", "name": "Kyllingefars"}) == [
        "kyllingefars",
        "hakket kylling",
    ]
    assert mp.name_fit(["løg"], "LØG") == (1, 1.0)
    matched, penalty = mp.name_fit(["løg"], "HVIDLØG")
    assert matched == 1
    assert penalty > 5
    assert mp.name_fit(["laks"], "RØGET LAKSEPÅLÆG")[1] > 5
    assert mp.name_fit(["kartofler"], "SØDE KARTOFLER")[1] > 5
    assert mp.name_fit(["laks"], "BROCCOLI") == (0, 1.15)


def test_extract_json() -> None:
    """The JSON object is found in an AI answer."""
    assert mp.extract_json({"a": 1}) == {"a": 1}
    assert mp.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert mp.extract_json('Her er planen: {"a": {"b": 2}} Hej') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        mp.extract_json("ingen json")
    with pytest.raises(ValueError):
        mp.extract_json(None)


def test_kinds() -> None:
    """Eggs, milk and fruit & vegetables are recognised."""
    assert mp.egg_level(make_product(1, "FRILANDSÆG", 30)) == 1
    assert mp.egg_level(make_product(1, "ØKO. ÆG", 30)) == 2
    assert mp.egg_level(make_product(1, "SKRABEÆG", 30)) == 0
    assert mp.line_kind({"search": "æg"}) == "egg"
    assert mp.line_kind({"search": "pålæg"}) is None
    assert mp.line_kind({"search": "letmælk"}) == "milk"
    assert mp.line_kind({"search": "havremælk"}) is None
    assert mp.line_kind({"search": "chokolademælk"}) is None
    assert mp.line_kind({"search": "gulerødder", "category": "Frugt & grønt"}) == "produce"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3 x æg", (3, "æg")),
        ("3x æg", (3, "æg")),
        ("3xæg", (3, "æg")),
        ("3 stk æg", (3, "æg")),
        ("3 æg", (3, "æg")),
        ("tre æg", (3, "æg")),
        ("To poser chips", (2, "chips")),
        ("<3 letmælk>", (3, "letmælk")),
        ("“Rugbrød”", (1, "Rugbrød")),
        ("500 g mel", (1, "500 g mel")),
        ("0 x æg", (1, "æg")),
        ("", (1, "")),
    ],
)
def test_parse_quick_add(text: str, expected: tuple[int, str]) -> None:
    """Amounts are read from typed and spoken text."""
    assert mp.parse_quick_add(text) == expected


def test_plan_summary() -> None:
    """Plans are listed with their dishes."""
    summary = mp.plan_summary(make_plan())
    assert summary["id"] == "plan-1"
    assert summary["dishes"][2] == "Kyllingewok med broccoli"


def test_prompt_with_every_rule() -> None:
    """Every setting ends up in the instructions for the AI."""
    settings = clean_settings(
        {
            "allergies": ["nuts"],
            "allergies_other": "kiwi",
            "avoid": ["pork"],
            "avoid_other": "svampe",
            "disliked_dishes": ["Fiskefrikadeller"],
            "organic": "only",
            "egg_min": "organic",
            "milk_organic": True,
            "produce_organic": True,
            "must_haves": [{"name": "Kaffe", "amount": 1}],
            "fixed_days": [{"weekday": 3, "text": "Rugbrødsdag"}],
        }
    )
    dates = mp.plan_dates(START, 7, {SKIP})
    prompt = mp.build_prompt(
        settings=settings,
        dates=dates,
        catalog=UPCOMING,
        offers=OFFERS,
        favorites_due=[{"id": "f1", "text": "Lasagne"}],
        favorites_optional=[{"id": "f2", "text": "Laks", "frequency": "on_offer"}],
        recent_dishes=["Tacos"],
        feedback="For dyrt",
        skipped=[SKIP],
        note="Fløde skal bruges inden tirsdag",
    )
    for part in (
        "Familiens ønsker til netop denne madplan",
        "Fløde skal bruges inden tirsdag",
        '"title": "Madplan uge 43"',
        "springes over",
        "onsdag 2026-10-21",
        "nødder, kiwi",
        "svinekød, svampe",
        "Fiskefrikadeller",
        "Tacos",
        "udelukkende økologiske",
        "økologiske æg",
        "Mælk skal være økologisk",
        "Frugt og grønt skal være økologisk",
        "VIGTIGT fra sidste forsøg: For dyrt",
        "[f1] Lasagne",
        "[f2] Laks (kun på tilbud)",
        "Faste ugevarer",
        "torsdag 2026-10-22: Rugbrødsdag",
        "UGENS TILBUD I REMA 1000 (Uge 43)",
        "o0 | Hakket oksekød 8-12% | 40 kr. (før 50) | 500 g 500 g",
        "o1 | Broccoli | 10 kr.",
        "days skal have præcis 6 elementer",
    ):
        assert part in prompt, part

    plain = mp.build_prompt(
        settings=clean_settings(
            {
                "leftover_days": 0,
                "organic": "none",
                "egg_min": "free_range",
                "pantry": "",
                "wishes": "",
                "budget": 0,
                "household": [],
            }
        ),
        dates=[START],
        catalog=None,
        offers=[OFFERS[1]],
        favorites_due=[],
        favorites_optional=[],
        recent_dishes=[],
    )
    assert "Ingen restedage" in plain
    assert "billigste varer" in plain
    assert "mindst frilandsæg" in plain
    assert "- 2 voksne" in plain
    assert "UGENS TILBUD I REMA 1000 (Ugens tilbud)" in plain
    assert "skal koste under" not in plain


def test_recipe_prompt() -> None:
    """The recipe prompt follows the household and the week's shopping."""
    settings = clean_settings(
        {
            "allergies": ["egg"],
            "allergies_other": "kiwi",
            "avoid": ["spicy"],
            "avoid_other": "svampe",
        }
    )
    plan = make_plan(start="2026-10-12")
    day = plan["days"][0]  # Monday, makes leftovers
    prompt = mp.build_recipe_prompt(settings=settings, day=day, plan=plan)
    assert "Lav dobbelt portion" in prompt
    assert "æg, kiwi" in prompt
    assert "stærk mad, svampe" in prompt
    assert "Højst 30 minutters" in prompt
    assert "Hakket oksekød (500 g)" in prompt
    assert "Persille (1 bundt), Spaghetti." in prompt

    weekend = mp.build_recipe_prompt(
        settings=clean_settings({"pantry": ""}),
        day={**day, "date": "2026-10-17", "makes_leftovers": False},
        plan={"shopping": []},
    )
    assert "Højst" not in weekend
    assert "Familiens ønsker" not in weekend
    noted = mp.build_recipe_prompt(
        settings=clean_settings({}), day=day, plan={"shopping": [], "note": "Brug fløden"}
    )
    assert (
        "Familiens ønsker til ugen (brug varer, de allerede har, hvor det passer): Brug fløden"
        in noted
    )
    assert "salt og peber" in weekend


# ----------------------------------------------------------------- planner


def ai_answer(dates: list[date], shopping: list[dict[str, Any]]) -> dict[str, Any]:
    """An AI answer for a plan over some dates."""
    days = []
    for idx, day in enumerate(dates):
        leftover = idx == 2
        days.append(
            {
                "date": day.isoformat(),
                "dish": "Rester af lasagne" if leftover else f"Ret {idx}",
                "type": "rester" if leftover else "normal",
                "uses_leftovers_from": dates[1].isoformat() if leftover else None,
                "makes_leftovers": idx == 1,
                "servings": "4",
                "active_minutes": 20,
                "total_minutes": "35",
            }
        )
    return {
        "title": "Madplan uge 43",
        "summary": "Hyggelig uge",
        "days": days,
        "shopping": shopping,
        "checklist": [{"requirement": "Budget", "ok": True}, "ikke en dict"],
        "deviations": "",
    }


SHOPPING = [
    {"name": "Hakket oksekød", "amount": 1000, "unit": "g", "search": "hakket oksekød",
     "category": "Kød", "offer": "o0"},
    {"name": "Æg", "amount": 6, "unit": "stk", "search": "æg", "category": "Mejeri"},
    {"name": "Letmælk", "amount": "1", "unit": "L", "search": "letmælk", "category": "Mejeri"},
    {"name": "Spaghetti", "amount": 500, "unit": "g", "search": "spaghetti", "category": "Kolonial"},
    {"name": "Løg", "amount": 2, "unit": "stk", "search": "løg", "category": "Frugt & grønt"},
    {"name": "Persille", "amount": 1, "unit": "bundt", "search": "persille",
     "category": "Frugt & grønt"},
    {"name": "Broccoli", "amount": 2, "unit": "stk", "search": "broccoli",
     "category": "Frugt & grønt", "offer": "o1"},
    {"amount": 1},
    "ikke en dict",
]  # fmt: skip

RECIPE = {
    "ingredients": [{"name": "spaghetti", "amount": "500 g"}, {"amount": "1"}],
    "steps": [{"text": "Kog pastaen.", "minutes": "10"}, "Server.", ""],
    "tip": "Gem lidt pastavand.",
    "active_minutes": 15,
    "total_minutes": 30,
}

SETTINGS = {
    "budget": 1000,
    "egg_min": "free_range",
    "milk_organic": True,
    "allergies": ["gluten"],
    "must_haves": [{"name": "Rugbrød", "product_id": 70001, "amount": 2}],
    "ai_task_entity": "ai_task.assistant",
}


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """The family's settings and an earlier plan."""
    return {
        "settings": SETTINGS,
        "plans": [make_plan("old", start="2026-10-11")],
        "favorites": [{"id": "fav1", "text": "Lasagne", "frequency": "weekly", "last_used": None}],
    }


class FakeAI:
    """Answers the planner's AI tasks."""

    def __init__(self, *plans: dict[str, Any], recipe: Any = RECIPE) -> None:
        self.plans = list(plans)
        self.recipe = recipe
        self.prompts: list[str] = []
        self.entities: list[str | None] = []

    async def __call__(self, hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)  # like a real AI call, let the event loop run
        self.entities.append(kwargs["entity_id"])
        if kwargs["task_name"] == "REMA 1000 madplan":
            self.prompts.append(kwargs["instructions"])
            answer = self.plans.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return SimpleNamespace(data=answer)
        recipe = self.recipe(kwargs) if callable(self.recipe) else self.recipe
        if isinstance(recipe, Exception):
            raise recipe
        return SimpleNamespace(data=recipe)


async def _generate(planner: mp.MealPlanner, ai: FakeAI, **kwargs: Any) -> None:
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        planner.async_start_generation(START, **kwargs)
        assert planner.generating
        await planner._task


async def test_generate_plan(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """A plan is made, priced by the family's rules and stored with recipes."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    await store.async_set_note("Fløde skal bruges inden tirsdag")
    dates = mp.plan_dates(START, 7, {SKIP})
    ai = FakeAI(json.dumps(ai_answer(dates, SHOPPING)))  # type: ignore[arg-type]
    await _generate(planner, ai, skip={SKIP})

    assert planner.status["state"] == "idle"
    plan = init_integration.runtime_data.store.latest_plan
    assert plan is not None
    assert plan["start_date"] == "2026-10-18"
    assert plan["title"] == "Madplan uge 43"
    assert plan["week"] == 43
    assert plan["skipped"] == ["2026-10-21"]
    # The wishes were used for this plan only.
    assert "Fløde skal bruges inden tirsdag" in ai.prompts[0]
    assert plan["note"] == "Fløde skal bruges inden tirsdag"
    assert store.note == ""
    assert [d["date"] for d in plan["days"]] == [d.isoformat() for d in dates]
    assert "onsdag 2026-10-21" in ai.prompts[0]
    assert "[fav1] Lasagne" in ai.prompts[0]
    assert set(ai.entities) == {"ai_task.assistant"}

    chosen = {line["name"]: line for line in plan["shopping"]}
    assert chosen["Hakket oksekød"]["product"]["id"] == 30001  # on offer
    assert chosen["Hakket oksekød"]["packages"] == 2
    assert chosen["Hakket oksekød"]["offer_name"] == "Hakket oksekød 8-12%"
    assert chosen["Æg"]["product"]["id"] == 40003  # organic within 20 %
    assert chosen["Letmælk"]["product"]["id"] == 20496  # organic milk required
    assert chosen["Spaghetti"]["product"]["id"] == 60003  # gluten-free
    assert chosen["Spaghetti"]["packages"] == 2
    assert chosen["Løg"]["product"]["id"] == 50003  # not hvidløg
    assert chosen["Persille"]["product"] is None
    assert "fritekst" in chosen["Persille"]["note"]
    assert chosen["Broccoli"]["product"]["id"] == 50002
    assert chosen["Rugbrød"]["product"]["id"] == 70001
    assert chosen["Rugbrød"]["packages"] == 2
    assert len(plan["shopping"]) == 8
    assert plan["total"] == pytest.approx(80 + 38 + 13.95 + 44 + 8 + 28 + 36)
    assert plan["over_budget"] is False
    assert plan["checklist"] == [{"requirement": "Budget", "ok": True}]

    leftover = plan["days"][2]
    assert leftover["steps"][0]["text"] == "Varm resten af Ret 1 op, og server den."
    assert leftover["ingredients"] == []
    cooked = plan["days"][0]
    assert cooked["ingredients"] == [{"name": "spaghetti", "amount": "500 g"}]
    assert cooked["steps"] == [
        {"text": "Kog pastaen.", "minutes": 10},
        {"text": "Server.", "minutes": 0},
    ]
    assert cooked["total_minutes"] == 30

    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, mp.ISSUE_NO_AI_TASK) is None


async def test_plan_priced_on_its_first_day(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """A plan for next week is priced with next week's prices and offers."""
    seen: list[datetime | None] = []

    async def search(query: str, limit: int = 24, at: datetime | None = None) -> list[Any]:
        seen.append(at)
        return await fake_search(query, limit)

    mock_client.async_search_products.side_effect = search
    planner = init_integration.runtime_data.planner
    dates = mp.plan_dates(START, 7)
    await _generate(planner, FakeAI(ai_answer(dates, SHOPPING[:2])))
    assert seen
    assert set(seen) == {datetime(2026, 10, 18, 10, tzinfo=UTC)}  # noon danish time
    # A plan that starts today (it is noon now) is priced now.
    assert mp.MealPlanner.price_time(date(2026, 10, 14)) is None
    # Something typed for the list is priced now.
    seen.clear()
    await planner.async_quick_add("letmælk")
    assert seen == [None]


def test_late_offers_in_prompt() -> None:
    """Offers that start thursday: left out, or marked with their first day."""
    coffee = Offer(id="o-3", heading="Kaffe", description=None, price=39, pre_price=None,
                   quantity=None, valid_from="2026-10-21T22:00:00+0000",
                   valid_to="2026-10-24T21:59:59+0000")  # fmt: skip
    offers = [*OFFERS, coffee]
    late = mp.late_offers(offers, START)
    assert late == {2: date(2026, 10, 22)}
    assert mp.late_offers(offers, date(2026, 10, 22)) == {}
    kwargs: dict[str, Any] = {
        "dates": mp.plan_dates(START, 7),
        "catalog": UPCOMING,
        "offers": offers,
        "favorites_due": [],
        "favorites_optional": [],
        "recent_dishes": [],
        "late": late,
    }
    once = mp.build_prompt(settings=clean_settings({}), **kwargs)
    assert "Kaffe" not in once
    assert "gælder først fra" not in once
    twice = mp.build_prompt(settings=clean_settings({"shop_late_week": True}), **kwargs)
    assert "o2 | Kaffe | 39 kr. | | gælder først fra torsdag 2026-10-22" in twice
    assert "må KUN bruges i retter på eller efter den dag" in twice


async def test_late_offer_bought_on_its_day(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    ai_task: str,
) -> None:
    """With late-week shopping, a thursday offer is bought and priced on thursday."""
    store = init_integration.runtime_data.store
    await store.async_set_settings({**SETTINGS, "shop_late_week": True, "must_haves": []})
    coffee = Offer(id="o-3", heading="Kaffe", description=None, price=39, pre_price=None,
                   quantity=None, valid_from="2026-10-21T22:00:00+0000",
                   valid_to="2026-10-24T21:59:59+0000")  # fmt: skip
    mock_client.async_get_offers.return_value = [*OFFERS, coffee]
    seen: dict[str, datetime | None] = {}

    async def search(query: str, limit: int = 24, at: datetime | None = None) -> list[Any]:
        seen.setdefault(query, at)
        return await fake_search(query, limit)

    mock_client.async_search_products.side_effect = search
    shopping = [
        SHOPPING[0],
        {"name": "Kaffe", "amount": 1, "unit": "pk", "search": "kaffe", "offer": "o2"},
    ]
    planner = init_integration.runtime_data.planner
    await _generate(planner, FakeAI(ai_answer(mp.plan_dates(START, 7), shopping)))
    plan = store.latest_plan
    assert plan is not None
    lines = {line["name"]: line for line in plan["shopping"]}
    assert lines["Kaffe"]["buy_from"] == "2026-10-22"
    assert lines["Hakket oksekød"]["buy_from"] is None
    assert seen["kaffe"] == datetime(2026, 10, 22, 10, tzinfo=UTC)
    assert seen["hakket oksekød"] == datetime(2026, 10, 18, 10, tzinfo=UTC)


async def test_generate_over_budget_tries_again(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """Over budget: the AI is asked once more and the cheapest plan is kept."""
    store = init_integration.runtime_data.store
    await store.async_set_settings({**SETTINGS, "budget": 100, "must_haves": []})
    planner = init_integration.runtime_data.planner
    dates = mp.plan_dates(START, 7)
    cheap = [{"name": "Løg", "amount": 2, "unit": "stk", "search": "løg"}]
    ai = FakeAI(ai_answer(dates, SHOPPING[:4]), ai_answer(dates, cheap))
    await _generate(planner, ai, send=True)

    assert len(ai.prompts) == 2
    assert "budgettet er 100 kr" in ai.prompts[1]
    plan = store.latest_plan
    assert plan is not None
    assert plan["total"] == 8
    assert plan["status"] == "sent"  # send=True


async def test_generate_keeps_cheapest_when_still_over(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """If both tries are over budget, the cheaper one is kept and marked."""
    store = init_integration.runtime_data.store
    await store.async_set_settings({**SETTINGS, "budget": 5, "must_haves": []})
    planner = init_integration.runtime_data.planner
    dates = mp.plan_dates(START, 7)
    ai = FakeAI(
        ai_answer(dates, SHOPPING[4:5]),
        ai_answer(dates, SHOPPING[:2]),
        recipe=HomeAssistantError("busy"),
    )
    await _generate(planner, ai)
    plan = store.latest_plan
    assert plan is not None
    assert plan["total"] == 8
    assert plan["over_budget"] is True
    assert plan["days"][0]["recipe_error"] == "busy"


async def test_generate_errors(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """Problems while making a plan are shown in the status."""
    planner = init_integration.runtime_data.planner
    await _generate(planner, FakeAI(HomeAssistantError("Finish reason MAX_TOKENS")))
    assert planner.status["state"] == "error"
    assert "MAX_TOKENS" in planner.status["message"]

    await _generate(planner, FakeAI("ikke json", "stadig ikke json"))
    assert planner.status["state"] == "error"

    await _generate(planner, FakeAI(HomeAssistantError("offline")))
    assert planner.status["message"] == "offline"

    dates = mp.plan_dates(START, 7)
    await _generate(planner, FakeAI("ikke json", ai_answer(dates, [])))
    assert planner.status["state"] == "idle"


async def test_generation_guards(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """No AI, everything skipped or already running."""
    planner = init_integration.runtime_data.planner
    with pytest.raises(ServiceValidationError) as err:
        planner.async_start_generation(START)
    assert err.value.translation_key == "no_ai_task"
    assert ir.async_get(hass).async_get_issue(DOMAIN, mp.ISSUE_NO_AI_TASK) is not None

    hass.states.async_set("ai_task.assistant", "unknown")
    every_day = {START + timedelta(days=i) for i in range(7)}
    with pytest.raises(ServiceValidationError) as err:
        planner.async_start_generation(START, skip=every_day)
    assert err.value.translation_key == "all_days_skipped"
    with pytest.raises(ServiceValidationError):
        await planner.async_generate(START, every_day)

    async def forever(*args: Any) -> None:
        await asyncio.Event().wait()

    with patch.object(planner, "_async_run", side_effect=forever):
        planner.async_start_generation()
        with pytest.raises(ServiceValidationError) as err:
            planner.async_start_generation()
        assert err.value.translation_key == "already_generating"
        planner.async_cancel()
        await asyncio.sleep(0)
    assert not planner.generating
    planner.async_cancel()  # nothing running


async def test_ai_entity_choice(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The chosen AI, else Home Assistant's preferred one, else the first."""
    planner = init_integration.runtime_data.planner
    assert planner._ai_entity() == "ai_task.assistant"  # chosen but missing
    hass.states.async_set("ai_task.other", "unknown")
    assert planner._ai_entity() == "ai_task.other"
    hass.states.async_set("ai_task.assistant", "unknown")
    assert planner._ai_entity() == "ai_task.assistant"

    await init_integration.runtime_data.store.async_set_settings({"ai_task_entity": None})
    hass.data["ai_task_preferences"] = SimpleNamespace(gen_data_entity_id="ai_task.other")
    assert planner._ai_entity() is None
    hass.states.async_remove("ai_task.other")
    hass.states.async_remove("ai_task.assistant")
    assert planner.ai_available()
    del hass.data["ai_task_preferences"]
    assert not planner.ai_available()


async def test_offers_for_the_plan(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """The avis that covers the start day is used."""
    planner = init_integration.runtime_data.planner
    catalog, offers = await planner._async_offers(START)
    assert catalog is UPCOMING
    assert offers == OFFERS
    catalog, _ = await planner._async_offers(date(2026, 10, 14))
    assert catalog is CURRENT
    catalog, _ = await planner._async_offers(date(2026, 12, 1))
    assert catalog is CURRENT  # nothing covers it: the current avis

    mock_client.async_get_offers.side_effect = RemaError("Tjek is down")
    assert await planner._async_offers(START) == (UPCOMING, [])

    with patch.object(planner, "_get_catalogs", return_value=(None, None)):
        assert await planner._async_offers(START) == (None, [])


async def test_regenerate_recipe(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """One day's recipe can be written again."""
    planner = init_integration.runtime_data.planner
    with patch("homeassistant.components.ai_task.async_generate_data", new=FakeAI()):
        day = await planner.async_regenerate_recipe("old", "2026-10-11")
    assert day["tip"] == "Gem lidt pastavand."

    with (
        patch(
            "homeassistant.components.ai_task.async_generate_data",
            new=FakeAI(recipe=HomeAssistantError("busy")),
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await planner.async_regenerate_recipe("old", "2026-10-11")
    assert err.value.translation_key == "recipe_failed"

    with pytest.raises(ServiceValidationError):
        await planner.async_regenerate_recipe("old", "2030-01-01")
    with pytest.raises(ServiceValidationError):
        await planner.async_regenerate_recipe("missing", "2026-10-11")

    # A leftover day needs no AI; it refers to the day it comes from.
    day = await planner.async_regenerate_recipe("old", "2026-10-12")
    assert day["steps"][0]["text"] == "Varm resten af Spaghetti bolognese op, og server den."


async def test_quick_add_rules(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Typed items: every word must fit, organic rules apply, else free text."""
    planner = init_integration.runtime_data.planner
    result = await planner.async_quick_add("cigaretter til far")
    assert result["free_text"] is True

    await init_integration.runtime_data.store.async_set_settings({"organic": "only"})
    result = await planner.async_quick_add("broccoli")
    assert result["product_id"] == 50002

    result = await planner.async_quick_add("spaghetti")
    assert result["product_id"] == 60002
    result = await planner.async_quick_add("rugbrød")
    assert result["note"] == "Ingen økologisk variant fundet"

    with pytest.raises(ServiceValidationError):
        await planner.async_quick_add("  ")

    mock_client.async_search_products.side_effect = RemaError("HTTP 500")
    result = await planner.async_quick_add("2 x kaffe")
    assert result["free_text"] is True
    assert result["added"] == "2 × kaffe"
    assert result["note"].startswith("Søgning fejlede")


async def test_matching_requirements_fallback(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """When no product meets a rule, it is searched for, else the cheapest is used."""
    planner = init_integration.runtime_data.planner
    await init_integration.runtime_data.store.async_set_settings(
        {"egg_min": "organic", "produce_organic": True}
    )
    only_caged = [p for p in CATALOGUE if p.id == 40001]
    organic = [p for p in CATALOGUE if p.id == 40003]

    async def search(query: str, limit: int = 24) -> list[Any]:
        if query in ("økologiske æg",):
            return organic
        if query == "øko æg":
            raise RemaError("timeout")
        return only_caged

    mock_client.async_search_products.side_effect = search
    line: dict[str, Any] = {"name": "Æg", "search": "æg", "amount": 10, "unit": "stk"}
    await planner._async_match(line)
    assert line["product"]["id"] == 40003

    organic.clear()
    line = {"name": "Æg", "search": "æg", "amount": 10, "unit": "stk"}
    await planner._async_match(line)
    assert line["product"]["id"] == 40001
    assert line["note"] == "Ingen vare opfylder kravet om økologiske æg – billigste valgt"

    async def broccoli(query: str, limit: int = 24) -> list[Any]:
        if query.startswith("øko"):
            raise RemaError("timeout")
        return [p for p in CATALOGUE if p.id == 50001]

    mock_client.async_search_products.side_effect = broccoli
    line = {"name": "Broccoli", "search": "broccoli", "amount": 1, "unit": "stk",
            "category": "Frugt & grønt"}  # fmt: skip
    await planner._async_match(line)
    assert line["product"]["id"] == 50001


async def test_must_have_lines(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Weekly must-haves: the chosen product, else the first priced result, else text."""
    planner = init_integration.runtime_data.planner
    line: dict[str, Any] = {"name": "Kaffe", "search": "Kaffe", "amount": 1, "must_have": True,
                            "product_id": None}  # fmt: skip
    await planner._async_match(line)
    assert line["product"] is None
    assert "fritekst" in line["note"]

    line = {"name": "Mælk", "search": "mælk", "amount": None, "must_have": True,
            "product_id": None}  # fmt: skip
    await planner._async_match(line)
    assert line["product"]["id"] == 20494

    calls = []

    async def search(query: str, limit: int = 24) -> list[Any]:
        calls.append(query)
        return [] if query == "kaffe filter" else [p for p in CATALOGUE if p.id == 70001]

    mock_client.async_search_products.side_effect = search
    line = {"name": "Rugbrød", "search": "kaffe filter", "amount": 1, "must_have": True,
            "product_id": 70001}  # fmt: skip
    await planner._async_match(line)
    assert calls == ["kaffe filter", "Rugbrød"]
    assert line["product"]["id"] == 70001

    line = {"name": "Rugbrød", "search": "Rugbrød", "amount": 1, "must_have": False,
            "product_id": 12345}  # fmt: skip
    await planner._async_match(line)
    assert line["product"] is None


async def test_candidates_edge_cases(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Unpriced products, neutral words and nothing called what was searched."""
    planner = init_integration.runtime_data.planner
    unpriced = make_product(1, "MÆLK", None)
    assert planner._candidates({}, [unpriced], "mælk") == ([], {})
    assert planner._candidates({}, CATALOGUE, "dansk rema") == ([], {})
    assert planner._candidates({}, CATALOGUE[:1], "laks")[0] == []


async def test_send_without_plan(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """There must be a plan to send."""
    init_integration.runtime_data.store.plans.clear()
    with pytest.raises(ServiceValidationError) as err:
        await init_integration.runtime_data.planner.async_send()
    assert err.value.translation_key == "no_plan"


async def test_auto_generate_rules(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """Automatic plans: only when on, for the new avis, once per week."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    with patch.object(planner, "async_start_generation") as start:
        planner.async_check_auto_generate(UPCOMING)  # switched off
        await store.async_set_settings({"auto_generate": True})
        planner.async_check_auto_generate(None)
        planner.async_check_auto_generate(CURRENT)  # does not cover next Sunday
        planner.async_check_auto_generate(UPCOMING)
        planner.async_check_auto_generate(UPCOMING)  # already tried this week
        assert start.call_count == 1

    planner._auto_attempted.clear()
    with patch.object(
        planner, "async_start_generation", side_effect=ServiceValidationError("no ai")
    ) as start:
        planner.async_check_auto_generate(UPCOMING)  # logged, not raised
    start.assert_called_once()

    planner._auto_attempted.clear()
    await store.async_add_plan(make_plan("next", start="2026-10-18"))
    with patch.object(planner, "async_start_generation") as start:
        planner.async_check_auto_generate(UPCOMING)  # a plan exists already
    start.assert_not_called()


async def test_auto_generate_on_start_day(
    hass: HomeAssistant, init_integration: MockConfigEntry, freezer: Any
) -> None:
    """On the start day itself the plan for the week after is made."""
    planner = init_integration.runtime_data.planner
    await init_integration.runtime_data.store.async_set_settings(
        {"auto_generate": True, "start_weekday": 2}
    )
    with patch.object(planner, "async_start_generation") as start:
        planner.async_check_auto_generate(UPCOMING)
    assert start.call_args.args[0] == date(2026, 10, 21)

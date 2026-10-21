"""Tests for meal plans: prompts, AI answers, product matching and sending."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.middagsro import mealplan as mp
from custom_components.middagsro.api import Offer, RemaError
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.storage import clean_settings
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


def test_recipe_prompt_with_the_dish_items() -> None:
    """With the overview's items for the dish, only those are in the recipe prompt."""
    plan = make_plan(start="2026-10-12")
    plan["shopping"][0]["product"] = {"name": "HK. OKSEKØD 8-12%"}
    plan["shopping"][1]["avis_item"] = {"name": "Persille"}
    day = {**plan["days"][0], "uses": ["hakket oksekød", "Persille"]}
    prompt = mp.build_recipe_prompt(settings=clean_settings({}), day=day, plan=plan)
    assert "Rettens varer fra indkøbslisten" in prompt
    assert "Hakket oksekød (500 g) [købes som HK. OKSEKØD 8-12%], Persille (1 bundt)." in prompt
    assert ", Spaghetti" not in prompt  # another dish's item
    assert "hakkede tomater på dåse" in prompt
    # Names the AI got wrong: the whole week's shopping, as before.
    other = mp.build_recipe_prompt(
        settings=clean_settings({}), day={**day, "uses": ["Kartofler"]}, plan=plan
    )
    assert "Ugens indkøb" in other


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


DISHES = ("Tacos", "Lasagne", "Risotto med svampe", "Pandekager", "Omelet", "Falafel", "Gullasch")


def ai_answer(
    dates: list[date], shopping: list[dict[str, Any]], dishes: tuple[str, ...] = DISHES
) -> dict[str, Any]:
    """An AI answer for a plan over some dates, keeping the family's rules.

    Leftover days (as many as the settings allow for that many days) are the
    third and the fifth, from the day before each.
    """
    leftovers = {2, 4}
    for _ in range(2 - min(2, (len(dates) - 1) // 2)):
        leftovers.remove(max(leftovers))
    days = []
    names = iter(dishes)
    for idx, day in enumerate(dates):
        leftover = idx in leftovers
        dish = days[-1]["dish"] if leftover else next(names)
        days.append(
            {
                "date": day.isoformat(),
                "dish": f"Rester af {dish[:1].lower()}{dish[1:]}" if leftover else dish,
                "type": "rester" if leftover else "normal",
                "uses_leftovers_from": dates[idx - 1].isoformat() if leftover else None,
                "makes_leftovers": idx + 1 in leftovers,
                "servings": "4",
                "active_minutes": 20,
                "total_minutes": "35",
                "uses": ["Spaghetti", 5, " "] if idx == 0 else "ikke en liste",
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
    "fixed_days": [],  # the fake answers don't know about rye-bread thursdays
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
            # Asked more often than there are answers: the last one again.
            answer = self.plans.pop(0) if len(self.plans) > 1 else self.plans[0]
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
    # The fake recipe uses 500 g of spaghetti in each of the four dishes: 2 kg, 5 packs.
    assert chosen["Spaghetti"]["packages"] == 5
    assert chosen["Løg"]["product"]["id"] == 50003  # not hvidløg
    assert chosen["Persille"]["product"] is None
    assert "fritekst" in chosen["Persille"]["note"]
    # Built on the (non-organic) broccoli offer: that broccoli, at the avis price.
    assert chosen["Broccoli"]["product"]["id"] == 50001
    assert chosen["Broccoli"]["price_source"] == "avis"
    assert chosen["Rugbrød"]["product"]["id"] == 70001
    assert chosen["Rugbrød"]["packages"] == 2
    assert len(plan["shopping"]) == 8
    assert plan["total"] == pytest.approx(80 + 38 + 13.95 + 110 + 8 + 20 + 36)
    assert plan["over_budget"] is False
    assert plan["checklist"] == [{"requirement": "Budget", "ok": True}]

    leftover = plan["days"][2]
    assert leftover["steps"][0]["text"] == "Varm resten af Lasagne op, og server den."
    assert leftover["ingredients"] == []
    cooked = plan["days"][0]
    assert cooked["ingredients"] == [{"name": "spaghetti", "amount": "500 g"}]
    assert cooked["steps"] == [
        {"text": "Kog pastaen.", "minutes": 10},
        {"text": "Server.", "minutes": 0},
    ]
    assert cooked["total_minutes"] == 30
    assert cooked["uses"] == ["Spaghetti"]
    assert plan["days"][1]["uses"] == []
    assert "hakkede tomater på dåse til kødsovs" in ai.prompts[0]

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


def _offer(heading: str, description: str | None = None, quantity: str | None = None) -> Offer:
    return Offer(id=heading, heading=heading, description=description, price=10, pre_price=None,
                 quantity=quantity, valid_from=None, valid_to=None)  # fmt: skip


@pytest.mark.parametrize(
    ("name", "underline", "organic", "heading", "description", "fits"),
    [
        # Real offers from REMA's avis and the products that were wrongly matched to them.
        ("NORSK RØGET LAKS", "50 GR. / REMA 1000", False, "REMA 1000 Laksefilet", "600 g", False),
        ("LAKSEFILET", "600 GR. / REMA 1000", False, "REMA 1000 Laksefilet", "600 g", True),
        ("ÆGGESTAND", "125 GR. / REMA 1000", False, "Æg", "Økologiske\n10 stk.", False),
        ("SKRABEÆG", "15 STK. / STR. S/M", False, "Æg", "Økologiske\n10 stk.", False),
        ("ØKOLOGISKE ÆG", "10 STK. / REMA 1000", True, "Æg", "Økologiske\n10 stk.", True),
        ("GRILLET MADBRØD", "600 GR. / REMA 1000", False, "Schulstad Det Gode brød",
         "350-950 g", False),
        ("SOLSIKKERUGBRØD", "950 GR. / SCHULSTAD, DG", False, "Schulstad Det Gode brød",
         "350-950 g", True),
        ("SOLSIKKERUGBRØD", "750 GR. / KOHBERG", False, "Schulstad Det Gode brød",
         "350-950 g", False),
        ("GULERØDDER", "1 KG. / DANMARK KL. 1", False, "Mini madspildsgulerødder", "500 g", False),
        ("HK. OKSEKØD 15-18%", "400 GR. / REMA 1000", False,
         "REMA 1000 Hakket dansk oksekød 8-12% eller ungkvæg i tern", "300-400 g", False),
        ("HK. OKSEKØD 8-12%", "400 GR. / REMA 1000", False,
         "REMA 1000 Hakket dansk oksekød 8-12% eller ungkvæg i tern", "300-400 g", True),
        ("BACONLEVERPOSTEJ", "200 GR. / TULIP", False,
         "REMA 1000 Frilandsgris Leverpostej eller krydderpaté", "250 g", False),
        ("LEVERPOSTEJ", "250 GR. / REMA 1000", False,
         "REMA 1000 salami, leverpostej eller Taga serrano", "60-250 g", True),
        ("EDAMAME BØNNER", "300 GR. / REMA 1000", False,
         "Peter Larsen eller Löfbergs kaffe eller hele bønner", "400 g", False),
        ("PEPSI MAX", "1.98 LTR. / 6 PK.", False, "Pepsi Max eller Faxe Kondi", "1,5 l", False),
        ("KLOVBORG 45+", "240 GR. / MELLEMLAGRET, SKIVER", False,
         "Arla Klovborg eller Cheasy skæreost", "467-747 g", False),
        ("PUCK", "200 GR. / HVID OST", False, "PUCK hvid ost", "200 g", True),
        ("KÆRGÅRDEN SMØRBAR", "200 GR. / LET", False, "Kærgården", "200 g", True),
        ("LØG", "1 KG. / DANMARK KL. 1", False, "Løg", "1 kg", True),
        ("RØDLØG", "500 GR. / HOLLAND", False, "Løg", "1 kg", False),
        ("PISKEFLØDE 36%", "0.25 LTR. / REMA 1000", False, "Karolines Køkken Piskefløde 36%",
         "250 ml", False),
        ("PISKEFLØDE 36%", "0.25 LTR. / KAROLINES KØKKEN", False,
         "Karolines Køkken Piskefløde 36%", "250 ml", True),
        ("LYSKÆDE", "1 STK. / 80 LED", False, "Lyskæde eller klyngelyskæde", None, True),
        ("ÆG", None, False, "Æg", "Økologiske eller konventionelle", True),
        ("ØKOLOGISKE ÆG", "8 STK. / REMA 1000", True, "Æg", "Økologiske\n10 stk.", False),
        ("ÆBLE JUICE", "1 LTR. / REMA 1000", False, "Æbler", "1 stk.", False),
        ("KØKKENRULLER", "484 GR. / REMA 1000 SOFT", False,
         "Lotus Premium Toiletpapir eller køkkenruller", None, False),
        ("SMOOTHIE MED HAVRE", "90 GR. / REMA 1000", False, "REMA 1000 Smoothie", "90 g", True),
        ("KLYNGELYSKÆDE", "1 STK. / 80 LED", False, "Lyskæde eller klyngelyskæde", None, True),
        ("POUSSIN", "500 GR. / FRANKRIG", False, "Fersk poussin", "500 g", True),
        # From the real avis for week 43.
        ("KÆRGÅRDEN SMØRBAR", "200 GR. / LET", False, "Kærgården",
         "Ved køb af flere end 6 stk. pr. variant pr. dag er prisen op til 24.95 pr. stk.\n200 g",
         True),
        ("KÆRGÅRDEN SMØRBAR", "200 GR. / LET", False, "Kærgården",
         "Ved køb af flere end 6 stk. pr. variant pr. dag er prisen op til 24.95 pr. stk.", False),
        ("HK. KYLLINGEKØD 7-10%", "400 GR. / REMA 1000", False,
         "REMA 1000 Hakket dansk kyllingekød, grise- og kalvekød, koteletter eller stegeflæsk",
         "400-500 g\nMax. 62.50 pr. kg", True),
        ("LAKSEFILET", "400 GR. / REMA 1000", False, "REMA 1000 Laksefilet",
         "600 g\nPartivare. 148.33 pr. kg", False),
        ("HAKKEBØFFER", "250 GR. / REMA 1000, BACON & GRØNT", False,
         "REMA 1000 Hakkebøffer eller kalvesticks med bacon", "Med 25% grønt 250-280 g", True),
        ("LASAGNEPLADER", "250 GR. / PASTA DI MARIA", False,
         "La Pasta di Maria Italiensk fettuccine naturel eller lasagneplader", "250-500 g", True),
        ("LEVERPOSTEJ", "500 GR. / REMA 1000", False,
         "REMA 1000 Frilandsgris Leverpostej eller krydderpaté", "200-250 g", False),
        # Real descriptions also hold limits: "Max. 6 stk." is no size.
        ("PEPSI MAX", "1.98 LTR. / 6 PK.", False, "Pepsi Max eller Faxe Kondi",
         "Max. 6 stk. pr. kunde\n1,5 l", False),
        ("KÆRGÅRDEN SMØRBAR", "200 GR. / LET", False, "Kærgården", "Max. 6 stk.\n200 g", True),
        ("ØKOLOGISKE ÆG", "10 STK. / REMA 1000", True, "Æg", "Økologiske 10 stk.\nMax 4 stk.",
         True),
        ("1,5% FEDT", None, False, "Letmælk 1,5%", None, False),
    ],
)  # fmt: skip
def test_avis_match(
    name: str, underline: str, organic: bool, heading: str, description: str | None, fits: bool
) -> None:
    """Only the very product an avis offer is for gets its price."""
    assert mp.avis_match(name, underline, organic, _offer(heading, description)) is fits


def test_offer_query_and_short_words() -> None:
    """The offer's own part is searched for; 'æg' is not 'æggestand'."""
    heading = "REMA 1000 salami, leverpostej eller Taga serrano"
    assert mp.offer_query(_offer(heading), "Leverpostej") == "leverpostej"
    assert mp.offer_query(_offer("REMA 1000 Laksefilet"), "Laks") == "Laksefilet"
    assert mp.name_fit(["æg"], "ÆGGESTAND")[0] == 0
    assert mp.name_fit(["æg"], "SKRABEÆG")[0] == 1
    assert mp.name_fit(["laks"], "LAKSEFILET")[0] == 1
    assert mp.name_fit(["laks"], "VARMRØGET LAKS")[1] > 5
    assert mp.name_fit(["laks"], "GRAVAD LAKS")[1] > 5


async def test_offer_line_gets_the_offer_product(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A line built on an offer gets that offer's product, or a normal match."""
    planner = init_integration.runtime_data.planner
    eggs: dict[str, Any] = {"name": "Æg", "search": "æg", "amount": 10, "unit": "stk"}
    await planner._async_match(eggs, None, _offer("Æg", "Økologiske\n10 stk."))
    assert eggs["product"]["name"] == "ØKOLOGISKE ÆG"  # the offer, not the cheaper frilandsæg

    # The offer is for something REMA doesn't have under that name: a normal match.
    onions: dict[str, Any] = {"name": "Løg", "search": "løg", "amount": 1, "unit": "kg"}
    await planner._async_match(onions, None, _offer("Mini madspildsgulerødder", "500 g"))
    assert onions["product"]["name"] == "LØG"

    # Tjek's product ids decide, and those products are fetched directly.
    salmon = make_product(440047, "LAKSEFILET", 69.95, underline="400 GR. / REMA 1000")
    mock_client.async_get_products.return_value = [salmon]
    fish: dict[str, Any] = {"name": "Laksefilet", "search": "laks", "amount": 400, "unit": "g"}
    offer = replace(_offer("REMA 1000 Laksefilet", "600 g"), product_ids=(440047,))
    await planner._async_match(fish, None, offer)
    assert fish["product"]["name"] == "LAKSEFILET"
    planner._avis_price(fish, offer)
    assert fish["price_source"] == "avis"
    mock_client.async_get_products.side_effect = RemaError("down")
    gone: dict[str, Any] = {"name": "Æg", "search": "æg", "amount": 10, "unit": "stk"}
    await planner._async_match(gone, None, replace(_offer("Æg"), product_ids=(40003,)))
    assert gone["product"]["name"] == "ØKOLOGISKE ÆG"  # found by searching instead
    mock_client.async_get_products.side_effect = None

    # Searched as "laks" but called "Laksefilet": the fillet, not the cheaper pastry.
    pastry = make_product(42980, "INDBAGT LAKS", 17.95, underline="250 GR. / REMA 1000")
    mock_client.async_search_products.side_effect = None
    mock_client.async_search_products.return_value = [pastry, salmon]
    line_fish: dict[str, Any] = {"name": "REMA 1000 Laksefilet", "search": "laks",
                                 "amount": 1200, "unit": "g"}  # fmt: skip
    await planner._async_match(line_fish)
    assert line_fish["product"]["name"] == "LAKSEFILET"

    # The AI put kebab on the frikadeller offer: no frikadeller for kebab.
    meatballs = make_product(45042, "FRIKADELLER", 25.0, underline="360 GR. / FRILANDSGRIS")
    mock_client.async_get_products.return_value = [meatballs]
    mock_client.async_search_products.return_value = [meatballs]
    kebab: dict[str, Any] = {"name": "Kyllingekebab", "search": "kyllingekebab",
                             "amount": 400, "unit": "g"}  # fmt: skip
    gyros = replace(_offer("REMA 1000 Frilandsgris Frikadeller eller gyros"), product_ids=(45042,))
    await planner._async_match(kebab, None, gyros)
    assert kebab["product"] is None

    # Same price for every bread on the offer: the biggest one.
    small = make_product(60152, "RUGBRØDSSANDWICH", 15.0, underline="480 GR. / SCHULSTAD, DG")
    big = make_product(60033, "SOLSIKKERUGBRØD", 15.0, underline="950 GR. / SCHULSTAD, DG")
    mock_client.async_search_products.return_value = [small, big]
    bread: dict[str, Any] = {"name": "Rugbrød", "search": "rugbrød", "amount": 2, "unit": "pk"}
    await planner._async_match(bread)
    assert bread["product"]["name"] == "SOLSIKKERUGBRØD"

    # 3 kg potatoes are not one sweet potato sold per piece.
    sweet = make_product(1, "SØDE KARTOFLER", 5.0, underline="1 STK.")
    potatoes = make_product(2, "KARTOFLER", 20.0, underline="2 KG / DANMARK")

    async def search(query: str, limit: int = 24, at: datetime | None = None) -> list[Any]:
        return [sweet, potatoes]

    mock_client.async_search_products.side_effect = search
    line: dict[str, Any] = {"name": "Kartofler", "search": "kartofler", "amount": 3, "unit": "kg"}
    await planner._async_match(line)
    assert (line["product"]["name"], line["packages"]) == ("KARTOFLER", 2)


async def test_avis_price_until_rema_has_it(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A line built on an avis offer gets the avis price while REMA shows the normal one."""
    planner = init_integration.runtime_data.planner
    onions = Offer(id="o", heading="Løg", description="Danske 1 kg", price=5, pre_price=None,
                   quantity="1 kg", valid_from=None, valid_to=None)  # fmt: skip
    line: dict[str, Any] = {"name": "Løg", "search": "løg", "amount": 2, "unit": "stk"}
    await planner._async_match(line)
    assert line["product"]["price"] == 8.0
    planner._avis_price(line, onions)
    assert (line["product"]["price"], line["product"]["normal_price"]) == (5, 8.0)
    assert line["product"]["is_advertised"]
    assert line["cost"] == 5
    assert line["price_source"] == "avis"

    # Not for organic products when the offer isn't organic, another product,
    # a product REMA already has on offer, or when REMA is cheaper anyway.
    for name, extra in (
        ("ØKO. BROCCOLI", {"is_organic": True}),
        ("SPAGHETTI", {}),
        ("LØG", {"is_advertised": True, "price": 5}),
        ("LØG", {"price": 4}),
    ):
        other: dict[str, Any] = {"packages": 1, "cost": 9,
                                 "product": {"name": name, "price": 9, **extra}}  # fmt: skip
        planner._avis_price(other, onions)
        assert "price_source" not in other, name
    organic = Offer(id="o", heading="Broccoli", description="Økologisk", price=5, pre_price=None,
                    quantity=None, valid_from=None, valid_to=None)  # fmt: skip
    eco: dict[str, Any] = {"packages": 1, "cost": 14,
                           "product": {"name": "ØKO. BROCCOLI", "price": 14, "is_organic": True}}  # fmt: skip
    planner._avis_price(eco, organic)
    assert eco["price_source"] == "avis"
    planner._avis_price({"product": None}, onions)
    planner._avis_price(line, None)


async def test_send_parts(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """The shopping day's items and the late-week items are sent separately."""
    store = init_integration.runtime_data.store
    plan = make_plan("parts", start="2026-10-18")
    plan["shopping"][2]["buy_from"] = "2026-10-22"  # spaghetti on thursday
    await store.async_add_plan(plan)
    planner = init_integration.runtime_data.planner

    def sent() -> list[str | int]:
        return [c.kwargs.get("name") or c.kwargs.get("product_id")
                for c in mock_client.async_add_to_list.call_args_list]  # fmt: skip

    await planner.async_send("parts")
    assert sent() == [30001, "Persille (1 bundt)"]
    assert plan["status"] == "sent"
    assert "late_sent_at" not in plan

    mock_client.async_add_to_list.reset_mock()
    await planner.async_send("parts", "late")
    assert sent() == ["Spaghetti"]
    assert plan["late_sent_at"]

    # Everything is sent: sending again adds nothing twice.
    mock_client.async_add_to_list.reset_mock()
    await planner.async_send("parts", "all")
    assert sent() == []
    # The last basket put back (the late one) is sent again.
    await planner.async_restore_sent("parts")
    await planner.async_send("parts", "all")
    assert sent() == ["Spaghetti"]

    # Nothing to send: nothing is added.
    plan["shopping"] = [line for line in plan["shopping"] if not line.get("buy_from")]
    mock_client.async_add_to_list.reset_mock()
    await planner.async_send("parts", "late")
    assert sent() == []


async def test_generate_over_budget_tries_again(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str, freezer: Any
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
    # send=True: sent when REMA has next week's products, 02:00 on the first day.
    assert plan["status"] == "draft"
    assert plan["send_at"] == "2026-10-18T00:05:00+00:00"
    freezer.move_to(datetime(2026, 10, 18, 0, 6, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert plan["status"] == "sent"
    assert "send_at" not in plan


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


async def test_only_weeks_with_an_avis(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str, freezer: Any
) -> None:
    """A plan can't start after the last avis that is out, nor run past it."""
    planner = init_integration.runtime_data.planner
    planner._get_catalogs = lambda: (CURRENT, None)  # next week's avis isn't out
    freezer.move_to(datetime(2026, 10, 12, 15, tzinfo=UTC))  # monday in week 42
    assert planner.default_start() == date(2026, 10, 12)  # the rest of this week
    assert planner.avis_end(date(2026, 10, 12)) == date(2026, 10, 17)
    with pytest.raises(ServiceValidationError) as err:
        planner.async_start_generation(date(2026, 10, 18))
    assert err.value.translation_key == "avis_not_out"
    assert err.value.translation_placeholders == {"date": "18/10", "last": "17/10"}
    assert planner.avis_end(date(2026, 10, 1)) is None  # before every avis: as before

    dates = mp.plan_dates(date(2026, 10, 15), 7)[:3]
    ai = FakeAI(ai_answer(dates, []))
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        plan = await planner.async_generate(date(2026, 10, 15))
    assert [d["date"] for d in plan["days"]] == ["2026-10-15", "2026-10-16", "2026-10-17"]

    # Out: next week is the default again, and a plan may run into it.
    planner._get_catalogs = lambda: (CURRENT, UPCOMING)
    assert planner.default_start() == date(2026, 10, 18)
    assert planner.avis_end(date(2026, 10, 15)) is None
    assert planner.avis_end(date(2026, 10, 20)) == date(2026, 10, 24)
    planner._get_catalogs = lambda: (None, None)
    assert planner.avis_end(date(2027, 1, 3)) is None


async def test_generation_guards(
    hass: HomeAssistant, init_integration: MockConfigEntry, freezer: Any
) -> None:
    """No AI, everything skipped or already running."""
    freezer.move_to(datetime(2026, 10, 14, 10, tzinfo=UTC))
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

    # A product REMA no longer has (a recipe's): the line's name finds one instead.
    line = {"name": "Rugbrød", "search": "Rugbrød", "amount": 1, "must_have": False,
            "product_id": 12345}  # fmt: skip
    await planner._async_match(line)
    assert line["product"]["id"] == 70001


async def test_candidates_edge_cases(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Unpriced products, neutral words and nothing called what was searched."""
    planner = init_integration.runtime_data.planner
    unpriced = make_product(1, "MÆLK", None)
    assert planner._candidates({}, [unpriced], "mælk") == ([], {})
    assert planner._candidates({}, CATALOGUE, "dansk rema") == ([], {})
    assert planner._candidates({}, CATALOGUE[:1], "laks")[0] == []


async def test_send_empties_the_basket(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Sent items leave the family's list; only new ones are sent next; the last can be put back."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = make_plan("basket", start="2026-10-18")
    await store.async_add_plan(plan)
    await planner.async_send("basket")
    assert all(line.get("sent") for line in plan["shopping"])
    first = plan["last_sent"]
    assert len(first["ids"]) == 3

    extra = {**plan["shopping"][1], "id": "extra", "name": "Basilikum"}
    extra.pop("sent")
    plan["shopping"].append(extra)
    mock_client.async_add_to_list.reset_mock()
    await planner.async_send("basket")
    assert [c.kwargs.get("name") for c in mock_client.async_add_to_list.call_args_list] == [
        "Basilikum (1 bundt)"
    ]
    assert plan["last_sent"]["ids"] == ["extra"]

    await planner.async_restore_sent("basket")
    assert [line["id"] for line in plan["shopping"] if not line.get("sent")] == ["extra"]
    assert "last_sent" not in plan
    with pytest.raises(ServiceValidationError) as err:
        await planner.async_restore_sent("basket")
    assert err.value.translation_key == "nothing_to_restore"
    with pytest.raises(ServiceValidationError) as err:
        await planner.async_restore_sent("findes-ikke")
    assert err.value.translation_key == "plan_not_found"
    store.plans.clear()
    with pytest.raises(ServiceValidationError) as err:
        await planner.async_restore_sent()
    assert err.value.translation_key == "no_plan"


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


LAKS = Offer(
    id="laks",
    heading="REMA 1000 Laksefilet",
    description="600 g\nPartivare. 148.33 pr. kg",
    price=89,
    pre_price=None,
    quantity="600 g",
    valid_from="2026-10-17T22:00:00+0000",
    valid_to="2026-10-24T21:59:59+0000",
    product_ids=(440095,),
    product_names=("REMA 1000 laksefilet 600g",),
)


async def test_avis_item_rema_does_not_have_yet(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, freezer: Any
) -> None:
    """An offer whose product REMA doesn't have: the avis's name and price.

    From the real avis for week 43: Tjek says the salmon offer is REMA's product
    440095, which REMA's webshop doesn't have (yet), and the webshop puts it on
    the list as free text. Before, the plan got 3 x 225 g salmon at the normal
    price instead of 600 g at 89 kr.
    """
    planner = init_integration.runtime_data.planner
    mock_client.async_get_products.return_value = []
    fish: dict[str, Any] = {"name": "Laksefilet", "search": "laks", "amount": 1200, "unit": "g"}
    await planner._async_match(fish, None, LAKS)
    assert fish["product"] is None
    assert fish["avis_item"] == {
        "name": "REMA 1000 laksefilet 600g",
        "underline": "600 g",
        "price": 89,
        "is_advertised": True,
        "product_ids": [440095],
    }
    assert (fish["packages"], fish["cost"], fish["price_source"]) == (2, 178, "avis")
    assert "vælges, når listen sendes" in fish["note"]
    planner._avis_price(fish, LAKS)  # no product: nothing to change
    assert fish["cost"] == 178

    # Once the offer runs and REMA still doesn't have it: a partivare.
    freezer.move_to(datetime(2026, 10, 18, 8, tzinfo=UTC))
    await planner._async_match(fish, None, LAKS)
    assert fish["note"] == "Partivare – kun i butikken, tilføjes som fritekst"

    # Several products and no price: the part of the offer the line is about.
    snack = replace(
        LAKS,
        heading="Pizza snack",
        description="Frost 120 g",
        price=None,
        quantity="120 g",
        valid_from=None,
        product_ids=(42689, 42690),
        product_names=("Pizza snack Salami", "Pizza Snack Margherita"),
    )
    pizza: dict[str, Any] = {"name": "Pizza snack", "search": "pizza snack", "amount": 4,
                             "unit": "stk"}  # fmt: skip
    await planner._async_match(pizza, None, snack)
    assert pizza["avis_item"]["name"] == "Pizza snack (tilbud)"
    assert (pizza["packages"], pizza["cost"]) == (4, None)

    # Not what the line asks for: no avis item (no meatballs for kebab).
    gyros = replace(LAKS, heading="REMA 1000 Frikadeller eller gyros", product_names=("GYROS",))
    kebab: dict[str, Any] = {"name": "Kyllingekebab", "search": "kyllingekebab", "amount": 400,
                             "unit": "g"}  # fmt: skip
    await planner._async_match(kebab, None, gyros)
    assert kebab["avis_item"] is None

    # Tjek lists products without REMA's id too: searched for by name instead.
    unlinked = replace(LAKS, unlinked=True)
    other: dict[str, Any] = {"name": "Laksefilet", "search": "laks", "amount": 600, "unit": "g"}
    await planner._async_match(other, None, unlinked)
    assert other["avis_item"] is None


def test_avis_packages() -> None:
    """How many of an avis item cover an amount."""
    assert mp.avis_packages(None, None, LAKS) == 1
    assert mp.avis_packages(1, "bundt", LAKS) == 1
    assert mp.avis_packages(3, "pk", LAKS) == 3
    assert mp.avis_packages(1.2, "kg", LAKS) == 2
    assert mp.avis_packages(1, "l", LAKS) == 1  # no size of that kind
    assert mp.avis_packages(3, "stk", LAKS) == 3


async def test_avis_item_sent_as_rema_product(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """When the list is sent, an avis item is looked up again: REMA's product if it has it."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = make_plan("avis", start="2026-10-18")
    fish = {
        "name": "Laksefilet",
        "amount": 1200.0,
        "unit": "g",
        "search": "laks",
        "category": "Fisk",
        "offer": "o1",
        "product": None,
        "avis_item": {"name": "REMA 1000 laksefilet 600g", "price": 89, "product_ids": [440095]},
        "packages": 2,
        "cost": 178,
        "note": "Avisvare",
    }
    plan["shopping"] = [fish]
    await store.async_add_plan(plan)

    def sent() -> list[tuple[str | int, int]]:
        fish.pop("sent", None)  # sent before: put back for the next try
        return [(c.kwargs.get("name") or c.kwargs.get("product_id"), c.kwargs["amount"])
                for c in mock_client.async_add_to_list.call_args_list]  # fmt: skip

    # REMA doesn't have it (a partivare): free text, as the webshop does.
    mock_client.async_get_products.return_value = []
    await planner.async_send("avis")
    assert sent() == [("REMA 1000 laksefilet 600g", 2)]

    # REMA can't be reached, or has something else under that id: free text too.
    for answer in (RemaError("down"), [make_product(440095, "VASKEMIDDEL", 20.0)]):
        mock_client.async_add_to_list.reset_mock()
        mock_client.async_get_products.side_effect = (
            answer if isinstance(answer, Exception) else None
        )
        mock_client.async_get_products.return_value = answer
        await planner.async_send("avis")
        assert sent() == [("REMA 1000 laksefilet 600g", 2)]
    mock_client.async_get_products.side_effect = None

    # From 02:00 on the first day REMA has it: that product, at REMA's price.
    salmon = make_product(440095, "LAKSEFILET", 89.0, underline="600 GR. / REMA 1000")
    mock_client.async_get_products.return_value = [salmon]
    mock_client.async_add_to_list.reset_mock()
    await planner.async_send("avis")
    assert sent() == [(440095, 2)]
    assert fish["product"]["name"] == "LAKSEFILET"
    assert fish["note"] is None
    assert "price_source" not in fish
    assert plan["total"] == 178


async def test_automatic_sends_wait_for_rema(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, freezer: Any
) -> None:
    """Automatic sends wait for 02:00 on the shopping day, also over a restart."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = make_plan("wait", start="2026-10-18")
    plan["shopping"][2]["buy_from"] = "2026-10-22"  # spaghetti on thursday
    await store.async_add_plan(plan)

    await planner._async_send_when_ready(plan)
    assert plan["send_at"] == "2026-10-18T00:05:00+00:00"
    assert plan["late_send_at"] == "2026-10-22T00:05:00+00:00"
    assert len(planner._sends) == 2

    # After a restart the waiting sends are scheduled again.
    planner.async_cancel()
    assert planner._sends == {}
    old = make_plan("old", start="2026-10-01")
    old["send_at"] = "2026-10-01T00:05:00+00:00"
    gone = make_plan("gone", start="2026-10-18")
    gone["send_at"] = "2026-10-18T00:05:00+00:00"
    await store.async_add_plan(old)
    await store.async_add_plan(gone)
    store.plans.append({**make_plan("bare", start="2026-10-18"), "send_at": "not a time"})
    planner.async_restore_sends()
    assert "send_at" not in old  # that week is over
    assert set(planner._sends) == {("wait", "send_at"), ("wait", "late_send_at"),
                                   ("gone", "send_at")}  # fmt: skip
    await store.async_delete_plan("gone")  # deleted meanwhile: nothing is sent

    freezer.move_to(datetime(2026, 10, 18, 0, 6, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert plan["status"] == "sent"
    assert "send_at" not in plan
    assert "late_sent_at" not in plan

    # REMA fails on thursday: logged, and the plan isn't marked as sent.
    mock_client.async_get_primary_list.side_effect = RemaError("down")
    freezer.move_to(datetime(2026, 10, 22, 0, 6, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "late_sent_at" not in plan
    assert planner._sends == {}

    # A plan for a week that has started is sent right away.
    mock_client.async_get_primary_list.side_effect = None
    now = make_plan("now", start="2026-10-20")
    await store.async_add_plan(now)
    await planner._async_send_when_ready(now)
    assert now["status"] == "sent"


async def test_send_must_haves_once(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """With the option, must-haves on the REMA list already (not bought) are not sent again."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner

    def must(name: str, product: dict[str, Any] | None) -> dict[str, Any]:
        return {"name": name, "amount": 1.0, "unit": "pk", "search": name, "category": "Faste varer",
                "offer": None, "must_have": True, "product_id": product and product["id"],
                "product": product, "packages": 1, "cost": None, "note": None}  # fmt: skip

    def plan_with_musts(plan_id: str) -> dict[str, Any]:
        plan = make_plan(plan_id, start="2026-10-18")
        plan["shopping"] += [
            must("Letmælk", {"id": 20494, "name": "LETMÆLK 1,5% FEDT", "underline": "1 LTR."}),
            must("Rugbrød", {"id": 70001, "name": "RUGBRØD", "underline": "1 KG."}),  # bought
            must("Kage til Anna", None),
        ]
        return plan

    def sent() -> list[Any]:
        return [
            c.kwargs.get("product_id") or c.kwargs.get("name")
            for c in mock_client.async_add_to_list.call_args_list
        ]

    # Off (the default): everything is sent.
    plan = plan_with_musts("off")
    await store.async_add_plan(plan)
    await planner.async_send("off")
    assert sent() == [30001, "Persille (1 bundt)", "Spaghetti", 20494, 70001, "Kage til Anna"]

    await store.async_set_settings({**store.settings, "must_haves_once": True})
    assert store.settings["must_haves_once"] is True
    mock_client.async_add_to_list.reset_mock()
    plan = plan_with_musts("on")
    await store.async_add_plan(plan)
    await planner.async_send("on")
    assert sent() == [30001, "Persille (1 bundt)", "Spaghetti", 70001]
    assert [line["name"] for line in plan["shopping"] if line.get("on_list")] == [
        "Letmælk",
        "Kage til Anna",
    ]
    assert all(line.get("sent") for line in plan["shopping"])
    await planner.async_restore_sent("on")
    assert not any(line.get("on_list") for line in plan["shopping"])

    # The REMA list can't be read: everything is sent.
    mock_client.async_add_to_list.reset_mock()
    real = mock_client.async_get_primary_list.return_value
    calls: list[int] = []

    async def first_fails() -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise RemaError("down")
        return real

    mock_client.async_get_primary_list.side_effect = first_fails
    await planner.async_send("on")
    assert len(sent()) == 6

    # No must-haves to send: the list isn't read for them.
    mock_client.async_get_primary_list.side_effect = None
    mock_client.async_get_primary_list.reset_mock()
    plan = make_plan("plain", start="2026-10-18")
    await store.async_add_plan(plan)
    await planner.async_send("plain")
    assert mock_client.async_get_primary_list.call_count == 2  # to add the items and refresh


async def test_send_keeps_what_got_there(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """REMA fails halfway: the items that got on the list stay sent, the rest is sent next time."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = make_plan("half", start="2026-10-18")
    await store.async_add_plan(plan)
    calls = 0

    async def add(shopping_list: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RemaError("REMA faldt ud")

    mock_client.async_add_to_list.side_effect = add
    with pytest.raises(RemaError):
        await planner.async_send("half")
    sent = [line["name"] for line in plan["shopping"] if line.get("sent")]
    assert sent == ["Hakket oksekød"]
    assert plan["last_sent"]["ids"] == [plan["shopping"][0]["id"]]
    assert plan["status"] == "draft"

    mock_client.async_add_to_list.side_effect = None
    mock_client.async_add_to_list.reset_mock()
    await planner.async_send("half")
    assert [c.kwargs.get("name") for c in mock_client.async_add_to_list.call_args_list] == [
        "Persille (1 bundt)",
        "Spaghetti",
    ]
    assert all(line.get("sent") for line in plan["shopping"])
    assert plan["status"] == "sent"

    # One send at a time: a second send while one runs waits, then has nothing to do.
    plan2 = make_plan("two", start="2026-10-18")
    await store.async_add_plan(plan2)
    started = asyncio.Event()

    async def slow(shopping_list: Any, **kwargs: Any) -> None:
        started.set()
        await asyncio.sleep(0)

    mock_client.async_add_to_list.side_effect = slow
    mock_client.async_add_to_list.reset_mock()
    first = asyncio.create_task(planner.async_send("two"))
    await started.wait()
    await planner.async_send("two")
    await first
    assert mock_client.async_add_to_list.call_count == 3

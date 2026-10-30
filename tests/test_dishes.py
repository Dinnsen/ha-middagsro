"""Tests for what counts as the same dish, the plan check, and the repairs built on them."""

from __future__ import annotations

from datetime import date
import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import dishes as ds, mealplan as mp, recipes as rc
from homeassistant.core import HomeAssistant

from .conftest import make_plan, make_product
from .test_mealplan import SETTINGS, SHOPPING, START, FakeAI, _generate, ai_answer

LAKS = "Ovnbagt laks med fettuccine spinat pasta, pesto og kogt frisk broccoli."
DISHES_NO_LASAGNE = ("Lasagne", "Risotto med svampe", "Pandekager", "Omelet", "Falafel")


def test_dish_key_and_same_dish() -> None:
    """The main dish decides; sides, cooking and leftovers don't."""
    assert ds.dish_key("Ovnbagt laks med pasta og broccoli") == {"laks"}
    assert ds.dish_key("Rester af spaghetti bolognese") == {"spaghetti", "bolognes"}
    assert ds.dish_key("Italiensk minipizza med salat") == {"minipizza", "pizza"}
    assert ds.dish_key("Hokkaido-suppe med brød") == {"hokkaido", "supp"}
    assert ds.dish_key("Ikke hjemme") == frozenset()
    assert ds.dish_key("Med") == frozenset()
    assert ds.dish_key("Nem og hurtig") == {"nem", "hurtig"}  # only the whole name is left
    assert ds.same_dish("Fiskefrikadeller", "Frikadeller", strict=True)
    assert not ds.same_dish("Frikadeller", "Fiskefrikadeller", strict=True)
    assert not ds.same_dish("Kyllingefrikadeller", "Fiskefrikadeller", strict=True)
    assert ds.same_dish("Kyllingefrikadeller", "Fiskefrikadeller")
    assert ds.same_dish("Ovnbagt laks med pasta og broccoli", LAKS)
    assert ds.same_dish("Kyllingefrikadeller med ovnbagte kartofler og gnavegrønt",
                        "Kyllinge- eller okse/svinefrikadeller med ovnbagte kartofler")  # fmt: skip
    assert ds.same_dish("Pitabrød med kebab og grøntsager", "Pitabrød med kebab eller tun")
    assert ds.same_dish("Italiensk minipizza", "Surdejspizza med tomatsalat")
    assert ds.same_dish("Lasagne", "Lasagne med salat")
    assert not ds.same_dish("Cæsarsalat med kylling", "Pasta med kylling og pesto")
    assert not ds.same_dish("Pasta med kylling", "Kyllingewok med nudler")
    assert not ds.same_dish("Ikke hjemme", "Ikke hjemme")
    assert ds.matches_any("Laks med ris", ["Tacos", LAKS]) == LAKS
    assert ds.matches_any("Tacos", []) is None
    assert ds.in_text("Ovnbagt laks med pasta", "Onsdag: laks med frisk spinat pasta og broccoli")
    assert not ds.in_text("Lasagne", "Onsdag: laks")
    assert not ds.in_text("Lasagne", "")


def test_household_portions() -> None:
    """Children count for less, the youngest the least."""
    household = [
        {"role": "adult", "age": 38},
        {"role": "adult", "age": 39},
        {"role": "child", "age": 10},
        {"role": "child", "age": 3},
        {"role": "child", "age": 14},
        {"role": "child"},
    ]
    assert ds.household_portions({"household": household}) == 4.9
    assert ds.household_portions({"household": []}) == 2.0


def _day(iso: str, dish: str, **extra: Any) -> dict[str, Any]:
    when = date.fromisoformat(iso)
    return {
        "date": iso,
        "weekday": mp.WEEKDAYS_DA[when.weekday()],
        "dish": dish,
        "type": "normal",
        "favorite_id": None,
        "uses_leftovers_from": None,
        "makes_leftovers": False,
        "active_minutes": 20,
        **extra,
    }


def test_check_plan() -> None:
    """Every rule the family set is checked, with an understandable line for each."""
    settings = {"leftover_days": 1, "min_vegetarian": 1, "max_vegetarian": 1,
                "max_cook_minutes_weekday": 30}  # fmt: skip
    plan = {
        "days": [
            _day("2026-10-25", "Ovnbagt laks med pasta", makes_leftovers=True),
            _day("2026-10-26", "Rester af laks", type="rester", uses_leftovers_from="2026-10-25"),
            _day("2026-10-27", "Lasagne", favorite_id="due"),
            _day("2026-10-28", "Kyllingefrikadeller", active_minutes=45),
            _day("2026-10-29", "Rester", type="fast", uses_leftovers_from="2026-10-28"),
            _day("2026-10-30", "Frikadeller med kartofler"),
            _day("2026-10-31", "Fiskefrikadeller", type="vegetar"),
        ]
    }
    problems = ds.check_plan(
        plan,
        settings,
        recent=["Laks med ris", "Lasagne med salat"],
        due_ids={"due"},
        note="",
        disliked=["Fiskefrikadeller med remoulade"],
    )
    assert problems == [
        'søndag 2026-10-25: "Ovnbagt laks med pasta" gentager "Laks med ris" fra de seneste uger '
        "– vælg en helt anden hovedret",
        # Kyllingefrikadeller are not the disliked fiskefrikadeller ...
        'lørdag 2026-10-31: "Fiskefrikadeller" er en variant af "Fiskefrikadeller med remoulade", '
        "som familien ikke kan lide",
        # ... but frikadeller twice in a week is the same dish twice.
        'fredag 2026-10-30: "Frikadeller med kartofler" er samme ret som "Kyllingefrikadeller" '
        "tidligere på ugen",
        'lørdag 2026-10-31: "Fiskefrikadeller" er samme ret som "Kyllingefrikadeller" tidligere '
        "på ugen",
        'onsdag 2026-10-28: "Kyllingefrikadeller" tager 45 minutters aktiv tilberedning; højst 30 '
        "på hverdage",
    ]
    # The note asked for the salmon; the leftovers must come from a double portion.
    plan["days"][0]["makes_leftovers"] = False
    plan["days"][6]["type"] = "normal"
    problems = ds.check_plan(
        plan, {**settings, "leftover_days": 2}, recent=["Laks"], due_ids=set(), note="søndag laks"
    )
    assert not any("gentager" in p for p in problems)
    assert (
        'Der er 1 restedage, men der skal være præcis 2 (type "rester" med uses_leftovers_from)'
        in problems
    )
    assert (
        "mandag 2026-10-26: rester af 2026-10-25, men den dag laver ikke dobbelt portion "
        "(makes_leftovers)"
    ) in problems
    assert "Kun 0 vegetarretter; der skal være mindst 1" in problems
    plan["days"][0]["type"] = plan["days"][2]["type"] = "vegetar"
    problems = ds.check_plan(plan, settings, recent=[], due_ids=set())
    assert "2 vegetarretter; der må højst være 1" in problems
    # Fixed days: thursday is leftovers (one of the two leftover days), saturday pizza.
    fixed = {
        **settings,
        "leftover_days": 2,
        "fixed_days": [
            {"weekday": 3, "text": "Rester"},
            {"weekday": 5, "text": "Pizza fra Netto"},
            {"weekday": 6, "text": "Ikke hjemme"},
        ],
    }
    plan["days"][4]["type"] = "rester"
    problems = ds.check_plan(plan, fixed, recent=[], due_ids=set())
    assert not any("restedage" in p for p in problems)
    # Two leftover days with thursday fixed: monday and thursday, not a third one.
    problems = ds.check_plan(plan, {**fixed, "leftover_days": 1}, recent=[], due_ids=set())
    assert "Der er 2 restedage, men der skal være præcis 1 (de faste restedage tæller med)" in (
        problems
    )
    # Fewer leftover days than fixed ones: the fixed day is still leftovers.
    plan["days"][1].update(type="normal", uses_leftovers_from=None, dish="Tacos")
    problems = ds.check_plan(plan, {**fixed, "leftover_days": 0}, recent=[], due_ids=set())
    assert not any("restedage" in p for p in problems)
    # The family's fixed leftovers day may be on a day they otherwise keep free of leftovers.
    problems = ds.check_plan(
        plan, {**fixed, "leftover_days": 1, "no_leftover_weekdays": ["3"]}, recent=[], due_ids=set()
    )
    assert not any("vil ikke have rester" in p for p in problems)
    plan["days"][1].update(type="rester", uses_leftovers_from="2026-10-25", dish="Rester af laks")
    assert (
        'lørdag 2026-10-31: skal være "Pizza fra Netto" (fast dag), ikke "Fiskefrikadeller"'
        in problems
    )
    plan["days"][4]["uses_leftovers_from"] = None
    problems = ds.check_plan(plan, fixed, recent=[], due_ids=set())
    assert not any("torsdag" in p for p in problems)  # still called "Rester"
    plan["days"][4]["dish"] = "Pandekager"
    plan["days"][6]["dish"] = "Minipizza"
    problems = ds.check_plan(plan, fixed, recent=[], due_ids=set())
    assert 'torsdag 2026-10-29: skal være rester (Rester), ikke "Pandekager"' in problems
    assert not any("Minipizza" in p for p in problems)


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """The family's settings, a plan they cooked, their favourites and their salmon recipe."""
    cooked = make_plan("cooked", start="2026-10-11")
    cooked["days"][0]["dish"] = "Ovnbagt laks med pasta"
    cooked["days"][1]["dish"] = "Rester af laks"
    cooked["sent_at"] = "2026-10-10T10:00:00+02:00"
    draft = make_plan("draft", start="2026-10-11")
    draft["days"][2]["dish"] = "Pandekager"
    return {
        "settings": {**SETTINGS, "no_repeat_weeks": 3, "must_haves": [], "pantry": "salt, olie"},
        "plans": [draft, cooked],
        "favorites": [
            {"id": "laks", "text": LAKS, "frequency": "inspiration", "last_used": None},
            {"id": "lasagne", "text": "Lasagne", "frequency": "weekly", "last_used": None},
        ],
        "recipes": [
            rc.clean_recipe(
                {
                    "name": "Lasagne med salat",
                    "rating": "like",
                    "favorite": True,
                    "servings": 4,
                    "ingredients": [
                        {"name": "hakket oksekød", "amount": "500 g",
                         "product": {"id": 30001, "name": "HK. OKSEKØD 8-12%", "underline": "500 GR."}},
                        "2 løg",
                        "1 glas pesto",
                        {"name": "lasagneplader", "amount": "250 g"},
                        "salt og olie",
                        {"name": "revet ost", "amount": "", "basic": True},
                    ],
                    "steps": ["Lav kødsovsen.", "Bag lasagnen."],
                }
            )
            | {"id": "r-lasagne"},
            rc.clean_recipe({"name": "Laks med spinatpasta", "rating": "like",
                             "ingredients": ["600 g laksefilet"], "steps": ["Bag."]})
            | {"id": "r-laks"},
        ],
    }  # fmt: skip


async def test_generate_keeps_rules_and_own_recipes(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """A repeat is sent back to the AI; the family's own recipe is used for its favourite."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    dates = mp.plan_dates(START, 7)
    repeat = ai_answer(dates, SHOPPING[:1], dishes=("Laks med ris", *DISHES_NO_LASAGNE))
    good = ai_answer(dates, SHOPPING[:1])
    ai = FakeAI(json.dumps(repeat), good)  # type: ignore[arg-type]
    await _generate(planner, ai)

    assert len(ai.prompts) == 2
    first = ai.prompts[0]
    # What the family had lately is not repeated, and not offered as inspiration.
    assert "må IKKE gentages" in first and "Kyllingewok med broccoli" in first
    assert (
        "Ovnbagt laks med pasta" in first and "Pandekager" not in first
    )  # the draft wasn't cooked
    assert "[laks]" not in first  # a favourite they just had
    assert "[lasagne] Lasagne – familiens egen opskrift r-lasagne" in first
    assert "500 g hakket oksekød (REMA-vare: HK. OKSEKØD 8-12% 500 GR.)" in first
    assert "3,2 voksenportioner" not in first and "voksenportioner" in first
    assert '"Laks med ris" gentager "Ovnbagt laks med pasta"' in ai.prompts[1]

    plan = store.latest_plan
    assert plan is not None
    assert plan["checklist"] == [{"requirement": "Budget", "ok": True}]
    lasagne = plan["days"][1]
    assert lasagne["dish"] == "Lasagne"
    assert lasagne["favorite_id"] == "lasagne"  # the AI forgot to say so
    assert lasagne["recipe_id"] == "r-lasagne"
    assert lasagne["steps"][0]["text"] == "Lav kødsovsen."
    # The list follows the recipe: its items in amounts for this household (double portion).
    assert lasagne["uses"] == ["Hakket oksekød", "Løg", "Pesto", "Lasagneplader"]
    lines = {line["name"]: line for line in plan["shopping"]}
    assert lines["Hakket oksekød"]["amount"] == 1000  # the AI's line, kept
    assert lines["Hakket oksekød"]["product"]["id"] == 30001
    # 2,9 adult portions, twice, from a recipe for 4: 1.45 of everything.
    assert (lines["Løg"]["amount"], lines["Løg"]["unit"]) == (3, "stk")
    assert (lines["Pesto"]["amount"], lines["Pesto"]["unit"]) == (2, "pk")
    assert lines["Pesto"]["category"] == "Kolonial"
    assert (lines["Lasagneplader"]["amount"], lines["Lasagneplader"]["unit"]) == (370, "g")
    assert all(line.get("recipe") for line in (lines["Løg"], lines["Pesto"]))
    assert "Salt og olie" not in lines and "Revet ost" not in lines
    assert store.favorites[1]["last_used"] == "2026-10-18"
    assert store.recipes[0]["times_planned"] == 1


async def test_generate_tells_what_it_could_not_fix(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """When the AI keeps breaking a rule, the plan says so, and the best try is kept."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    dates = mp.plan_dates(START, 7)
    # Two things wrong (a repeat, and tacos twice), then one.
    worse = ai_answer(
        dates, [], dishes=("Laks med ris", "Tacos", "Lasagne", "Tacos med bønner", "Falafel")
    )
    bad = ai_answer(dates, [], dishes=("Laks med ris", *DISHES_NO_LASAGNE))
    await _generate(planner, FakeAI(worse, bad, bad))
    plan = store.latest_plan
    assert plan is not None
    assert [c["ok"] for c in plan["checklist"]] == [True, False]
    assert plan["checklist"][1]["requirement"].startswith(
        'søndag 2026-10-18: "Laks med ris" gentager'
    )
    assert plan["days"][0]["recipe_id"] is None  # not the family's salmon: no ❤️, another dish


async def test_recipe_lines_and_product_kinds(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Shopping lines from a recipe's ingredients; products that are another kind of thing."""
    line = mp.recipe_line({"name": "laksefilet", "amount": "1,2 kg"}, 0.4)
    assert line.pop("id")
    assert line == {
        "name": "Laksefilet", "amount": 480, "unit": "g", "search": "laks", "key": "laks",
        "category": "Fisk", "offer": None, "must_have": False, "product_id": None, "recipe": True,
    }  # fmt: skip
    assert mp.recipe_line({"name": "fløde", "amount": "2,5 dl"}, 1.0)["amount"] == 250
    assert mp.recipe_line({"name": "æg", "amount": "3 stk"}, 1.5)["amount"] == 5
    assert mp.recipe_line({"name": "hvidløg", "amount": "2 fed"}, 1.0)["amount"] == 1
    assert mp.recipe_line({"name": "pesto", "amount": "ca. 1 glas"}, 1.5)["amount"] == 2
    assert mp.recipe_line({"name": "æbler", "amount": "2-3"}, 1.0)["amount"] == 2
    assert mp.recipe_line({"name": "persille", "amount": "1 bundt"})["unit"] == "pk"
    assert mp.recipe_line({"name": "smør", "amount": "lidt"})["amount"] == 1
    assert mp.recipe_line({"name": "citron", "amount": "½"})["amount"] == 1
    assert mp.recipe_line({"name": "mælk", "amount": "5 ml"}, 1.0)["amount"] == 5
    assert mp.line_category("frosne ærter") == "Frost"
    assert mp.line_category("kyllingebryst") == "Kød"
    assert mp.line_category("revet ost") == "Mejeri"
    assert mp.line_category("pitabrød") == "Brød"
    assert mp.line_category("pesto") == "Kolonial"
    assert (
        mp.recipe_factor(
            {"household": [{"role": "adult", "age": 30}]},
            {"servings": 4},
            {"makes_leftovers": True},
        )
        == 0.5
    )

    planner = init_integration.runtime_data.planner
    kebab = make_product(1, "KYLLINGEKEBAB", 29.95, underline="300 GR.", department="Frost",
                         category="Kød & fjerkræ")  # fmt: skip
    pizza = make_product(2, "KEBAB PIZZA", 20.0, underline="484 GR.", department="Frost",
                         category="Pizza")  # fmt: skip
    line = {"name": "Kebab", "search": "kebab", "amount": 500, "unit": "g", "category": "Frost"}
    assert mp.kind_penalty(line, pizza, ["kebab"]) == 5.0
    assert mp.kind_penalty(line, kebab, ["kebab"]) == 0.0
    assert mp.kind_penalty({"name": "Pizza", "search": "pizza"}, pizza, ["pizza"]) == 0.0
    candidates, _penalty = planner._candidates(line, [pizza, kebab], "kebab")
    assert [p.id for p in candidates] == [kebab.id]  # the pizza shelf is never the kebab
    fresh = make_product(3, "BROCCOLI", 12.0, underline="1 STK.", department="Frugt & grønt")
    frozen = make_product(4, "BROCCOLI", 10.0, underline="400 GR. / ØKO.", department="Frost",
                          is_organic=True)  # fmt: skip
    produce = {"name": "Broccoli", "search": "broccoli", "amount": 2, "unit": "stk",
               "category": "Frugt & grønt"}  # fmt: skip
    assert mp.kind_penalty(produce, frozen, ["broccoli"]) == 5.0
    assert mp.kind_penalty(produce, fresh, ["broccoli"]) == 0.0
    assert mp.kind_penalty({**produce, "search": "frossen broccoli"}, fresh, ["broccoli"]) == 5.0
    assert mp.kind_penalty({**produce, "search": "frossen broccoli"}, frozen, ["broccoli"]) == 0.0
    assert mp.kind_penalty({"name": "Frisk spinat", "search": "spinat"}, frozen, ["spinat"]) == 5.0

    # ... but the pizza costs five times as much in the choice, so the kebab is chosen.
    mock_client.async_search_products.side_effect = None
    mock_client.async_search_products.return_value = [pizza, kebab]
    await planner._async_match(line)
    assert line["product"]["id"] == kebab.id
    mock_client.async_search_products.return_value = [frozen, fresh]
    await planner._async_match(produce)
    assert produce["product"]["id"] == fresh.id


async def test_recipe_product_looked_up(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A recipe's own REMA product is fetched when the search doesn't list it."""
    planner = init_integration.runtime_data.planner
    line = mp.recipe_line(
        {"name": "lasagneplader", "amount": "500 g", "product": {"id": 777, "name": "LASAGNE"}}
    )
    plates = make_product(777, "LASAGNEPLADER", 15.0, underline="250 GR.")
    mock_client.async_search_products.side_effect = None
    mock_client.async_search_products.return_value = []
    mock_client.async_get_products.return_value = [plates]
    await planner._async_match(line)
    assert line["product"]["id"] == 777
    assert line["packages"] == 2
    # Gone from REMA: found by its name instead, or free text.
    mock_client.async_get_products.return_value = []
    await planner._async_match(line)
    assert line["product"] is None
    assert "fritekst" in line["note"]


def test_dish_identity_is_about_the_main_dish() -> None:
    """Pasta is not the dish, what is on it is; kinds of dish only when they define it."""
    assert not ds.same_dish("Pasta med kødsovs", "Pasta carbonara")
    assert not ds.same_dish("Ris med kylling", "Ris med rejer")
    assert ds.same_dish("Kylling i karry", "Ris med kylling")
    assert ds.same_dish("Pasta", "Pasta carbonara")
    assert not ds.same_dish("Tomatsuppe", "Græskarsuppe")
    assert not ds.same_dish("Kyllingegryde", "Oksegryde")
    assert ds.same_dish("Kartoffelsuppe", "Suppe med kartofler")
    assert ds.same_dish("Laksefilet med pasta", "Ovnbagt laks med ris")
    assert ds.same_dish("Kyllingebryst med ris", "Kylling i karry")
    assert ds.same_dish("Tacos med kylling", "Kyllingetacos")
    assert not ds.same_dish("Pasta med kylling og pesto", "Kyllingewok")


def test_fixed_day_texts() -> None:
    """The default rye-bread thursday passes for rye bread, and for a day the AI calls fixed."""
    settings = {
        "leftover_days": 0,
        "fixed_days": [{"weekday": 3, "text": "Rugbrødsdag (kun denne ene dag med rugbrød)"}],
    }
    thursday = _day("2026-10-29", "Rugbrød med æg og leverpostej")
    assert ds.check_plan({"days": [thursday]}, settings, recent=[], due_ids=set()) == []
    thursday["dish"] = "Smørrebrød"
    assert len(ds.check_plan({"days": [thursday]}, settings, recent=[], due_ids=set())) == 1
    thursday["type"] = "fast"
    assert ds.check_plan({"days": [thursday]}, settings, recent=[], due_ids=set()) == []


def test_amounts_are_parsed_and_scaled() -> None:
    """Fractions, ranges and multiples; a recipe's amounts scaled for the household."""
    assert mp.parse_amount("1½ dl") == (1.5, "dl")
    assert mp.parse_amount("1 1/2 dl") == (1.5, "dl")
    assert mp.parse_amount("1/2 l") == (0.5, "l")
    assert mp.parse_amount("2 x 400 g") == (800, "g")
    assert mp.parse_amount("2-3 stk") == (2, "stk")
    assert mp.parse_amount("ca. 3 pk.") == (3, "pk")
    assert mp.parse_amount("lidt") is None
    assert mp.recipe_line({"name": "fløde", "amount": "1½ dl"}, 2.0)["amount"] == 300
    assert mp.recipe_line({"name": "tomater", "amount": "2 x 400 g"}, 1.0)["amount"] == 800
    assert mp.to_base(3, "pk.") == ("pack", 3)
    assert rc.scale_amount("500 g", 1.5) == "750 g"
    assert rc.scale_amount("1½ dl", 1.5) == "2,25 dl"
    assert rc.scale_amount("2 stk", 1.45) == "3 stk"
    assert rc.scale_amount("lidt", 2.0) == "lidt"
    assert rc.scale_amount("500 g", 1.0) == "500 g"
    day: dict[str, Any] = {"active_minutes": 5, "total_minutes": 10}
    rc.recipe_to_day(
        {"ingredients": [{"name": "fløde", "amount": "2 dl"}], "steps": [], "servings": 4}, day, 1.5
    )
    assert day["ingredients"] == [{"name": "fløde", "amount": "3 dl"}]
    assert day["servings"] == 6


def test_ingredient_matches_a_line() -> None:
    """A compound counts, unless its first part makes it another thing."""
    assert mp._names_match({"name": "Laksefilet"}, {"name": "laks"})
    assert mp._names_match(
        {"name": "Hakket oksekød", "search": "oksekød"}, {"name": "hakket oksekød"}
    )
    assert not mp._names_match({"name": "Hvidløg"}, {"name": "løg"})
    assert not mp._names_match({"name": "Havremælk"}, {"name": "mælk"})
    assert not mp._names_match({"name": "Løg"}, {"name": "hvidløg"})
    assert mp._names_match(
        {"name": "Pasta", "product": {"name": "FETTUCCINE"}}, {"name": "fettuccine"}
    )
    assert not mp._names_match({"name": "Løg"}, {"name": ""})


async def test_recipes_share_lines(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """Two recipe days: a shared item is bought for both, and a line one of them keeps isn't dropped."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    store.recipes.insert(
        0,
        rc.clean_recipe(
            {"name": "Omelet med løg", "rating": "like", "favorite": True, "servings": 4,
             "ingredients": ["2 løg", "6 æg"], "steps": ["Pisk."]}
        )
        | {"id": "r-omelet"},
    )  # fmt: skip
    dates = mp.plan_dates(START, 7)
    answer = ai_answer(dates, [{"name": "Løg", "amount": 2, "unit": "stk", "search": "løg"}])
    answer["days"][6]["uses"] = ["Løg"]  # the omelet's own line, by the AI
    answer["days"][1]["uses"] = ["Løg"]  # ... shared with the lasagne
    await _generate(planner, FakeAI(answer))
    plan = store.latest_plan
    assert plan is not None
    omelet, lasagne = plan["days"][6], plan["days"][1]
    assert (omelet["recipe_id"], lasagne["recipe_id"]) == ("r-omelet", "r-lasagne")
    lines = {line["name"]: line for line in plan["shopping"]}
    assert lines["Løg"]["amount"] == 2  # the AI's line is kept as it is
    assert "Æg" in lines
    assert omelet["uses"] == ["Løg", "Æg"]
    assert lasagne["uses"][:2] == ["Hakket oksekød", "Løg"]


def test_amounts_follow_the_recipes() -> None:
    """A line's packages grow to what the dishes use; two dishes share a line."""
    beef = {
        "id": 1,
        "name": "HK. GRIS & KALV 4-7%",
        "underline": "400 GR. / REMA 1000",
        "price": 29.0,
    }
    cheese = {"id": 2, "name": "REVET HÅRD OST", "underline": "100 GR. / AMBROSI", "price": 15.95}
    chicken = {"id": 3, "name": "ØKO KYLLING", "underline": "1100 GR. / ROKKEDAHL", "price": 115.0}
    plan = {
        "days": [
            _day("2026-10-25", "Lasagne", ingredients=[
                {"name": "Hakket gris & kalv", "amount": "1200 g"},
                {"name": "Revet hård ost", "amount": "300 g"},
                {"name": "Letmælk", "amount": "1 liter"},
                {"name": "Hakkede tomater", "amount": "3 dåser"},
            ]),
            _day("2026-10-26", "Rester", type="rester", uses_leftovers_from="2026-10-25",
                 ingredients=[{"name": "Hakket gris & kalv", "amount": "9 kg"}]),
            _day("2026-10-27", "Hakkebøffer", ingredients=[
                {"name": "Hakket gris og kalv", "amount": "1600 g"},
                {"name": "Øko kylling", "amount": "2 stk"},
                {"name": "Fløde", "amount": "5 dl"},
            ]),
        ],
        "shopping": [
            {"name": "Hakket dansk oksekød", "amount": 2, "unit": "pk", "packages": 2, "cost": 58.0, "product": beef},
            {"name": "Revet ost", "amount": 1, "unit": "pk", "packages": 1, "cost": 15.95, "product": cheese},
            {"name": "Dansk kylling", "amount": 1, "unit": "stk", "packages": 1, "cost": 115.0, "product": chicken},
            {"name": "Mælk", "amount": 2, "unit": "l", "packages": 2, "cost": 27.9,
             "product": {"id": 4, "name": "LETMÆLK 1,5%", "underline": "1 LTR. / ARLA", "price": 13.95}},
            {"name": "Hakkede tomater", "amount": 3, "unit": "dåser", "packages": 3, "cost": 20.73,
             "product": {"id": 5, "name": "HAKKEDE TOMATER", "underline": "400 GR.", "price": 6.91}},
            {"name": "Fløde", "amount": 250, "unit": "ml", "packages": 1, "cost": None, "product": None},
            {"name": "Smør", "amount": 1, "unit": "pk", "packages": 1, "cost": 20.0, "must_have": True,
             "product": {"id": 6, "name": "SMØR", "underline": "250 GR.", "price": 20.0}},
        ],
    }  # fmt: skip
    changed = mp.fit_amounts(plan)
    assert changed == ["Hakket dansk oksekød", "Revet ost", "Dansk kylling", "Fløde"]
    lines = {line["name"]: line for line in plan["shopping"]}
    assert (lines["Hakket dansk oksekød"]["packages"], lines["Hakket dansk oksekød"]["cost"]) == (
        7,
        203.0,
    )
    assert lines["Revet ost"]["packages"] == 3
    assert lines["Dansk kylling"]["packages"] == 2
    assert lines["Fløde"]["amount"] == 500
    assert lines["Mælk"]["packages"] == 2  # enough already
    assert lines["Hakkede tomater"]["packages"] == 3
    assert plan["total"] == 203.0 + 47.85 + 230.0 + 27.9 + 20.73 + 20.0
    assert mp.fit_amounts(plan) == []  # nothing more to do
    # Never more than fourfold: a recipe gone wild doesn't empty the shop.
    plan["days"][2]["ingredients"][0]["amount"] = "40 kg"
    mp.fit_amounts(plan)
    assert lines["Hakket dansk oksekød"]["packages"] == 28


def test_compound_search_words() -> None:
    """ "Cæsardressing" finds REMA's "CÆSAR DRESSING"."""
    assert mp.name_fit(["cæsardressing"], "CÆSAR DRESSING") == (1, 1.15)
    assert mp.name_fit(["cæsardressing"], "ITALIANO DRESSING")[0] == 0
    assert "cæsar dressing" in mp.search_queries(
        {"search": "Cæsardressing", "name": "Cæsardressing"}
    )
    assert mp.search_queries({"search": "pesto", "name": "Grøn pesto"}) == ["pesto", "Grøn pesto"]

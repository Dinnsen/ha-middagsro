"""Buy the ingredient, not its preparation, and keep recipe water at home."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import matching, mealplan as mp
from custom_components.middagsro.storage import clean_settings
from custom_components.middagsro.words import (
    canned_tomato_product,
    canned_tomatoes,
    ingredient_name,
    is_tap_water,
)

from .conftest import make_plan, make_product


@pytest.mark.parametrize(
    "text,expected",
    [
        ("finthakket løg", "løg"),
        ("løg, finthakket", "løg"),
        ("fint hakket løg", "løg"),
        ("grofthakkede rødløg", "rødløg"),
        ("presset hvidløg", "hvidløg"),
        ("hvidløg (presset)", "hvidløg"),
        ("knust hvidløg", "hvidløg"),
        ("revet gulerod", "gulerod"),
        ("gulerødder i små tern", "gulerødder"),
        ("Knoldselleri, i tern", "Knoldselleri"),
        ("Svinemørbrad, i tern", "Svinemørbrad"),
        ("Kyllingebryst, i tern", "Kyllingebryst"),
        ("kyllingebryst skåret i små tern", "kyllingebryst"),
        ("Oksekød til gryderet, tern", "Oksekød til gryderet"),
        ("Bacon i tern", "Bacon i tern"),
        ("Feta i tern", "Feta i tern"),
        ("finthakket persille", "persille"),
        ("hakket oksekød", "hakket oksekød"),
        ("finthakket oksekød", "hakket oksekød"),
        ("hakkede tomater", "hakkede tomater"),
        ("knuste tomater", "knuste tomater"),
        ("revet ost", "revet ost"),
        ("revet ost med hvidløg", "revet ost med hvidløg"),
        ("hakket oksekød med løg", "hakket oksekød med løg"),
        ("tørret oregano", "tørret oregano"),
        ("soltørrede tomater", "soltørrede tomater"),
        ("æg (M)", "æg (M)"),
    ],
)
def test_preparation_and_product_type(text: str, expected: str) -> None:
    assert ingredient_name(text) == expected


@pytest.mark.parametrize(
    "name",
    [
        "vand",
        "Kogende vand",
        "koldt vand",
        "lunkent vand",
        "vand fra hanen",
        "postevand",
        "vand til kogning af pasta",
        "vand (efter behov)",
    ],
)
def test_recipe_water_is_not_shopping(name: str) -> None:
    assert is_tap_water(name)
    assert mp.MealPlanner._clean_line({"name": name, "amount": 500, "unit": "ml"}) is None


@pytest.mark.parametrize(
    "name",
    [
        "danskvand",
        "mineralvand",
        "vand med brus",
        "vand på flaske",
        "kokosvand",
        "rosenvand",
        "vandkastanjer",
        "vand og bouillon",
    ],
)
def test_real_products_are_preserved(name: str) -> None:
    assert not is_tap_water(name)
    assert mp.MealPlanner._clean_line({"name": name}) is not None


def test_clean_shopping_names_and_matching() -> None:
    line = mp.MealPlanner._clean_line(
        {"name": "finthakket løg", "search": "løg finthakket", "amount": 2, "unit": "stk"}
    )
    assert line and (line["name"], line["search"], line["amount"]) == ("løg", "løg", 2)
    assert matching.search_queries({"search": "presset hvidløg", "name": "Hvidløg, presset"}) == [
        "hvidløg"
    ]
    assert mp._names_match({"name": "Løg", "search": "løg"}, {"name": "finthakket løg"})
    assert not mp._names_match({"name": "Løg", "search": "løg"}, {"name": "presset hvidløg"})
    ingredient = {"name": "hvidløg, presset", "amount": "2 fed"}
    assert mp.recipe_line(ingredient)["search"] == "hvidløg"
    assert ingredient["name"] == "hvidløg, presset"  # the recipe keeps its instructions


@pytest.mark.parametrize("product_name", ["Rummo spaghetti", "Spaghetti"])
def test_recipe_pasta_brand_does_not_pin_the_product(product_name: str) -> None:
    assert ingredient_name("Rummo spaghetti") == "spaghetti"
    line = mp.recipe_line(
        {
            "name": "Rummo spaghetti",
            "amount": "500 g",
            "product": {"id": 123, "name": product_name},
        }
    )
    assert line["name"] == "Spaghetti" and line["search"].lower() == "spaghetti"
    assert line["product_id"] is None


@pytest.mark.parametrize(
    "name", ["grøntsagsbouillon", "bouillonterninger", "bouillon terninger", "hønsebouillon"]
)
def test_stock_volume_is_not_dry_product_volume(name: str) -> None:
    line = mp.recipe_line({"name": name, "amount": "5 dl"})
    assert line["stock_cubes"] and line["unit"] == "pk" and line["amount"] == 1
    assert "terninger" in line["search"]
    assert "bouillon" not in clean_settings({})["pantry"]
    assert (
        "bouillon"
        not in clean_settings({"pantry": "salt, peber, olie, smør, mel, sukker, eddike, bouillon"})[
            "pantry"
        ]
    )


async def test_stock_matching_excludes_liquid_and_powder(init_integration: MockConfigEntry) -> None:
    planner = init_integration.runtime_data.planner
    line = mp.MealPlanner._clean_line({"name": "Grøntsagsbouillon", "amount": 500, "unit": "ml"})
    assert line and line["unit"] == "pk"
    cubes = make_product(1, "Grøntsagsbouillon", 12, underline="120 G")
    liquid = make_product(2, "Grøntsagsbouillon", 3, underline="500 ML")
    powder = make_product(3, "Grøntsagsbouillon pulver", 4, underline="150 G")
    found, _ = planner._candidates(line, [cubes, liquid, powder], line["search"], None)
    assert [p.id for p in found] == [1]


@pytest.mark.parametrize("herb", ["oregano", "timian", "basilikum", "persille"])
async def test_herb_form_from_bilka_shelf(init_integration, herb):
    planner = init_integration.runtime_data.planner
    dried = make_product(
        1, herb.capitalize(), 10, underline="25 G", category="Krydderier og bouillon, fond"
    )
    fresh = make_product(
        2,
        herb.capitalize(),
        8,
        underline="1 STK",
        department="Frugt og grønt",
        category="Grønt, salat og krydderurter",
    )
    cut = make_product(3, f"{herb}, Afskåret", 7, underline="20 G", department="Frugt og grønt")
    frozen = make_product(4, herb.capitalize(), 5, department="Frost")
    unknown = make_product(5, herb.capitalize(), 3)
    for label, expected in [
        (f"Tørret {herb}", [1]),
        (f"{herb}, tørret", [1]),
        (f"Frisk {herb}", [2, 3]),
    ]:
        line = mp.MealPlanner._clean_line({"name": label})
        assert herb in [q.lower() for q in matching.search_queries(line)]
        found, _ = planner._candidates(line, [dried, fresh, cut, frozen, unknown], herb)
        assert [p.id for p in found] == expected
    line = mp.MealPlanner._clean_line({"name": f"Tørret {herb}"})
    found, _ = planner._candidates(line, [fresh, cut, frozen], herb)
    assert not found  # no switching forms when the requested kind is unavailable


@pytest.mark.parametrize(
    "label,query,product_name,category,department",
    [
        ("Tørret oregano", "oregano", "Oregano", "Krydderier og bouillon, fond", "Kolonial"),
        ("Timian, tørret", "timian", "Timian", "Krydderier og bouillon, fond", "Kolonial"),
        ("Karrypulver", "karry", "Karry", "Krydderier og bouillon, fond", "Kolonial"),
        (
            "Oksebouillon terninger",
            "oksebouillon",
            "Oksebouillon",
            "Krydderier og bouillon, fond",
            "Kolonial",
        ),
        (
            "Svinemørbrad, i tern",
            "mørbrad gris",
            "Mørbrad af gris u. bimørbrad",
            "Svinekød",
            "Kød og fisk",
        ),
        ("Kyllingebryst, i tern", "kyllingebryst", "Kyllingebrystfilet", "Fjerkræ", "Kød og fisk"),
        (
            "Knoldselleri, i tern",
            "knoldselleri",
            "Knoldselleri",
            "Grønt, salat og krydderurter",
            "Frugt og grønt",
        ),
        ("Oksekød til gryderet, tern", "gullasch", "Gullasch", "Oksekød", "Kød og fisk"),
    ],
)
async def test_screenshot_ingredients_match_real_bilka_names(
    init_integration, label, query, product_name, category, department
):
    planner = init_integration.runtime_data.planner
    product = make_product(
        10, product_name, 20, underline="400 G", category=category, department=department
    )
    line = mp.MealPlanner._clean_line({"name": label})

    async def search(text, at=None):
        return [product] if text.lower() == query else []

    with patch.object(planner, "_async_search", side_effect=search):
        await planner._async_match(line)
    assert line["product"] and line["product"]["id"] == 10


async def test_alternative_names_never_pick_other_meat_or_ready_meals(init_integration):
    planner = init_integration.runtime_data.planner
    pork = mp.MealPlanner._clean_line({"name": "Svinemørbrad"})
    bad = [
        make_product(1, "Oksemørbrad", 5, category="Oksekød"),
        make_product(2, "Nakkefilet af gris", 5, category="Svinekød"),
    ]
    assert not planner._candidates(pork, bad, "mørbrad gris")[0]
    beef = mp.MealPlanner._clean_line({"name": "Oksekød til gryderet, tern"})
    ready = make_product(3, "Gullasch", 5, category="Færdigretter", department="Køl")
    assert not planner._candidates(beef, [ready], "gullasch")[0]
    curry = mp.MealPlanner._clean_line({"name": "Karrypulver"})
    sauce = make_product(4, "Kylling i karry", 5, category="Færdigretter", department="Køl")
    assert not planner._candidates(curry, [sauce], "karry")[0]


async def test_retry_missing_keeps_matches_sent_lines_and_transfer_ids(
    hass, init_integration, hass_ws_client, mock_client
):
    planner = init_integration.runtime_data.planner
    plan = make_plan()
    missing = mp.MealPlanner._clean_line({"name": "Timian, tørret"})
    missing["id"] = "keep-transfer-id"
    sent = mp.MealPlanner._clean_line({"name": "Allerede sendt", "search": "sent"})
    sent["sent"] = "2026-10-27T12:00:00+01:00"
    selected = mp.MealPlanner._clean_line({"name": "Valgt af bruger", "product_id": 123})
    selected["product_id"] = 123
    plan["shopping"] = [plan["shopping"][0], missing, sent, selected]
    plan["missing_products"] = [{"id": missing["id"], "name": "Timian, tørret"}]
    await planner.store.async_add_plan(plan)
    product = make_product(
        99, "Timian", 10, underline="25 G", category="Krydderier og bouillon, fond"
    )

    async def search(query, at=None):
        return [product] if query.lower() == "timian" else []

    client = await hass_ws_client(hass)
    with patch.object(planner, "_async_search", side_effect=search) as lookup:
        await client.send_json(
            {"id": 1, "type": "middagsro/plan/refresh", "plan_id": plan["id"], "unmatched": True}
        )
        result = await client.receive_json()
    assert result["success"]
    assert missing["product"]["id"] == 99
    assert missing["id"] == "keep-transfer-id"
    assert plan["shopping"][0]["product"]["id"] == 30001
    assert sent["sent"] and selected["product_id"] == 123
    assert plan["missing_products"] == []
    assert "timian" in {call.args[0].lower() for call in lookup.call_args_list}
    mock_client.async_add_to_list.assert_not_awaited()


async def test_imported_recipe_water_and_preparation(init_integration: MockConfigEntry) -> None:
    planner = init_integration.runtime_data.planner
    plan = make_plan()
    plan["shopping"] = []
    plan["days"] = plan["days"][:1]
    plan["days"][0]["recipe_id"] = "own-recipe"
    recipe = {
        "servings": 4,
        "ingredients": [
            {"name": "Vand", "amount": "2 dl"},
            {"name": "Finthakket løg", "amount": "1 stk"},
        ],
    }
    with (
        patch("custom_components.middagsro.mealplan.find_recipe", return_value=recipe),
        patch.object(
            planner,
            "_async_price_lines",
            AsyncMock(),
        ),
    ):
        await planner._async_align_recipes(plan, [], None, None)
    assert len(plan["shopping"]) == 1
    assert plan["shopping"][0]["name"] == "Løg"
    assert recipe["ingredients"][0]["name"] == "Vand"


async def test_recipe_extras_do_not_reintroduce_water(init_integration: MockConfigEntry) -> None:
    planner = init_integration.runtime_data.planner
    plan = make_plan()
    plan["shopping"] = []
    plan["days"] = plan["days"][:1]
    plan["days"][0]["ingredients"] = [
        {"name": "Kogende vand", "amount": "1 l"},
        {"name": "Presset hvidløg", "amount": "2 fed"},
    ]
    with patch.object(planner, "_async_price_lines", AsyncMock()):
        await planner._async_recipe_extras(plan, [], None, None)
    assert [line["search"] for line in plan["shopping"]] == ["hvidløg"]


async def test_match_uses_clean_query(init_integration: MockConfigEntry) -> None:
    planner = init_integration.runtime_data.planner
    line = {"name": "Hvidløg", "search": "hvidløg presset", "amount": 1, "unit": "pk"}
    garlic = make_product(1, "Hvidløg", 10, underline="100 G")
    with patch.object(planner, "_async_search", AsyncMock(return_value=[garlic])) as search:
        await planner._async_match(line)
    assert search.call_args_list[0].args[0] == "hvidløg"
    assert line["product"]["id"] == 1


@pytest.mark.parametrize(
    "text",
    ["Hakkede tomater", "2 tomater, hakket", "flåede tomater", "Knuste tomater", "hk. tomater"],
)
def test_chopped_and_peeled_tomatoes_are_canned(text: str) -> None:
    assert canned_tomatoes(text)
    assert mp.line_category(text) == "Kolonial"


@pytest.mark.parametrize("text", ["tomater", "pillede tomater", "cherrytomater", "hakket løg"])
def test_other_tomatoes_are_not_canned(text: str) -> None:
    assert not canned_tomatoes(text)


async def test_canned_tomatoes_never_fresh(init_integration: MockConfigEntry) -> None:
    """'Hakkede tomater' is a can: fresh tomatoes and other tomato products are left out."""
    planner = init_integration.runtime_data.planner
    canned = make_product(1, "HAKKEDE TOMATER", 6, underline="400 G / ITALIEN")
    carton = make_product(2, "Tomater, hakkede", 7, underline="390 G", category="Konserves")
    fresh = make_product(3, "Tomater", 15, underline="500 G", department="Frugt & grønt")
    sundried = make_product(4, "Soltørrede tomater", 25, underline="280 G")
    plain = make_product(5, "Tomater i dåse", 8, underline="400 G")
    for text in ("hakkede tomater", "2 tomater, hakket"):
        line = {"name": text, "search": "hakkede tomater"}
        found, _ = planner._candidates(line, [canned, carton, fresh, sundried, plain], "tomater")
        ids = {p.id for p in found}
        assert 1 in ids and ids <= {1, 2, 5}
    assert canned_tomato_product("Flåede tomater", "400 G", None, None)
    assert not canned_tomato_product("Tomater", "500 G", "Frugt og grønt", None)
    assert not canned_tomato_product("Agurk", "1 STK", None, None)
    assert not canned_tomato_product("Tomater", "500 G", None, None)  # no sign of a can
    # Peeled ("pillede") tomatoes are fresh: nothing is filtered.
    line = {"name": "pillede tomater", "search": "tomater"}
    found, _ = planner._candidates(line, [fresh], "tomater")
    assert [p.id for p in found] == [3]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Citronsaft (friskpresset)", "citron"),
        ("Rød chili, hakket (mængde efter smag)", "Rød chili"),
        ("Stængler citrongræs, banket på langs og fintstrimlet", "citrongræs"),
        ("2 stængler citrongræs", "citrongræs"),
        ("Lime, saften herfra", "Lime"),
        ("Purløg (tørret eller frisk)", "Purløg"),
        ("3 fed hvidløg", "hvidløg"),
        ("Løg, finthakket", "Løg"),
        ("Fløde (38%)", "Fløde (38%)"),
        ("2 tomater, hakket", "2 tomater, hakket"),
        ("Tomater, hakkede", "Tomater, hakkede"),
        ("Citronsaft", "Citronsaft"),
    ],
)
def test_recipe_notes_are_not_shopping(text: str, expected: str) -> None:
    """A recipe's notes ("saften herfra", "(mængde efter smag)") are not part of the name."""
    assert ingredient_name(text) == expected


async def test_instant_noodles_are_not_noodles(init_integration: MockConfigEntry) -> None:
    planner = init_integration.runtime_data.planner
    cup = make_product(1, "CUPNUDLER OKSEKØD", 5.88, underline="65 GR.")
    plain = make_product(2, "NUDLER", 12.0, underline="250 GR.")
    line = {"name": "Nudler", "search": "nudler", "amount": 320, "unit": "g"}
    found, _penalty = planner._candidates(line, [cup, plain], "nudler")
    assert [p.id for p in found] == [2]  # the instant meal is never the noodles

"""2.13: the AI names the catalogue entry, and needs are counted in base units."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import amounts, mealplan as mp, structures
from custom_components.middagsro.api import RemaError
from custom_components.middagsro.bilka import BILKA_ID
from custom_components.middagsro.ingredients import CATALOG, catalogue_entry, words_are
from custom_components.middagsro.shops import next_shops
from custom_components.middagsro.storage import clean_settings
from homeassistant.core import HomeAssistant

from .conftest import make_product


def test_catalogue_key() -> None:
    """The AI's key is an entry of the catalogue; the words may or may not say so."""
    assert catalogue_entry("Salat") is CATALOG["salat"]
    assert catalogue_entry("noget andet") is None
    assert catalogue_entry(None) is None
    assert words_are(CATALOG["salat"], {"hjertesalat"})
    assert words_are(CATALOG["pølser"], {"grillpølser"})
    assert not words_are(CATALOG["laurbærblade"], {"kaffirblade"})
    assert not words_are(CATALOG["forårsløg"], {"vårløg"})


def test_lines_with_the_ai_key() -> None:
    """Words the catalogue doesn't know are searched as the AI's key, and asked about;
    words it knows win over the key."""
    clean = mp.MealPlanner._clean_line
    spring = clean({"name": "Vårløg", "search": "vårløg", "key": "forårsløg", "amount": 1})
    assert spring is not None
    assert spring["key"] == "forårsløg"
    assert spring["catalog"] == "forårsløg"
    assert spring["guessed"] is True
    assert mp.line_spec(spring).entry is CATALOG["forårsløg"]  # also when matched again
    plain = clean({"name": "Vårløg", "search": "vårløg", "amount": 1})
    assert plain is not None
    assert "catalog" not in plain
    assert plain["key"] != "forårsløg"
    salad = clean({"name": "Hjertesalat", "key": "salat"})
    assert salad is not None
    assert salad["catalog"] == "salat"
    assert "guessed" not in salad
    words_win = clean({"name": "Laksefilet", "key": "torsk"})
    assert words_win is not None
    assert words_win["key"] == "laks"
    assert "catalog" not in words_win
    nonsense = clean({"name": "Kaffirblade", "key": "findes ikke"})
    assert nonsense is not None
    assert "catalog" not in nonsense


async def test_a_guessed_key_is_asked_about(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    onions = make_product(306680, "FORÅRSLØG", 6.0, department="Frugt & grønt", underline="1 BDT.")

    async def search(query: str, limit: int = 15, **kwargs: Any) -> list[Any]:
        return [onions] if "løg" in query else []

    mock_client.async_search_products.side_effect = search
    planner = init_integration.runtime_data.planner
    line = planner._clean_line(
        {"name": "Vårløg", "search": "vårløg", "key": "forårsløg", "amount": 1, "unit": "bdt"}
    )
    await planner._async_match(line)
    assert line["product"]["name"] == "FORÅRSLØG"
    assert line["confidence"] == "medium"


def test_prompt_and_structure_have_the_key() -> None:
    settings = clean_settings({})
    dates = mp.plan_dates(date(2026, 11, 1), 7, set())
    prompt = mp.build_prompt(
        settings=settings,
        dates=dates,
        catalog=None,
        offers=[],
        favorites_due=[],
        favorites_optional=[],
        recent_dishes=[],
    )
    assert "Varenøgler: " in prompt
    assert "hakket oksekød" in prompt.split("Varenøgler: ")[1]
    assert '"key": "laks"' in prompt
    lib = structures.schema_library()
    plan = structures.plan_structure(lib)
    base = {"name": "Laks", "amount": 600, "unit": "g", "search": "laks", "category": "Fisk"}

    def shopping(line: dict[str, Any]) -> dict[str, Any]:
        answer = {"title": "Uge 45", "summary": "", "days": [], "shopping": [line]}
        return plan(answer)["shopping"][0]  # type: ignore[no-any-return]

    assert shopping({**base, "key": "laks"})["key"] == "laks"
    assert shopping({**base, "key": None})["key"] is None
    assert "key" not in shopping(base)


def test_needs_in_every_unit() -> None:
    """A thing written as 300 g and as 1 pk is both; each is counted in packages."""
    beef = make_product(1, "HAKKET OKSEKØD", 40, underline="500 GR.")
    line: dict[str, Any] = {"name": "Hakket oksekød", "amount": 300, "unit": "g"}
    amounts.add_amounts(line, {"amount": 1, "unit": "pk"})
    assert line["amount"] == 300
    assert line["need"] == {"g": 300, "pack": 1}
    assert amounts.base_need(line) == {"g": 300, "pack": 1}
    assert mp.line_packages(line, beef) == 2  # 0.6 + 1 packs
    assert mp.packages_needed(300, "g", beef) == 1

    # Pieces to grams when the catalogue knows a piece: one unit, no need kept.
    onions: dict[str, Any] = {"name": "Løg", "amount": 2, "unit": "stk"}
    amounts.add_amounts(onions, {"amount": 200, "unit": "g"}, 100)
    assert onions == {"name": "Løg", "amount": 400, "unit": "g"}

    # Something counted that a bag doesn't say: the bag still covers it.
    pita: dict[str, Any] = {"name": "Pitabrød", "amount": 2, "unit": "stk"}
    amounts.add_amounts(pita, {"amount": 1, "unit": "pk"})
    assert mp.line_packages(pita, make_product(2, "PITA", 15, underline="375 GR.")) == 1
    assert mp.packages_needed(None, None, beef, need={"stk": 2}) == 1
    assert amounts.base_need({"name": "Salt"}) == {}
    assert amounts.base_need({"name": "x", "amount": 2, "unit": "spande"}) == {}


def test_grams_of_something_sold_per_piece() -> None:
    """600 g squash is two of 300 g; 500 g broccoli is one head of about 400 g."""
    squash = make_product(3, "SQUASH", 7, underline="1 STK. / SPANIEN KL. 1")
    assert mp.packages_needed(600, "g", squash, 300) == 2
    assert mp.packages_needed(500, "g", squash, 400) == 1
    assert mp.packages_needed(600, "g", squash) == 1  # what one weighs is unknown


async def test_next_shops(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The next shops are asked in turn; a shop that can't be reached changes nothing."""
    store = init_integration.runtime_data.store
    await store.async_set_settings({"chains": [BILKA_ID]})
    planner = init_integration.runtime_data.planner
    assert [shop.name for shop in next_shops(planner)] == ["Bilka"]
    planner.bilka = MagicMock(async_search=AsyncMock(side_effect=RemaError("nede")))
    unsure = {"id": "a", "name": "Galangarod", "search": "galangarod", "amount": 1,
              "unit": "stk", "product": None, "confidence": "low", "note": "Ingen sikker vare"}  # fmt: skip
    plan: dict[str, Any] = {"shopping": [dict(unsure)]}
    await planner._async_next_shops(plan)
    assert plan["shopping"][0]["note"] == "Ingen sikker vare"

    planner.bilka = MagicMock(async_search=AsyncMock(return_value=[]))
    guess = {"name": "Kaffirblade", "search": "kaffirblade", "amount": 1, "unit": "stk",
             "product": {"id": 9, "name": "LAURBÆRBLADE", "price": 10}, "confidence": "low"}  # fmt: skip
    plan = {"shopping": [{**guess, "note": "Måske"}, {**guess, "note": None}]}
    await planner._async_next_shops(plan)
    assert [line["note"] for line in plan["shopping"]] == [
        "Måske (heller ikke sikker i Bilka)",
        "Heller ikke sikker i Bilka – tjek den",
    ]
    await planner._async_next_shops({"shopping": []})  # nothing to look for

    planner.client.has_prices = False  # another shop than REMA: no searches
    assert next_shops(planner) == []


async def test_bbq_is_barbecue(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """BBQ is short for barbecue; "Original" is the brand's usual variety. Plain
    kyllingebryst is still not the BBQ-marinated one."""
    sauce = make_product(110238, "BBQ SAUCE", 17.16, underline="370 GR. / REMA 1000",
                         category="Dressing")  # fmt: skip
    chicken = make_product(404000, "BBQ KYLLINGEBRYST", 39, underline="300 GR.",
                           department="Kød, fisk & fjerkræ", category="Kylling")  # fmt: skip

    async def search(query: str, limit: int = 15, **kwargs: Any) -> list[Any]:
        return [sauce, chicken]

    mock_client.async_search_products.side_effect = search
    planner = init_integration.runtime_data.planner
    line = planner._clean_line(
        {"name": "Barbecue Sauce Original", "amount": 80, "unit": "ml",
         "search": "Barbecue Sauce Original", "category": "Kolonial"}
    )  # fmt: skip
    await planner._async_match(line)
    assert line["product"]["name"] == "BBQ SAUCE"
    breast = planner._clean_line(
        {"name": "Kyllingebryst", "amount": 300, "unit": "g", "category": "Kød"}
    )
    await planner._async_match(breast)
    assert breast["product"] is None


async def test_repeated_days_are_swapped(
    hass: HomeAssistant, init_integration: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A day the AI kept repeating is swapped as Skift ret does it; a day that can't
    be (only repeats suggested, or the AI failing) keeps its warning."""
    from custom_components.middagsro import planedit  # noqa: PLC0415
    from homeassistant.exceptions import HomeAssistantError  # noqa: PLC0415

    from .conftest import make_plan  # noqa: PLC0415

    planner = init_integration.runtime_data.planner
    plan = make_plan("rep", start="2026-11-01")
    days = plan["days"]
    plan["checklist"] = [
        {"requirement": "Fredag er altid pizzadag", "ok": True},
        *(
            {"requirement": f'{d["weekday"]} {d["date"]}: "{d["dish"]}" gentager "x" fra de '
             "seneste uger – vælg en helt anden hovedret", "ok": False}
            for d in days
        ),
        {"requirement": 'mandag 2099-01-01: "Tacos" gentager "x" fra de seneste uger', "ok": False},
    ]  # fmt: skip
    await init_integration.runtime_data.store.async_add_plan(plan)
    swapped: list[tuple[str, str]] = []

    async def options(planner: Any, plan_id: str, day: str) -> dict[str, Any]:
        if day == days[1]["date"]:
            raise HomeAssistantError("AI'en svarer ikke")
        dishes = ["Ovnbagt laks"] if day == days[2]["date"] else ["Ovnbagt laks", "Tacos"]
        return {"options": [{"dish": d} for d in dishes]}

    async def swap(planner: Any, plan_id: str, day: str, option: dict[str, Any]) -> dict[str, Any]:
        swapped.append((day, option["dish"]))
        return plan

    monkeypatch.setattr(planedit, "async_swap_options", options)
    monkeypatch.setattr(planedit, "async_swap_dish", swap)
    await planner._async_swap_repeats(plan, ["Laks med pasta"])
    assert swapped == [(days[0]["date"], "Tacos")]
    left = [c["requirement"][:20] for c in plan["checklist"] if not c["ok"]]
    assert len(left) == 3  # the AI failing, only repeats, and a day not in the plan
    assert not any(
        c["requirement"].startswith(f"{days[0]['weekday']} {days[0]['date']}")
        for c in plan["checklist"]
    )


async def test_the_pasta_the_line_is_called(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """ "Fettuccine spinat pasta" is FETTUCCINE SPINAT, not the cheapest pasta (also
    in a smaller package); without it in the shop, the pasta found is to be checked.
    The family's choice is remembered for fettuccine spinat pasta, not every pasta."""
    from custom_components.middagsro.matching import choice_key  # noqa: PLC0415

    screws = make_product(90312, "PASTA SKRUER", 5.95, underline="500 GR. / REMA 1000",
                          category="Ris & pasta, mv")  # fmt: skip
    penne = make_product(90346, "PENNE RIGATE", 8.72, underline="500 GR. / REMA 1000",
                         category="Ris & pasta, mv")  # fmt: skip
    spinach = make_product(412322, "FETTUCCINE SPINAT", 10.16, underline="250 GR. / PASTA DI MARIA",
                           department="Køl", category="Frisk pasta")  # fmt: skip
    shelf = [screws, penne, spinach]

    async def search(query: str, limit: int = 15, **kwargs: Any) -> list[Any]:
        return shelf

    mock_client.async_search_products.side_effect = search
    planner = init_integration.runtime_data.planner
    item = {"name": "Fettuccine spinat pasta", "amount": 2, "unit": "pk", "search": "pasta",
            "category": "Kolonial"}  # fmt: skip
    line = planner._clean_line(item)
    await planner._async_match(line)
    assert line["product"]["name"] == "FETTUCCINE SPINAT"
    assert line["confidence"] == "high"
    shelf.remove(spinach)
    await planner._async_match(line)
    assert line["product"]["name"] == "PASTA SKRUER"
    assert line["confidence"] == "medium"

    assert choice_key(line) == "pasta fettuccine spinat"
    assert choice_key(planner._clean_line({"name": "Pasta"})) == "pasta"
    assert choice_key(planner._clean_line({"name": "Rød peberfrugt"})) == "peberfrugt rød"
    assert choice_key(planner._clean_line({"name": "Laksefilet"})) == "laks"


async def test_a_brand_in_the_name_is_on_the_package(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """ "Schulstad brød" is Schulstad's bread: the brand is in REMA's underline."""
    schulstad = make_product(62632, "SØDMÆLKSBRØD", 15, underline="600 GR. / SCHULSTAD",
                             department="Brød & Bavinchi", category="Brød")  # fmt: skip
    toast = make_product(60001, "TOASTBRØD", 9, underline="500 GR. / REMA 1000",
                         department="Brød & Bavinchi", category="Brød")  # fmt: skip

    async def search(query: str, limit: int = 15, **kwargs: Any) -> list[Any]:
        return [toast, schulstad]

    mock_client.async_search_products.side_effect = search
    planner = init_integration.runtime_data.planner
    line = planner._clean_line(
        {"name": "Schulstad brød", "amount": 1, "unit": "pk", "search": "brød", "category": "Brød"}
    )
    await planner._async_match(line)
    assert line["product"]["name"] == "SØDMÆLKSBRØD"
    assert line["confidence"] == "high"

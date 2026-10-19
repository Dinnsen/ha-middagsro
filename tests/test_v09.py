"""Tests for 0.9: the family's rules, nutrition, deleting and skipping days,
changing shopping items and the health summary."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import health as hl, mealplan as mp, planedit as pe
from custom_components.middagsro.api import RemaError
from custom_components.middagsro.storage import clean_settings, ensure_line_ids
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import make_plan, make_product
from .test_planedit import FakeAI


def test_settings_rules_and_nutrition() -> None:
    """Rules are a list of points; nutrition targets are kept sane."""
    settings = clean_settings(
        {
            "rules": [" Altid frisk broccoli til laks ", "", None, "x" * 400],
            "nutrition_enabled": 1,
            "protein_pct": 140,
            "carb_pct": "x",
            "kcal_min": 900,
            "kcal_max": 800,
        }
    )
    assert settings["rules"] == ["Altid frisk broccoli til laks", "x" * 300]
    assert (settings["nutrition_enabled"], settings["protein_pct"], settings["carb_pct"]) == (
        True,
        100,
        45,
    )
    assert (settings["kcal_min"], settings["kcal_max"]) == (900, 900)


def test_prompts_use_rules_and_nutrition() -> None:
    """The rules and the nutrition target reach the AI everywhere."""
    settings = clean_settings(
        {
            "rules": ["Altid frisk broccoli til laks"],
            "nutrition_enabled": True,
            "protein_pct": 40,
            "carb_pct": 35,
            "fat_pct": 25,
            "kcal_min": 800,
            "kcal_max": 900,
        }
    )
    plan = make_plan(start="2026-10-12")
    prompt = mp.build_prompt(
        settings=settings,
        dates=[date(2026, 10, 12)],
        catalog=None,
        offers=[],
        favorites_due=[],
        favorites_optional=[],
        recent_dishes=[],
    )
    assert "Familiens faste regler" in prompt
    assert "- Altid frisk broccoli til laks" in prompt
    assert "800-900 kcal pr. voksenportion" in prompt
    assert "40 % protein, 35 % kulhydrat og 25 % fedt" in prompt
    recipe = mp.build_recipe_prompt(settings=settings, day=plan["days"][0], plan=plan)
    assert "Altid frisk broccoli til laks" in recipe
    assert "Juster mængderne" in recipe
    assert '"nutrition"' in recipe
    swap = pe.build_swap_prompt(settings=settings, plan=plan, day=plan["days"][0], offer_lines=[])
    assert "Altid frisk broccoli til laks" in swap
    assert "800-900 kcal" in swap
    assert mp.nutrition_target(clean_settings({})) is None


def test_clean_nutrition() -> None:
    """The AI's estimate per adult portion."""
    assert mp.clean_nutrition({"kcal": "780", "protein_g": 52.25, "fat_g": -1, "x": 2}) == {
        "kcal": 780.0,
        "protein_g": 52.2,
    }
    assert mp.clean_nutrition({"protein_g": 30}) is None
    assert mp.clean_nutrition("nej") is None


def test_line_ids() -> None:
    """Every shopping line gets an id, kept once given."""
    plan = make_plan()
    plan["shopping"][0]["id"] = "keep"
    plan["shopping"].append("ikke en dict")
    ensure_line_ids(plan)
    assert plan["shopping"][0]["id"] == "keep"
    assert all(line.get("id") for line in plan["shopping"][1:3])


def test_own_lines() -> None:
    """A dish's own items, by its items or (older plans) its ingredients' names."""
    plan = make_plan(start="2026-10-18")
    ensure_line_ids(plan)
    ids = {line["name"]: line["id"] for line in plan["shopping"]}
    sunday, _, tuesday = plan["days"]
    # Older plan: by ingredients. Both dishes use hakket oksekød (make_plan).
    sunday["ingredients"] = [{"name": "hakket oksekød"}, {"name": "spaghetti"}]
    tuesday["ingredients"] = [{"name": "hakket oksekød"}, {"name": "frisk persille"}]
    assert pe.own_lines(plan, sunday) == {ids["Spaghetti"]}
    assert pe.own_lines(plan, tuesday) == {ids["Persille"]}
    # Newer plan: by the items each dish uses.
    sunday["uses"] = ["Hakket oksekød", "Spaghetti"]
    tuesday["uses"] = ["Persille"]
    assert pe.own_lines(plan, sunday) == {ids["Hakket oksekød"], ids["Spaghetti"]}


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan whose dishes say which items they use."""
    plan = make_plan("p", start="2026-10-18")
    sunday, monday, tuesday = plan["days"]
    sunday["uses"] = ["Hakket oksekød", "Spaghetti"]
    monday["uses"] = []
    tuesday["uses"] = ["Persille"]
    return {"plans": [plan]}


async def test_delete_and_skip_days(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """Deleting a dish empties the day (and its leftovers); skipping removes the day."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = await pe.async_clear_day(planner, "p", "2026-10-18")
    sunday, monday, _tuesday = plan["days"]
    assert (sunday["dish"], sunday["type"], sunday["ingredients"]) == ("", "tom", [])
    assert monday["type"] == "tom"  # its leftovers went with it
    assert [line["name"] for line in plan["shopping"]] == ["Persille"]
    assert plan["total"] == 0

    # An empty day gets a new dish without anything leaving the list.
    ai = FakeAI(items={"add": [], "uses": ["Persille"], "remove": ["Persille"]})
    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        plan = await pe.async_swap_dish(planner, "p", "2026-10-18", {"dish": "Omelet"})
    assert plan["days"][0]["dish"] == "Omelet"
    assert [line["name"] for line in plan["shopping"]] == ["Persille"]
    prompt = ai.prompts["REMA 1000 ny ret"][0]
    assert 'Aftensmaden 2026-10-18 bliver "Omelet"' in prompt
    assert "remove:" not in prompt
    swap = pe.build_swap_prompt(
        settings=store.settings, plan=plan, day={**plan["days"][1], "type": "tom"}, offer_lines=[]
    )
    assert "mangler aftensmad" in swap

    plan = await pe.async_clear_day(planner, "p", "2026-10-20", skip=True)
    assert [d["date"] for d in plan["days"]] == ["2026-10-18", "2026-10-19"]
    assert plan["skipped"] == ["2026-10-20"]
    assert [line["name"] for line in plan["shopping"]] == ["Persille"]  # the omelet uses it too
    with pytest.raises(ServiceValidationError):
        await pe.async_clear_day(planner, "p", "2026-10-30")


async def test_edit_lines(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A shopping line: more of it, another product, or gone."""
    store = init_integration.runtime_data.store
    planner = init_integration.runtime_data.planner
    plan = store.get_plan("p")
    assert plan is not None
    beef, persille, spaghetti = plan["shopping"]

    plan = await pe.async_edit_line(planner, "p", beef["id"], packages=3)
    beef = plan["shopping"][0]
    assert (beef["packages"], beef["product_id"]) == (3, 30001)
    assert beef["cost"] is None  # make_plan's product has no price
    beef["product"]["price"] = 40.0
    plan = await pe.async_edit_line(planner, "p", beef["id"], packages=200)
    assert (plan["shopping"][0]["packages"], plan["shopping"][0]["cost"]) == (99, 3960)
    plan = await pe.async_edit_line(planner, "p", persille["id"], packages=2)
    assert plan["shopping"][1]["cost"] is None  # free text

    noodles = make_product(60002, "SPAGHETTI", 9.0, underline="1 KG / REMA 1000")
    mock_client.async_get_products.return_value = [noodles]
    plan = await pe.async_edit_line(planner, "p", spaghetti["id"], product_id=60002)
    line = plan["shopping"][2]
    assert (line["product"]["name"], line["product_id"], line["packages"]) == (
        "SPAGHETTI",
        60002,
        1,
    )
    plan["shopping"][2]["added"] = True
    plan["shopping"][2]["buy_from"] = "2026-10-22"
    plan["shopping"][2]["packages"] = 4
    plan = await pe.async_edit_line(planner, "p", spaghetti["id"], product_id=60002)
    assert plan["shopping"][2]["packages"] == 4  # an added item keeps its count

    mock_client.async_get_products.return_value = []
    with pytest.raises(ServiceValidationError) as err:
        await pe.async_edit_line(planner, "p", spaghetti["id"], product_id=1)
    assert err.value.translation_key == "product_not_found"
    mock_client.async_get_products.side_effect = RemaError("down")
    with pytest.raises(HomeAssistantError):
        await pe.async_edit_line(planner, "p", spaghetti["id"], product_id=1)

    plan = await pe.async_edit_line(planner, "p", persille["id"], delete=True)
    assert [line["name"] for line in plan["shopping"]] == ["Hakket oksekød", "Spaghetti"]
    for plan_id, line_id, key in (("x", "a", "plan_not_found"), ("p", "nope", "line_not_found")):
        with pytest.raises(ServiceValidationError) as invalid:
            await pe.async_edit_line(planner, plan_id, line_id, delete=True)
        assert invalid.value.translation_key == key


def _line(name: str, underline: str | None, **extra: Any) -> dict[str, Any]:
    product = {"name": name.upper(), "underline": underline, **extra.pop("product", {})}
    return {"name": name, "packages": extra.pop("packages", 1), "product": product, **extra}


def test_food_groups_and_grams() -> None:
    """Lines sorted by the dietary advice, with their weight."""
    assert hl.food_group(_line("Laksefilet", "600 GR.")) == "fish"
    assert hl.food_group(_line("Torsk", None, product={"category": "Fisk & Skaldyr"})) == "fish"
    assert hl.food_group(_line("Hakket oksekød", "400 GR.")) == "red_meat"
    assert hl.food_group(_line("Kyllingestrimler", "300 GR.")) is None
    assert hl.food_group(_line("Kartofler", "2 KG.", category="Frugt & grønt")) is None
    assert hl.food_group(_line("Broccoli", "400 GR.")) == "vegetables"
    assert hl.food_group(_line("Agurk", "1 STK.", category="Frugt & grønt")) == "vegetables"
    assert hl.food_group(_line("Røde linser", "500 GR.")) == "legumes"
    assert hl.food_group(_line("Mel", "2 KG.")) is None
    assert hl.line_grams(_line("Laks", "2 X 125 GR.", packages=2)) == 500
    assert hl.line_grams({"name": "Kartofler", "amount": 2, "unit": "kg"}) == 2000
    assert hl.line_grams({"name": "Mælk", "amount": 5, "unit": "dl"}) is None
    assert hl.line_grams(_line("Agurk", "1 STK.")) is None


def test_plan_health() -> None:
    """Nutrition against the targets, the dietary advice and labels."""
    settings = clean_settings(
        {
            "nutrition_enabled": True,
            "household": [
                {"role": "adult"},
                {"role": "child", "age": 2},
                {"role": "child", "age": 8},
                {"role": "child", "age": 12},
            ],
        }
    )
    plan = make_plan(start="2026-10-18")
    sunday, _monday, tuesday = plan["days"]
    sunday["nutrition"] = {"kcal": 800, "protein_g": 50, "carbs_g": 80, "fat_g": 30}
    tuesday["dish"] = ""  # deleted
    plan["shopping"] = [
        _line("Laksefilet", "600 GR.", cost=89, product={"labels": ["Nøglehul", "ASC"]}),
        _line("Hakket oksekød", "500 GR.", cost=40, product={"labels": []}),
        _line("Broccoli", "400 GR.", cost=14, product={"is_organic": True, "labels": []}),
        _line("Agurk", "1 STK.", cost=12, product={"labels": []}),
        _line("Linser", None),
    ]
    result = hl.plan_health(plan, settings)
    assert result["people"] == 2.8  # 1 + 0.4 + 0.6 + 0.8
    assert result["days"] == 2
    assert [d["leftovers"] for d in result["dinners"]] == [False, True]
    assert result["average"]["kcal"] == 800
    assert result["average_percent"] == {"protein": 25, "carbs": 41, "fat": 34}
    assert result["targets"]["kcal_min"] == 600
    advice = {a["key"]: a["value"] for a in result["advice"]}
    assert advice == {"vegetables": 71, "fish": 750, "red_meat": 438, "legumes": 0}
    assert result["unknown"] == ["Agurk", "Linser"]
    assert result["labels"] == {"keyhole": 57, "organic": 9, "asc_msc": 57, "known": True}

    empty = hl.plan_health({"days": [], "shopping": []}, clean_settings({"household": []}))
    assert (empty["average"], empty["targets"], empty["labels"]["keyhole"]) == (None, None, None)
    assert empty["people"] == 1
    assert hl._percent({"kcal": 0}) is None


async def test_websocket_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """The panel's commands for days, lines and health."""
    client = await hass_ws_client(hass)
    store = init_integration.runtime_data.store
    plan = store.get_plan("p")
    assert plan is not None
    line_id = plan["shopping"][1]["id"]

    async def ws(msg_id: int, **msg: Any) -> dict[str, Any]:
        await client.send_json({"id": msg_id, **msg})
        result: dict[str, Any] = await client.receive_json()
        return result

    health = await ws(1, type="middagsro/health")
    assert health["result"]["plan_id"] == "p"
    assert (await ws(2, type="middagsro/health", plan_id="p"))["success"]
    changed = await ws(3, type="middagsro/plan/line", plan_id="p", line_id=line_id, packages=2)
    assert changed["result"]["shopping"][1]["packages"] == 2
    cleared = await ws(4, type="middagsro/day/clear", plan_id="p", date="2026-10-20", skip=True)
    assert cleared["result"]["skipped"] == ["2026-10-20"]
    store.plans.clear()
    missing = await ws(5, type="middagsro/health")
    assert missing["error"]["code"] == "middagsro_error"


def test_rema_nutrition() -> None:
    """A dish's nutrition from REMA's product data, per adult portion."""
    plan = make_plan(start="2026-10-18")
    ensure_line_ids(plan)
    sunday, _monday, tuesday = plan["days"]
    sunday["uses"] = ["Hakket oksekød", "Spaghetti"]
    tuesday["uses"] = ["Hakket oksekød"]
    beef, _persille, spaghetti = plan["shopping"]
    beef.update(amount=1000, unit="g")
    spaghetti["product"] = {"id": 60002, "underline": "500 GR."}
    table = {
        30001: {"kcal": 200, "protein_g": 20, "fat_g": 12},
        60002: {"kcal": 350, "carbs_g": 70},
    }
    # Sunday makes leftovers: 2 portions; beef is shared with tuesday.
    result = hl.rema_nutrition(plan, sunday, 1.0, table)
    assert result == {"kcal": 1375.0, "protein_g": 50.0, "carbs_g": 175.0, "fat_g": 30.0,
                      "fiber_g": 0.0, "coverage": 100}  # fmt: skip
    assert hl.rema_nutrition(plan, tuesday, 2.0, {}) is None
    health = hl.plan_health(plan, clean_settings({"household": [{"role": "adult"}]}), table)
    assert health["dinners"][1]["rema"] == health["dinners"][0]["rema"]  # leftovers
    assert health["rema_average"]["kcal"] > 0


async def test_nutrition_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    mock_client: MagicMock,
) -> None:
    """Nutrition for one product, and REMA's data in the health summary."""
    client = await hass_ws_client(hass)
    mock_client.async_get_nutrition = AsyncMock(return_value={30001: {"kcal": 200}})
    await client.send_json({"id": 1, "type": "middagsro/nutrition", "product_id": 30001})
    assert (await client.receive_json())["result"] == {"kcal": 200}
    await client.send_json({"id": 2, "type": "middagsro/nutrition", "product_id": 5})
    assert (await client.receive_json())["result"] == {}
    mock_client.async_get_nutrition.side_effect = RemaError("down")
    await client.send_json({"id": 3, "type": "middagsro/health"})
    assert (await client.receive_json())["success"]

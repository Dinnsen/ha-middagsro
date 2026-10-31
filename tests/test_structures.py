"""Structured answers from the AI, and the AI's help choosing between products."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import structures
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import make_plan, make_product


def test_structures_validate_answers() -> None:
    """The schemas accept what the AI should answer and refuse what it shouldn't."""
    lib = structures.schema_library()
    assert hasattr(lib, "Schema")
    plan = structures.plan_structure(lib)
    answer = {
        "title": "Uge 45",
        "summary": "Nemt",
        "days": [
            {
                "date": "2026-11-02",
                "dish": "Tacos",
                "type": "normal",
                "favorite_id": None,
                "uses_leftovers_from": None,
                "makes_leftovers": True,
                "servings": 4,
                "active_minutes": 20,
                "total_minutes": 30,
                "uses": ["Hakket oksekød"],
            }
        ],
        "shopping": [
            {"name": "Hakket oksekød", "amount": 500, "unit": "g", "search": "hakket oksekød",
             "category": "Kød", "offer": "o1"}
        ],
        "checklist": [],
        "deviations": "",
    }  # fmt: skip
    assert plan(answer)["days"][0]["dish"] == "Tacos"
    with pytest.raises(lib.Invalid):
        plan({**answer, "days": [{**answer["days"][0], "type": "fest"}]})
    recipe = structures.recipe_structure(lib)
    assert recipe(
        {"ingredients": [{"name": "løg", "amount": "1"}], "steps": [{"text": "Hak.", "minutes": 2}]}
    )
    choices = structures.choices_structure(lib)
    assert choices({"choices": [{"line": "a1", "product": 12}, {"line": "a2", "product": None}]})


def test_schema_library_follows_home_assistant() -> None:
    """The library is the one AI Task names for its structure."""

    def fake(hass: Any, *, structure: "probatio.Schema | None" = None) -> None:  # noqa: F821, UP037
        return None

    with patch("homeassistant.components.ai_task.task.async_generate_data", new=fake):
        lib = structures.schema_library()
    assert lib.__name__ in ("probatio", "voluptuous")  # probatio when it is installed


async def test_ask_ai_falls_back_without_a_structure(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """An AI Task entity that can't take a response schema is asked freely instead."""
    planner = init_integration.runtime_data.planner
    calls: list[Any] = []

    async def generate(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs.get("structure"))
        if kwargs.get("structure") is not None:
            raise HomeAssistantError("response_schema is not supported by this model")
        return SimpleNamespace(data={"ok": True})

    lib = structures.schema_library()
    with patch("homeassistant.components.ai_task.async_generate_data", new=generate):
        answer = await planner._async_ask_ai("hej", "test", structure=lib.Schema({"ok": bool}))
    assert answer == {"ok": True}
    assert calls[0] is not None and calls[1] is None

    async def broken(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        raise HomeAssistantError("offline")

    with (
        patch("homeassistant.components.ai_task.async_generate_data", new=broken),
        pytest.raises(HomeAssistantError),
    ):
        await planner._async_ask_ai("hej", "test", structure=lib.Schema({"ok": bool}))


async def test_ai_helps_choose_between_products(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, ai_task: str
) -> None:
    """The AI picks among the products found for uncertain lines; the lines stay marked."""
    planner = init_integration.runtime_data.planner
    plan = make_plan("choices")
    beef, parsley, pasta = plan["shopping"]
    beef.update(id="beef", confidence="high")
    parsley.update(
        id="parsley",
        confidence="low",
        product={"id": 80001, "name": "PERSILLE PESTO", "underline": "190 GR.", "price": 20.0},
        packages=1,
        cost=20.0,
        alternatives=[{"id": 80002, "name": "PERSILLE", "underline": "1 BDT.", "price": 9.0}],
    )
    pasta.update(
        id="pasta",
        confidence="medium",
        product={"id": 60002, "name": "SPAGHETTI", "underline": "1 KG", "price": 9.0},
        packages=1,
        cost=9.0,
        alternatives=[{"id": 60003, "name": "GLUTENFRI SPAGHETTI", "price": 22.0}],
    )
    sure = {**beef, "id": "sure", "confidence": "medium", "alternatives": [{"id": 1, "name": "X"}],
            "product_id": 30001}  # fmt: skip
    plan["shopping"].append(sure)
    prompts: list[str] = []

    async def generate(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        prompts.append(kwargs["instructions"])
        return SimpleNamespace(
            data={
                "choices": [
                    {"line": "parsley", "product": 80002},
                    {"line": "pasta", "product": None},
                    {"line": "nope", "product": 1},
                ]
            }
        )

    mock_client.async_get_products.return_value = [
        make_product(80002, "PERSILLE", 9.0, underline="1 BDT.", department="Frugt & grønt")
    ]
    with patch("homeassistant.components.ai_task.async_generate_data", new=generate):
        await planner._async_ai_choices(plan)
    assert len(prompts) == 1
    assert (
        "parsley | Persille (1 bundt) | 80001: PERSILLE PESTO (190 GR.); 80002: PERSILLE (1 BDT.)"
        in prompts[0]
    )
    assert "sure |" not in prompts[0]  # chosen by the family already: not asked about
    assert parsley["product"]["id"] == 80002
    assert parsley["confidence"] == "medium"
    assert parsley["note"] == "AI'en valgte denne blandt mulighederne – tjek den"
    assert [a["id"] for a in parsley["alternatives"]] == [80001]
    assert parsley["cost"] == 9.0
    assert pasta["product"]["id"] == 60002
    assert pasta["confidence"] == "low"
    assert "tjek den" in pasta["note"]
    assert plan["total"] == 40.0 + 9.0 + 9.0 + 40.0

    # Nothing uncertain, or the AI failing, changes nothing.
    async def broken(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        raise HomeAssistantError("busy")

    parsley["reviewed"] = True
    with patch("homeassistant.components.ai_task.async_generate_data", new=broken):
        await planner._async_ai_choices(plan)
    assert pasta["product"]["id"] == 60002

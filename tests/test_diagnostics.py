"""Tests for REMA 1000 diagnostics."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro.diagnostics import async_get_config_entry_diagnostics
from homeassistant.core import HomeAssistant

from .conftest import EMAIL, PASSWORD, make_plan


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan with a missing product and a failed recipe."""
    plan = make_plan()
    plan["days"][2]["recipe_error"] = "timeout"
    return {
        "plans": [plan],
        "settings": {"household": [{"role": "adult", "age": 41, "sex": "female"}]},
    }


async def test_diagnostics(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """Diagnostics hold counts and settings, never the login or names."""
    result = await async_get_config_entry_diagnostics(hass, init_integration)
    text = json.dumps(result)
    assert EMAIL not in text
    assert PASSWORD not in text
    assert "Kage til Anna" not in text
    assert "Spaghetti" not in text

    assert result["entry"]["data"] == {"email": "**REDACTED**", "password": "**REDACTED**"}
    assert result["shopping_list"]["items"] == 3
    assert result["shopping_list"]["unbought_items"] == 2
    assert result["offers"]["current"]["label"] == "Uge 42"
    assert result["settings"]["household_members"] == 1
    assert result["latest_plan"]["lines_without_product"] == 2
    assert result["latest_plan"]["recipe_errors"] == 1
    assert result["planner"] == {"state": "idle", "ai_available": True}


async def test_diagnostics_without_data(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Works before any list, offers or plan exist."""
    data = init_integration.runtime_data
    data.shopping_list.data = None
    data.offers.data = None
    data.store.plans = []
    result = await async_get_config_entry_diagnostics(hass, init_integration)
    assert result["shopping_list"]["items"] is None
    assert result["offers"]["current"] is None
    assert result["latest_plan"] is None
    assert result["planner"]["ai_available"] is False

"""Tests for 2.8.1: an AI service's errors told in plain Danish."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro import mealplan as mp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import make_plan

GOOGLE = (
    'Sorry, I had a problem getting a response from Google Generative AI.: {"error": {"code": '
    '402, "message": "Your prepayment credits are depleted. Please go to AI Studio at '
    'https://ai.studio/projects", "status": "RESOURCE_EXHAUSTED"}}'
)


@pytest.fixture
def storage_contents() -> dict[str, Any]:
    """A plan already made."""
    return {"plans": [make_plan("p", start="2026-10-11")]}


@pytest.mark.parametrize(
    ("text", "key", "provider"),
    [
        (GOOGLE, "ai_no_credit", "Google AI Studio"),
        ("Error code: 429 - insufficient_quota (OpenAI)", "ai_no_credit", "OpenAI"),
        ("anthropic: Your credit balance is too low", "ai_no_credit", "Anthropic"),
        ("429 RESOURCE_EXHAUSTED: rate limit for gemini", "ai_busy", "Google AI Studio"),
        ("Overloaded (529)", "ai_busy", "Min AI"),
        ("API key not valid. Please pass a valid API key.", "ai_key_failed", "Min AI"),
        ("401 Unauthorized from mistral", "ai_key_failed", "Mistral"),
    ],
)
def test_ai_problem(text: str, key: str, provider: str) -> None:
    """What the AI service said, and who it is."""
    problem = mp.ai_problem(HomeAssistantError(text), "Min AI")
    assert problem is not None
    assert problem.translation_key == key
    assert problem.translation_placeholders == {"provider": provider}


def test_not_an_ai_problem() -> None:
    """Other errors are left as they are."""
    assert mp.ai_problem(HomeAssistantError("Something else went wrong")) is None
    assert mp.ai_provider("nothing to go by") == "AI-tjenesten"


async def test_plan_tells_the_family(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """A plan that can't be made says why in Danish (no traceback in the log)."""
    planner = init_integration.runtime_data.planner
    ai = AsyncMock(side_effect=HomeAssistantError(GOOGLE))
    with (
        patch("homeassistant.components.ai_task.async_generate_data", new=ai),
        patch.object(mp._LOGGER, "exception") as logged,
    ):
        planner.async_start_generation(mp.date(2026, 10, 18))
        await planner._task
    assert planner.status["state"] == "error"
    assert planner.status["message"].startswith(
        "AI'en svarede ikke: kontoen hos Google AI Studio er løbet tør for kredit"
    )
    logged.assert_not_called()


async def test_other_errors_are_logged(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """An unknown error keeps its traceback in the log."""
    planner = init_integration.runtime_data.planner
    ai = AsyncMock(side_effect=HomeAssistantError("noget helt andet"))
    with (
        patch("homeassistant.components.ai_task.async_generate_data", new=ai),
        patch.object(mp._LOGGER, "exception") as logged,
    ):
        planner.async_start_generation(mp.date(2026, 10, 18))
        await planner._task
    assert planner.status["message"] == "noget helt andet"
    logged.assert_called_once()

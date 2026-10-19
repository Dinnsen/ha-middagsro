"""Tests for setting up and unloading REMA 1000."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rema1000.api import RemaAuthError, RemaConnectionError, RemaError
from custom_components.rema1000.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import NOW, UPCOMING


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_panel: tuple[AsyncMock, MagicMock],
) -> None:
    """The entry loads, shows the panel and unloads again."""
    register, unregister = mock_panel
    assert init_integration.state is ConfigEntryState.LOADED
    register.assert_awaited_once()
    assert hass.services.has_service(DOMAIN, "add_items")

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    unregister.assert_called_once()


async def test_panel_stays_while_another_account_is_loaded(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    mock_panel: tuple[AsyncMock, MagicMock],
) -> None:
    """The panel is shared; it is only removed with the last account."""
    second = MockConfigEntry(
        domain=DOMAIN,
        title="other@example.com",
        unique_id="4343",
        data={"email": "other@example.com", "password": "x"},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    _, unregister = mock_panel
    assert await hass.config_entries.async_unload(second.entry_id)
    unregister.assert_not_called()


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (RemaAuthError("rejected"), ConfigEntryState.SETUP_ERROR),
        (RemaConnectionError("down"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_login_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_panel: tuple[AsyncMock, MagicMock],
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """A rejected login asks for the password; a network error retries."""
    mock_client.async_login.side_effect = error
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is state
    if state is ConfigEntryState.SETUP_ERROR:
        flows = hass.config_entries.flow.async_progress()
        assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_setup_list_auth_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_panel: tuple[AsyncMock, MagicMock],
) -> None:
    """A session REMA no longer accepts while reading the list starts reauth."""
    mock_client.async_get_primary_list.side_effect = RemaAuthError("expired")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_list_error_retries(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_panel: tuple[AsyncMock, MagicMock],
) -> None:
    """The list must load once; otherwise setup is retried."""
    mock_client.async_get_primary_list.side_effect = RemaError("HTTP 500")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_without_offers(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_panel: tuple[AsyncMock, MagicMock],
) -> None:
    """The offers come from a third party and may fail without blocking setup."""
    mock_client.async_get_catalogs.side_effect = RemaError("Tjek is down")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.middagsro_current_offer_catalogue").state == "unavailable"


async def test_auto_generate_on_new_catalogue(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_panel: tuple[AsyncMock, MagicMock],
    ai_task: str,
    freezer: Any,
) -> None:
    """With automatic plans on, next week's plan starts when the new avis is out."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Copenhagen")
    hass_storage[f"{DOMAIN}.{config_entry.entry_id}.mealplans"] = {
        "version": 1,
        "key": f"{DOMAIN}.{config_entry.entry_id}.mealplans",
        "data": {"settings": {"auto_generate": True, "auto_send": True}, "plans": []},
    }
    config_entry.add_to_hass(hass)
    with patch("custom_components.rema1000.mealplan.MealPlanner.async_start_generation") as start:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    start.assert_called_once()
    start_date = start.call_args.args[0]
    assert start_date.isoformat() == "2026-10-18"  # the Sunday the next avis starts
    assert start.call_args.kwargs == {"send": True}
    assert UPCOMING.valid_from is not None

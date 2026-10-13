"""Tests for the REMA 1000 coordinators."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rema1000.api import Catalog
from custom_components.rema1000.coordinator import RemaOffersCoordinator
from homeassistant.core import HomeAssistant

from .conftest import CURRENT, NOW, UPCOMING


async def test_offers_pick_current_and_next(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: Any,
) -> None:
    """The running avis with most offers is current; the first future one is next."""
    freezer.move_to(NOW)
    small = Catalog("small", "Lokal avis", CURRENT.valid_from, CURRENT.valid_to, 4)
    later = Catalog(
        "later",
        "Uge 44",
        datetime(2026, 10, 24, 22, tzinfo=UTC),
        datetime(2026, 10, 31, 21, tzinfo=UTC),
        None,
    )
    undated = Catalog("undated", None, None, None, None)
    mock_client.async_get_catalogs.return_value = [later, small, CURRENT, UPCOMING, undated]
    config_entry.add_to_hass(hass)
    coordinator = RemaOffersCoordinator(hass, config_entry, mock_client)
    await coordinator.async_refresh()

    data = coordinator.data
    assert data.current is CURRENT
    assert data.upcoming is UPCOMING
    assert set(data.first_seen) == {"later", "small", "cat-42", "cat-43", "undated"}

    await hass.async_block_till_done()
    key = f"rema1000.{config_entry.entry_id}.catalogs"
    assert hass_storage[key]["data"]["first_seen"]["cat-43"] == NOW.isoformat()

    # A restart keeps when each avis was first seen.
    freezer.tick(3600)
    again = RemaOffersCoordinator(hass, config_entry, mock_client)
    await again.async_refresh()
    assert again.data.first_seen["cat-43"] == NOW.isoformat()


async def test_offers_none_running(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock, freezer: Any
) -> None:
    """Between two aviser there may be no current one."""
    freezer.move_to(NOW)
    mock_client.async_get_catalogs.return_value = [UPCOMING]
    config_entry.add_to_hass(hass)
    coordinator = RemaOffersCoordinator(hass, config_entry, mock_client)
    await coordinator.async_refresh()
    assert coordinator.data.current is None
    assert coordinator.data.upcoming is UPCOMING

    mock_client.async_get_catalogs.return_value = []
    await coordinator.async_refresh()
    assert coordinator.data.upcoming is None

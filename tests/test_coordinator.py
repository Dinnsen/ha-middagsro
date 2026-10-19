"""Tests for the REMA 1000 coordinators."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro.api import Catalog
from custom_components.middagsro.coordinator import RemaOffersCoordinator
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
    key = f"middagsro.{config_entry.entry_id}.catalogs"
    assert hass_storage[key]["data"]["first_seen"]["cat-43"] == NOW.isoformat()

    # A restart keeps when each avis was first seen.
    freezer.tick(3600)
    again = RemaOffersCoordinator(hass, config_entry, mock_client)
    await again.async_refresh()
    assert again.data.first_seen["cat-43"] == NOW.isoformat()


async def test_insert_is_not_next_weeks_avis(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock, freezer: Any
) -> None:
    """An insert (indstik) is out on wednesday, before it starts: not next week's avis.

    From REMA's real aviser: "Uge 42 Indstik" runs thursday to saturday inside
    "Uge 42"; the month-long "Meget mere" aviser have no offers.
    """
    freezer.move_to(NOW)  # wednesday
    insert = Catalog("insert", "Uge 42 Indstik", datetime(2026, 10, 14, 22, tzinfo=UTC),
                     CURRENT.valid_to, 12)  # fmt: skip
    season = Catalog("season", "Meget mere sæson", datetime(2026, 9, 30, 22, tzinfo=UTC),
                     datetime(2026, 10, 31, 23, tzinfo=UTC), 0)  # fmt: skip
    mock_client.async_get_catalogs.return_value = [insert, season, CURRENT, UPCOMING]
    config_entry.add_to_hass(hass)
    coordinator = RemaOffersCoordinator(hass, config_entry, mock_client)
    await coordinator.async_refresh()
    assert coordinator.data.current is CURRENT
    assert coordinator.data.upcoming is UPCOMING

    # Before next week's avis is out.
    mock_client.async_get_catalogs.return_value = [insert, season, CURRENT]
    await coordinator.async_refresh()
    assert coordinator.data.upcoming is None

    # On thursday, the week's avis is still the current one.
    freezer.move_to(datetime(2026, 10, 15, 8, tzinfo=UTC))
    await coordinator.async_refresh()
    assert coordinator.data.current is CURRENT


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

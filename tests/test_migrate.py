"""Tests for moving an installation of the old rema1000 integration to Middagsro."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.migrate import MIGRATE_FROM, OLD_DOMAIN, old_entries
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import make_plan


async def test_moving_the_old_integration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_client: MagicMock,
    mock_panel: Any,
) -> None:
    """The account, its plans, device and entities (with their ids) come over."""
    old = MockConfigEntry(
        domain=OLD_DOMAIN,
        title="familien@example.com",
        unique_id="749434",
        data={CONF_EMAIL: "familien@example.com", CONF_PASSWORD: "hemmelig"},
    )
    old.add_to_hass(hass)
    hass_storage[f"{OLD_DOMAIN}.{old.entry_id}.mealplans"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{OLD_DOMAIN}.{old.entry_id}.mealplans",
        "data": {"plans": [make_plan("p")], "settings": {"budget": 777}},
    }
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=old.entry_id, identifiers={(OLD_DOMAIN, "749434")}, name="REMA 1000"
    )
    entities = er.async_get(hass)
    sensor = entities.async_get_or_create(
        "sensor",
        OLD_DOMAIN,
        "749434_meal_plan",
        config_entry=old,
        device_id=device.id,
        suggested_object_id="rema_1000_meal_plan",
    )
    hass.states.async_set(sensor.entity_id, "unavailable")
    assert old_entries(hass) == [old]

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert (result["type"], result["step_id"]) == (FlowResultType.FORM, "migrate")
    assert result["description_placeholders"] == {"account": "familien@example.com"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert MIGRATE_FROM not in entry.data
    assert entry.data[CONF_PASSWORD] == "hemmelig"
    assert hass.config_entries.async_get_entry(old.entry_id) is None
    assert entry.runtime_data.store.settings["budget"] == 777
    assert entry.runtime_data.store.get_plan("p") is not None
    assert f"{OLD_DOMAIN}.{old.entry_id}.mealplans" not in hass_storage
    moved = entities.async_get(sensor.entity_id)
    assert moved is not None
    assert (moved.platform, moved.config_entry_id) == (DOMAIN, entry.entry_id)
    assert sensor.entity_id == "sensor.rema_1000_meal_plan"  # the id is kept
    device = devices.async_get(device.id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, "749434")}
    assert device.config_entry_id == entry.entry_id
    assert old_entries(hass) == []

    # Nothing more to move: the normal login.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["step_id"] == "user"


async def test_moving_a_loaded_entry_twice(
    hass: HomeAssistant, mock_client: MagicMock, mock_panel: Any
) -> None:
    """A loaded old entry is unloaded first; an account already moved is not moved again."""
    old = MockConfigEntry(
        domain=OLD_DOMAIN, unique_id="749434", data={CONF_EMAIL: "a", CONF_PASSWORD: "b"}
    )
    old.add_to_hass(hass)
    old.mock_state(hass, ConfigEntryState.LOADED)
    first = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    second = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(first["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_get_entry(old.entry_id) is None
    result = await hass.config_entries.flow.async_configure(second["flow_id"], {})
    assert (result["type"], result["reason"]) == (FlowResultType.ABORT, "already_configured")


async def test_old_entry_already_gone(
    hass: HomeAssistant, mock_client: MagicMock, mock_panel: Any
) -> None:
    """An entry that says it comes from an old one that is gone just starts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="749434",
        data={CONF_EMAIL: "a", CONF_PASSWORD: "b", MIGRATE_FROM: "gone"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert MIGRATE_FROM not in entry.data

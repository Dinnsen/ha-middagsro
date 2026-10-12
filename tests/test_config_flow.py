"""Tests for the REMA 1000 config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rema1000.api import RemaAuthError, RemaConnectionError
from custom_components.rema1000.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import EMAIL, PASSWORD, USER_ID


@pytest.fixture(autouse=True)
def no_setup(mock_panel: tuple[AsyncMock, MagicMock]) -> None:
    """Entries created by the flow are set up with the mocked client."""


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A working login creates the entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: f"  {EMAIL} ", CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"] == {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    assert result["result"].unique_id == str(USER_ID)


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (RemaAuthError("rejected"), "invalid_auth"),
        (RemaConnectionError("down"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_client: MagicMock, error: Exception, key: str
) -> None:
    """Errors are shown, and the flow can be finished after fixing them."""
    mock_client.async_login.side_effect = error
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}

    mock_client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_client: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The same REMA account can only be added once."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_client: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A new password is saved and the entry reloaded."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"email": EMAIL}

    mock_client.async_login.side_effect = RemaAuthError("rejected")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "still-wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_other_account(
    hass: HomeAssistant, mock_client: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Logging in to another account is refused."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    mock_client.async_login.return_value = 999
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "other"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert config_entry.data[CONF_PASSWORD] == PASSWORD


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_client: MagicMock, config_entry: MockConfigEntry
) -> None:
    """E-mail and password can be changed for the same account."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_client.async_login.side_effect = RemaConnectionError("down")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "new@example.com", CONF_PASSWORD: "new"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: " new@example.com ", CONF_PASSWORD: "new"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_EMAIL: "new@example.com", CONF_PASSWORD: "new"}
    assert config_entry.title == "new@example.com"


async def test_reconfigure_flow_other_account(
    hass: HomeAssistant, mock_client: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Reconfigure cannot switch to another REMA account."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    mock_client.async_login.return_value = 999
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "other@example.com", CONF_PASSWORD: "x"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert config_entry.data[CONF_EMAIL] == EMAIL

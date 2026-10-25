"""Tests for the REMA 1000 config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.middagsro.api import RemaAuthError, RemaConnectionError
from custom_components.middagsro.const import DOMAIN
from custom_components.middagsro.store_client import CONF_STORE, REMA
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
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: REMA})
    assert result["step_id"] == "rema"
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
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: REMA})
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
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: REMA})
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
    assert result["description_placeholders"]["email"] == EMAIL

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
    assert result["description_placeholders"] == {"store": "REMA 1000"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: REMA})
    assert result["step_id"] == "reconfigure_rema"

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
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: REMA})
    mock_client.async_login.return_value = 999
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "other@example.com", CONF_PASSWORD: "x"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert config_entry.data[CONF_EMAIL] == EMAIL


NETTO = "9ba51"


@pytest.fixture
def no_entry_setup() -> object:
    """Entries for another shop are not set up here (that reads Tjek)."""
    with patch("custom_components.middagsro.async_setup_entry", AsyncMock(return_value=True)):
        yield


@pytest.mark.usefixtures("no_entry_setup")
async def test_other_shop(hass: HomeAssistant) -> None:
    """Another shop takes no login: what only works with REMA is listed first."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: NETTO})
    assert result["step_id"] == "store"
    assert result["description_placeholders"]["store"] == "Netto"
    assert "- REMA's opskrifter" in result["description_placeholders"]["missing"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Middagsro – Netto"
    assert result["data"] == {CONF_STORE: NETTO}
    assert result["result"].unique_id == f"store_{NETTO}"

    # Once per shop.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: NETTO})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("no_entry_setup")
async def test_shop_already_chosen_by_a_changed_entry(hass: HomeAssistant) -> None:
    """A REMA entry changed to Netto keeps its unique id, but Netto is taken."""
    MockConfigEntry(domain=DOMAIN, unique_id="123", data={CONF_STORE: NETTO}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: NETTO})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("no_entry_setup")
async def test_reconfigure_to_another_shop(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """REMA to Netto: the login is forgotten, the entry (and its entities' ids) kept."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: NETTO})
    assert result["step_id"] == "reconfigure_store"
    assert result["description_placeholders"]["store"] == "Netto"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_STORE: NETTO}
    assert config_entry.title == "Middagsro – Netto"
    assert config_entry.unique_id == str(USER_ID)

    # Taken by another entry.
    MockConfigEntry(domain=DOMAIN, unique_id="store_bdf5A", data={CONF_STORE: "bdf5A"}).add_to_hass(
        hass
    )
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["description_placeholders"] == {"store": "Netto"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STORE: "bdf5A"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("no_entry_setup")
async def test_reconfigure_from_another_shop_to_rema(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """An entry made for Netto may log in to any REMA account not set up already."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"store_{NETTO}",
        title="Middagsro – Netto",
        data={CONF_STORE: NETTO},
    )
    entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, unique_id="555", data={CONF_EMAIL: "x", CONF_PASSWORD: "y"}
    )
    other.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: REMA})
    assert result["step_id"] == "reconfigure_rema"
    mock_client.async_login.return_value = 555
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    assert result["reason"] == "already_configured"

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STORE: REMA})
    mock_client.async_login.return_value = USER_ID
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    assert entry.title == EMAIL
    assert entry.unique_id == f"store_{NETTO}"

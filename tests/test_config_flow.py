"""Tests for the TRMNL Terminus config flow."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trmnl_terminus.api import (
    TerminusAuthenticationError,
    TerminusConnectionError,
)
from custom_components.trmnl_terminus.const import DOMAIN

from .conftest import SERVER_URL

USER_INPUT = {
    CONF_URL: "terminus.local:3000/",
    CONF_USERNAME: " user@example.com ",
    CONF_PASSWORD: "secret",
}
EXPECTED_DATA = {
    CONF_URL: SERVER_URL,
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "secret",
}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_terminus_client: AsyncMock) -> None:
    """A valid URL and credentials create an entry with a normalized URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Terminus (terminus.local)"
    assert result["data"] == EXPECTED_DATA
    assert result["result"].unique_id == SERVER_URL
    mock_terminus_client.async_login.assert_awaited_once()
    mock_terminus_client.async_get_devices.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_invalid_url(
    hass: HomeAssistant, mock_terminus_client: AsyncMock
) -> None:
    """An unusable URL is reported on the URL field and can be corrected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_URL: "ftp://nope"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}
    mock_terminus_client.async_login.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TerminusAuthenticationError("nope"), "invalid_auth"),
        (TerminusConnectionError("down"), "cannot_connect"),
        (RuntimeError("weird"), "unknown"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_terminus_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Login problems show an error and the flow can recover."""
    mock_terminus_client.async_login.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_terminus_client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_terminus_client")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The same server cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_terminus_client")
async def test_reauth(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Reauth updates the stored credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_PASSWORD: "new-secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"
    assert mock_config_entry.unique_id == SERVER_URL


@pytest.mark.usefixtures("mock_setup_entry", "mock_terminus_client")
async def test_reconfigure_new_url(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfigure can move the entry to another server URL."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_URL: "https://other.local"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_URL] == "https://other.local"
    assert mock_config_entry.unique_id == "https://other.local"


@pytest.mark.usefixtures("mock_setup_entry", "mock_terminus_client")
async def test_reconfigure_to_existing_server_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfiguring onto a URL owned by another entry is refused."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://other.local",
        data={**EXPECTED_DATA, CONF_URL: "https://other.local"},
    )
    other.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_URL: "https://other.local"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_URL] == SERVER_URL

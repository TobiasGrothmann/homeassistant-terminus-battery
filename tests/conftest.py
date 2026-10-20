"""Common fixtures for the TRMNL Terminus tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trmnl_terminus.api import TerminusDevice, TerminusModel
from custom_components.trmnl_terminus.const import DOMAIN

from . import load_fixture

SERVER_URL = "http://terminus.local:3000"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.trmnl_terminus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Terminus (terminus.local)",
        unique_id=SERVER_URL,
        data={
            CONF_URL: SERVER_URL,
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
        },
    )


def fixture_devices() -> list[TerminusDevice]:
    """Return the devices from the fixture file."""
    return [
        TerminusDevice.from_dict(item)
        for item in json.loads(load_fixture("devices.json"))["data"]
    ]


def fixture_models() -> list[TerminusModel]:
    """Return the models from the fixture file."""
    return [
        TerminusModel.from_dict(item)
        for item in json.loads(load_fixture("models.json"))["data"]
    ]


@pytest.fixture
def mock_terminus_client() -> Generator[AsyncMock]:
    """Mock the Terminus client in the coordinator and the config flow."""
    with (
        patch(
            "custom_components.trmnl_terminus.coordinator.TerminusClient",
            autospec=True,
        ) as mock_client,
        patch(
            "custom_components.trmnl_terminus.config_flow.TerminusClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.url = SERVER_URL
        client.async_get_devices.return_value = fixture_devices()
        client.async_get_models.return_value = fixture_models()
        client.async_set_sleep.return_value = fixture_devices()[0]
        yield client

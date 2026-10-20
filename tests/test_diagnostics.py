"""Tests for the TRMNL Terminus diagnostics."""

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from . import setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Diagnostics redact secrets and serialize dates."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"]["password"] == REDACTED
    assert result["entry"]["url"] == "http://terminus.local:3000"
    assert len(result["devices"]) == 2
    device = result["devices"][0]
    assert device["mac_address"] == REDACTED
    assert device["battery_charge"] == 99.0
    assert device["synced_at"] == "2026-10-19T14:31:31+00:00"
    assert "api_key" not in device
    assert result["devices"][1]["sleep_start_at"] == "22:30:00"
    assert [model["label"] for model in result["models"]] == [
        "TRMNL X",
        "TRMNL OG (1-bit)",
    ]

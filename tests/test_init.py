"""Tests for TRMNL Terminus setup, device registry and device lifecycle."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.trmnl_terminus.api import (
    TerminusAuthenticationError,
    TerminusConnectionError,
)
from custom_components.trmnl_terminus.const import DEFAULT_SCAN_INTERVAL, DOMAIN

from . import setup_integration


async def test_load_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """The entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (TerminusAuthenticationError("nope"), ConfigEntryState.SETUP_ERROR),
        (TerminusConnectionError("down"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Auth failures stop setup; connection failures retry."""
    mock_terminus_client.async_get_devices.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """An authentication failure starts a reauth flow."""
    mock_terminus_client.async_get_devices.side_effect = TerminusAuthenticationError(
        "nope"
    )
    await setup_integration(hass, mock_config_entry)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Devices carry label, model, firmware and MAC from Terminus."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_4"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "TRMNL"
    assert device.manufacturer == "TRMNL"
    assert device.model == "TRMNL X"
    assert device.sw_version == "1.8.10"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "02:a1:b2:c3:d4:e5")}
    assert device.configuration_url == "http://terminus.local:3000/devices/4"

    og = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_5"), mock_config_entry.entry_id
    )
    assert og is not None
    assert og.name == "Kitchen OG"
    assert og.model == "TRMNL OG (1-bit)"
    assert og.connections == set()


async def test_stale_device_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device that disappears from Terminus is removed from the registry."""
    await setup_integration(hass, mock_config_entry)
    identifier = (DOMAIN, f"{mock_config_entry.entry_id}_5")
    assert (
        device_registry.async_get_device_by_identifier(
            identifier, mock_config_entry.entry_id
        )
        is not None
    )

    mock_terminus_client.async_get_devices.return_value = (
        mock_terminus_client.async_get_devices.return_value[:1]
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            identifier, mock_config_entry.entry_id
        )
        is None
    )
    assert hass.states.get("sensor.kitchen_og_battery") is None


async def test_new_device_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device that appears in Terminus gets entities without a restart."""
    devices = mock_terminus_client.async_get_devices.return_value
    mock_terminus_client.async_get_devices.return_value = devices[:1]
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.kitchen_og_battery") is None

    mock_terminus_client.async_get_devices.return_value = devices
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.kitchen_og_battery") is not None
    assert hass.states.get("switch.kitchen_og_sleep_mode") is not None


async def test_update_failure_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed poll makes entities unavailable; the next success restores them."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.trmnl_battery").state == "99.0"

    mock_terminus_client.async_get_devices.side_effect = TerminusConnectionError("down")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.trmnl_battery").state == "unavailable"

    mock_terminus_client.async_get_devices.side_effect = None
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.trmnl_battery").state == "99.0"

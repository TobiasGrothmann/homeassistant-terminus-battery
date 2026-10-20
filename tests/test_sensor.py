"""Tests for the TRMNL Terminus sensors."""

from unittest.mock import AsyncMock

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import setup_integration


async def test_default_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Enabled-by-default sensors report Terminus values unchanged."""
    await setup_integration(hass, mock_config_entry)

    battery = hass.states.get("sensor.trmnl_battery")
    assert battery is not None
    assert battery.state == "99.0"
    assert battery.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert battery.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert battery.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    entry = entity_registry.async_get("sensor.trmnl_battery")
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_4_battery"

    assert hass.states.get("sensor.trmnl_signal_strength").state == "-53"
    assert (
        hass.states.get("sensor.trmnl_last_seen").state == "2026-10-19T14:31:31+00:00"
    )


async def test_unreported_battery_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """A device that never sent a percentage shows unknown, not 0 or a guess."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.kitchen_og_battery").state == STATE_UNKNOWN
    assert hass.states.get("sensor.kitchen_og_signal_strength").state == "-70"


async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Diagnostic extras exist in the registry but are disabled."""
    await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.trmnl_battery_voltage",
        "sensor.trmnl_wi_fi_band",
        "sensor.trmnl_firmware_version",
        "sensor.trmnl_wake_reason",
        "sensor.trmnl_refresh_rate",
        "sensor.trmnl_wake_duration",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None


async def test_enabled_voltage_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Once enabled, the voltage sensor reports the raw value."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "sensor",
        "trmnl_terminus",
        f"{mock_config_entry.entry_id}_5_battery_voltage",
        suggested_object_id="kitchen_og_battery_voltage",
        config_entry=mock_config_entry,
        disabled_by=None,
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.kitchen_og_battery_voltage")
    assert state is not None
    assert state.state == "3.9"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLTAGE

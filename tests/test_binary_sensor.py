"""Tests for the TRMNL Terminus binary sensors."""

from unittest.mock import AsyncMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import setup_integration


async def test_charging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """The charging sensor mirrors Terminus's charging flag."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.trmnl_charging")
    assert state is not None
    assert state.state == STATE_OFF
    assert (
        state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.BATTERY_CHARGING
    )

    assert hass.states.get("binary_sensor.kitchen_og_charging").state == STATE_ON

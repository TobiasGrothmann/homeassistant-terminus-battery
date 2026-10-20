"""Tests for the TRMNL Terminus sleep time entities."""

from datetime import time
from unittest.mock import AsyncMock

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import setup_integration


async def test_time_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Times are unknown without a schedule and reported otherwise."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("time.trmnl_sleep_start_time").state == STATE_UNKNOWN
    assert hass.states.get("time.trmnl_sleep_end_time").state == STATE_UNKNOWN
    assert hass.states.get("time.kitchen_og_sleep_start_time").state == "22:30:00"
    assert hass.states.get("time.kitchen_og_sleep_end_time").state == "06:30:00"


async def test_set_start_fills_missing_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Setting a start time on an unscheduled device adds the default stop."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.trmnl_sleep_start_time", ATTR_TIME: "21:00:00"},
        blocking=True,
    )

    mock_terminus_client.async_set_sleep.assert_awaited_once_with(
        4, time(21, 0), time(6, 0)
    )


async def test_set_stop_keeps_existing_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Setting the stop time keeps the device's current start time."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.kitchen_og_sleep_end_time", ATTR_TIME: "07:00:00"},
        blocking=True,
    )

    mock_terminus_client.async_set_sleep.assert_awaited_once_with(
        5, time(22, 30), time(7, 0)
    )

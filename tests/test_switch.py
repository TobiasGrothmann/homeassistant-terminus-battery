"""Tests for the TRMNL Terminus sleep mode switch."""

from datetime import time
from unittest.mock import AsyncMock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trmnl_terminus.api import TerminusError

from . import setup_integration


async def test_sleep_mode_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Sleep mode is on exactly when both times are set."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.trmnl_sleep_mode").state == STATE_OFF
    assert hass.states.get("switch.kitchen_og_sleep_mode").state == STATE_ON


async def test_turn_on_uses_defaults_when_never_scheduled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Turning on a device without a known schedule applies the defaults."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.trmnl_sleep_mode"},
        blocking=True,
    )

    mock_terminus_client.async_set_sleep.assert_awaited_once_with(
        4, time(22, 0), time(6, 0)
    )


async def test_turn_on_restores_last_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Turning on a device that had a schedule restores that schedule."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.kitchen_og_sleep_mode"},
        blocking=True,
    )

    mock_terminus_client.async_set_sleep.assert_awaited_once_with(
        5, time(22, 30), time(6, 30)
    )


async def test_turn_off_clears_both_times(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Turning off clears both times."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.kitchen_og_sleep_mode"},
        blocking=True,
    )

    mock_terminus_client.async_set_sleep.assert_awaited_once_with(5, None, None)


async def test_action_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_terminus_client: AsyncMock,
) -> None:
    """Terminus errors surface as Home Assistant errors."""
    await setup_integration(hass, mock_config_entry)
    mock_terminus_client.async_set_sleep.side_effect = TerminusError("boom")

    with pytest.raises(HomeAssistantError, match="boom"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.trmnl_sleep_mode"},
            blocking=True,
        )

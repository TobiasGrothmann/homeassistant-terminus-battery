"""Switch entities for the TRMNL Terminus integration."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TerminusConfigEntry, TerminusCoordinator
from .entity import TerminusEntity, exception_handler

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerminusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terminus switches based on a config entry."""
    coordinator = entry.runtime_data

    known_device_ids: set[int] = set()

    def _async_entity_listener() -> None:
        new_ids = set(coordinator.data.devices) - known_device_ids
        if new_ids:
            async_add_entities(
                TerminusSleepModeSwitch(coordinator, device_id) for device_id in new_ids
            )
            known_device_ids.update(new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class TerminusSleepModeSwitch(TerminusEntity, SwitchEntity):
    """Enable or disable the device's sleep schedule.

    Terminus has no explicit flag: sleep is on when both times are set.
    Turning on restores the last known schedule (or a default one); turning
    off clears both times.
    """

    _attr_translation_key = "sleep_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TerminusCoordinator, device_id: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("sleep_mode")

    @property
    @override
    def is_on(self) -> bool:
        """Return True when a sleep schedule is configured."""
        return self._device.sleep_enabled

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable sleep mode."""
        start, stop = self.coordinator.sleep_times_for(self._device_id)
        await self.coordinator.client.async_set_sleep(self._device_id, start, stop)
        await self.coordinator.async_request_refresh()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable sleep mode."""
        await self.coordinator.client.async_set_sleep(self._device_id, None, None)
        await self.coordinator.async_request_refresh()

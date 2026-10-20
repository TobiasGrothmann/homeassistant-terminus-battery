"""Time entities for the TRMNL Terminus integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import Any, override

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import TerminusDevice
from .coordinator import TerminusConfigEntry, TerminusCoordinator
from .entity import TerminusEntity, exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TerminusTimeEntityDescription(TimeEntityDescription):
    """Describes a Terminus time entity."""

    value_fn: Callable[[TerminusDevice], time | None]
    set_value_fn: Callable[
        [TerminusCoordinator, TerminusDevice, time], Coroutine[Any, Any, Any]
    ]


async def _set_sleep_start(
    coordinator: TerminusCoordinator, device: TerminusDevice, value: time
) -> None:
    """Set the sleep start, keeping (or defaulting) the stop time."""
    stop = device.sleep_stop_at or coordinator.sleep_times_for(device.id)[1]
    await coordinator.client.async_set_sleep(device.id, value, stop)


async def _set_sleep_stop(
    coordinator: TerminusCoordinator, device: TerminusDevice, value: time
) -> None:
    """Set the sleep stop, keeping (or defaulting) the start time."""
    start = device.sleep_start_at or coordinator.sleep_times_for(device.id)[0]
    await coordinator.client.async_set_sleep(device.id, start, value)


TIME_DESCRIPTIONS: tuple[TerminusTimeEntityDescription, ...] = (
    TerminusTimeEntityDescription(
        key="sleep_start",
        translation_key="sleep_start",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.sleep_start_at,
        set_value_fn=_set_sleep_start,
    ),
    TerminusTimeEntityDescription(
        key="sleep_stop",
        translation_key="sleep_stop",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.sleep_stop_at,
        set_value_fn=_set_sleep_stop,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerminusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terminus time entities based on a config entry."""
    coordinator = entry.runtime_data

    known_device_ids: set[int] = set()

    def _async_entity_listener() -> None:
        new_ids = set(coordinator.data.devices) - known_device_ids
        if new_ids:
            async_add_entities(
                TerminusTimeEntity(coordinator, device_id, description)
                for device_id in new_ids
                for description in TIME_DESCRIPTIONS
            )
            known_device_ids.update(new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class TerminusTimeEntity(TerminusEntity, TimeEntity):
    """Defines a Terminus time entity."""

    entity_description: TerminusTimeEntityDescription

    def __init__(
        self,
        coordinator: TerminusCoordinator,
        device_id: int,
        description: TerminusTimeEntityDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = self._unique_id(description.key)

    @property
    @override
    def native_value(self) -> time | None:
        """Return the current value, or None when no schedule is set."""
        return self.entity_description.value_fn(self._device)

    @exception_handler
    @override
    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        await self.entity_description.set_value_fn(
            self.coordinator, self._device, value
        )
        await self.coordinator.async_request_refresh()

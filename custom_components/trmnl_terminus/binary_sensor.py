"""Binary sensors for the TRMNL Terminus integration."""

from __future__ import annotations

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TerminusConfigEntry, TerminusCoordinator
from .entity import TerminusEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerminusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terminus binary sensors based on a config entry."""
    coordinator = entry.runtime_data

    known_device_ids: set[int] = set()

    def _async_entity_listener() -> None:
        new_ids = set(coordinator.data.devices) - known_device_ids
        if new_ids:
            async_add_entities(
                TerminusChargingSensor(coordinator, device_id) for device_id in new_ids
            )
            known_device_ids.update(new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class TerminusChargingSensor(TerminusEntity, BinarySensorEntity):
    """Whether the device reports that it is charging (USB connected)."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TerminusCoordinator, device_id: int) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("charging")

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when charging."""
        return self._device.charging

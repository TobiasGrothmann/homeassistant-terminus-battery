"""Sensors for the TRMNL Terminus integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import TerminusDevice
from .coordinator import TerminusConfigEntry, TerminusCoordinator
from .entity import TerminusEntity

PARALLEL_UPDATES = 0


def _reported(value: float | int | None) -> float | int | None:
    """Return a numeric reading, or None when Terminus holds its 0 default.

    Terminus stores 0 for readings a device has never sent (battery charge on
    devices without a gas gauge, voltage, RSSI, Wi-Fi band). A reported value
    of exactly 0 is not meaningful for any of these, so it maps to unknown.
    """
    return value if value else None


@dataclass(frozen=True, kw_only=True)
class TerminusSensorEntityDescription(SensorEntityDescription):
    """Describes a Terminus sensor entity."""

    value_fn: Callable[[TerminusDevice], StateType | datetime]


SENSOR_DESCRIPTIONS: tuple[TerminusSensorEntityDescription, ...] = (
    TerminusSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda device: _reported(device.battery_charge),
    ),
    TerminusSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: _reported(device.battery_voltage),
    ),
    TerminusSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: _reported(device.wifi_signal),
    ),
    TerminusSensorEntityDescription(
        key="wifi_band",
        translation_key="wifi_band",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.GIGAHERTZ,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
        value_fn=lambda device: _reported(device.wifi_band),
    ),
    TerminusSensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.synced_at,
    ),
    TerminusSensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.firmware_version,
    ),
    TerminusSensorEntityDescription(
        key="wake_reason",
        translation_key="wake_reason",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.wake_reason,
    ),
    TerminusSensorEntityDescription(
        key="refresh_rate",
        translation_key="refresh_rate",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.refresh_rate,
    ),
    TerminusSensorEntityDescription(
        key="wake_duration",
        translation_key="wake_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.wake_duration,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerminusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terminus sensors based on a config entry."""
    coordinator = entry.runtime_data

    known_device_ids: set[int] = set()

    def _async_entity_listener() -> None:
        new_ids = set(coordinator.data.devices) - known_device_ids
        if new_ids:
            async_add_entities(
                TerminusSensor(coordinator, device_id, description)
                for device_id in new_ids
                for description in SENSOR_DESCRIPTIONS
            )
            known_device_ids.update(new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class TerminusSensor(TerminusEntity, SensorEntity):
    """Defines a Terminus sensor."""

    entity_description: TerminusSensorEntityDescription

    def __init__(
        self,
        coordinator: TerminusCoordinator,
        device_id: int,
        description: TerminusSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = self._unique_id(description.key)

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)

"""Base entity for the TRMNL Terminus integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, override

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import TerminusDevice, TerminusError
from .const import DOMAIN, MANUFACTURER
from .coordinator import TerminusCoordinator


class TerminusEntity(CoordinatorEntity[TerminusCoordinator]):
    """Defines a base Terminus entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TerminusCoordinator, device_id: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        device = self._device
        model = (
            coordinator.data.models.get(device.model_id)
            if device.model_id is not None
            else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_identifier(device_id))},
            connections=(
                {(CONNECTION_NETWORK_MAC, device.mac_address)}
                if device.mac_address
                else set()
            ),
            name=device.label or f"TRMNL {device.id}",
            manufacturer=MANUFACTURER,
            model=model.label if model else None,
            sw_version=device.firmware_version,
            configuration_url=f"{coordinator.client.url}/devices/{device.id}",
        )

    @property
    def _device(self) -> TerminusDevice:
        """Return the device from coordinator data."""
        return self.coordinator.data.devices[self._device_id]

    @property
    @override
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self._device_id in self.coordinator.data.devices

    def _unique_id(self, key: str) -> str:
        """Return a unique id for an entity key of this device."""
        return f"{self.coordinator.device_identifier(self._device_id)}_{key}"


def exception_handler[EntityT: TerminusEntity, **P](
    func: Callable[Concatenate[EntityT, P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[EntityT, P], Coroutine[Any, Any, None]]:
    """Translate Terminus errors raised by entity actions into HA errors."""

    async def handler(self: EntityT, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except TerminusError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler

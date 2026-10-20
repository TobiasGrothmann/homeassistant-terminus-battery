"""Data update coordinator for the TRMNL Terminus integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TerminusAuthenticationError,
    TerminusClient,
    TerminusDevice,
    TerminusError,
    TerminusModel,
)
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLEEP_START,
    DEFAULT_SLEEP_STOP,
    DOMAIN,
    LOGGER,
)

type TerminusConfigEntry = ConfigEntry[TerminusCoordinator]


@dataclass
class TerminusData:
    """Coordinator data."""

    devices: dict[int, TerminusDevice]
    models: dict[int, TerminusModel]


class TerminusCoordinator(DataUpdateCoordinator[TerminusData]):
    """Fetch devices (and, when needed, models) from Terminus."""

    config_entry: TerminusConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: TerminusConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = TerminusClient(
            url=config_entry.data[CONF_URL],
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            session=async_get_clientsession(hass),
        )
        self._models: dict[int, TerminusModel] = {}
        # Last schedule seen per device, restored when sleep mode is re-enabled.
        self.last_sleep_times: dict[int, tuple[time, time]] = {}

    def device_identifier(self, device_id: int) -> str:
        """Return the device registry identifier for a Terminus device."""
        return f"{self.config_entry.entry_id}_{device_id}"

    def sleep_times_for(self, device_id: int) -> tuple[time, time]:
        """Return the schedule to apply when enabling sleep for a device."""
        return self.last_sleep_times.get(
            device_id, (DEFAULT_SLEEP_START, DEFAULT_SLEEP_STOP)
        )

    @override
    async def _async_update_data(self) -> TerminusData:
        """Fetch data from Terminus."""
        try:
            devices = await self.client.async_get_devices()
            unknown_models = {
                device.model_id
                for device in devices
                if device.model_id is not None and device.model_id not in self._models
            }
            if unknown_models or not self._models:
                models = await self.client.async_get_models()
                self._models = {model.id: model for model in models}
        except TerminusAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from err
        except TerminusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        new_data = {device.id: device for device in devices}
        for device in devices:
            if device.sleep_start_at is not None and device.sleep_stop_at is not None:
                self.last_sleep_times[device.id] = (
                    device.sleep_start_at,
                    device.sleep_stop_at,
                )

        if self.data is not None:
            device_registry = dr.async_get(self.hass)
            for device_id in set(self.data.devices) - set(new_data):
                if entry := device_registry.async_get_device_by_identifier(
                    (DOMAIN, self.device_identifier(device_id)),
                    self.config_entry.entry_id,
                ):
                    device_registry.async_remove_device(entry.id)

        return TerminusData(devices=new_data, models=dict(self._models))

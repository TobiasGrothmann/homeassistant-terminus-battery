"""Diagnostics support for the TRMNL Terminus integration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import TerminusConfigEntry

TO_REDACT = {CONF_PASSWORD, "mac_address"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, time)):
        return value.isoformat()
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TerminusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": [
            async_redact_data(
                {key: _jsonable(value) for key, value in asdict(device).items()},
                TO_REDACT,
            )
            for device in coordinator.data.devices.values()
        ],
        "models": [asdict(model) for model in coordinator.data.models.values()],
    }

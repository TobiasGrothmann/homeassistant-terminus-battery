"""Tests for the TRMNL Terminus integration."""

from pathlib import Path

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Return the contents of a fixture file."""
    return (FIXTURES / name).read_text()


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add a config entry and set it up."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

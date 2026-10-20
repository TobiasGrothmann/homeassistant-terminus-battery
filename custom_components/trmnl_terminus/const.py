"""Constants for the TRMNL Terminus integration."""

from datetime import time, timedelta
import logging

DOMAIN = "trmnl_terminus"

LOGGER = logging.getLogger(__package__)

MANUFACTURER = "TRMNL"

# Devices check in every `refresh_rate` seconds (60 s on a TRMNL X by
# default), so a short poll keeps the battery reading current.
DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)

# Terminus requires both sleep times to be set together. When sleep mode is
# switched on for a device that never had a schedule, these are used.
DEFAULT_SLEEP_START = time(hour=22, minute=0)
DEFAULT_SLEEP_STOP = time(hour=6, minute=0)

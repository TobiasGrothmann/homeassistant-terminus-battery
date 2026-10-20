"""Minimal asynchronous client for the Terminus (TRMNL BYOS) server API.

Terminus authenticates server-side API calls with a JWT obtained from
``POST /login`` (email + password). Access tokens expire (30 minutes by
default), so the client logs in lazily and transparently re-logs in once
when the token is rejected (401, or 400 with an "expired JWT" body).

Only the endpoints this integration needs are implemented:

* ``GET  /api/devices``
* ``GET  /api/models``
* ``PATCH /api/devices/:id``
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, time
import socket
from typing import Any, Self

from aiohttp import ClientError, ClientResponse, ClientSession
from aiohttp.hdrs import METH_GET, METH_PATCH, METH_POST
from yarl import URL

from .const import LOGGER

USER_AGENT = "HomeAssistant-trmnl_terminus"


class TerminusError(Exception):
    """Generic Terminus error."""


class TerminusConnectionError(TerminusError):
    """Terminus could not be reached."""


class TerminusAuthenticationError(TerminusError):
    """Login credentials or access token were rejected."""


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_time(value: Any) -> time | None:
    """Parse Terminus ``HH:MM:SS`` strings."""
    if not value:
        return None
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """Parse Terminus ISO 8601 timestamps."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def format_time(value: time | None) -> str | None:
    """Serialize a time for the Terminus API."""
    return value.strftime("%H:%M:%S") if value is not None else None


@dataclass(frozen=True, kw_only=True)
class TerminusDevice:
    """A device as reported by ``GET /api/devices``.

    Values are passed through as Terminus reports them. Nothing is derived
    or estimated here. ``battery_charge`` is the percentage the device
    itself reports (TRMNL X gas gauge); devices that do not report it leave
    it at Terminus's default of ``0.0``.
    """

    id: int
    label: str | None
    mac_address: str | None
    model_id: int | None
    playlist_id: int | None
    firmware_version: str | None
    firmware_update: bool | None
    battery_charge: float | None
    battery_voltage: float | None
    charging: bool | None
    wifi_signal: int | None
    wifi_band: float | None
    refresh_rate: int | None
    wake_reason: str | None
    wake_duration: int | None
    width: int | None
    height: int | None
    sleep_start_at: time | None
    sleep_stop_at: time | None
    synced_at: datetime | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build a device from an API payload."""
        return cls(
            id=int(data["id"]),
            label=_as_str(data.get("label")),
            mac_address=_as_str(data.get("mac_address")),
            model_id=_as_int(data.get("model_id")),
            playlist_id=_as_int(data.get("playlist_id")),
            firmware_version=_as_str(data.get("firmware_version")),
            firmware_update=_as_bool(data.get("firmware_update")),
            battery_charge=_as_float(data.get("battery_charge")),
            battery_voltage=_as_float(data.get("battery_voltage")),
            charging=_as_bool(data.get("charging")),
            wifi_signal=_as_int(data.get("wifi_signal")),
            wifi_band=_as_float(data.get("wifi_band")),
            refresh_rate=_as_int(data.get("refresh_rate")),
            wake_reason=_as_str(data.get("wake_reason")),
            wake_duration=_as_int(data.get("wake_duration")),
            width=_as_int(data.get("width")),
            height=_as_int(data.get("height")),
            sleep_start_at=_parse_time(data.get("sleep_start_at")),
            sleep_stop_at=_parse_time(data.get("sleep_stop_at")),
            synced_at=_parse_datetime(data.get("synced_at")),
        )

    @property
    def sleep_enabled(self) -> bool:
        """Return True when a sleep schedule is configured.

        Terminus has no separate flag; sleep is active when both times exist.
        """
        return self.sleep_start_at is not None and self.sleep_stop_at is not None


@dataclass(frozen=True, kw_only=True)
class TerminusModel:
    """A device model as reported by ``GET /api/models``."""

    id: int
    name: str | None
    label: str | None
    kind: str | None
    width: int | None
    height: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Build a model from an API payload."""
        return cls(
            id=int(data["id"]),
            name=_as_str(data.get("name")),
            label=_as_str(data.get("label")),
            kind=_as_str(data.get("kind")),
            width=_as_int(data.get("width")),
            height=_as_int(data.get("height")),
        )


def normalize_url(url: str) -> str:
    """Normalize a user supplied server URL to ``scheme://host[:port]``.

    Raises ValueError when the URL is unusable.
    """
    url = url.strip()
    if "://" not in url:
        url = f"http://{url}"
    parsed = URL(url)
    if parsed.scheme not in ("http", "https") or not parsed.host:
        raise ValueError(f"Invalid Terminus URL: {url}")
    return str(parsed.with_path("").with_query(None).with_fragment(None)).rstrip("/")


class TerminusClient:
    """Client for the Terminus server API."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        session: ClientSession,
        *,
        request_timeout: float = 15,
    ) -> None:
        """Initialize the client. ``url`` must already be normalized."""
        self.url = url
        self._username = username
        self._password = password
        self._session = session
        self._request_timeout = request_timeout
        self._token: str | None = None
        self._login_lock = asyncio.Lock()

    async def async_login(self) -> None:
        """Obtain an access token. No-op when a token is already held."""
        async with self._login_lock:
            if self._token is not None:
                return
            response = await self._raw_request(
                METH_POST,
                "/login",
                json={"login": self._username, "password": self._password},
                authenticated=False,
            )
            if response.status in (400, 401, 403):
                raise TerminusAuthenticationError(
                    "Terminus rejected the login credentials"
                )
            if response.status >= 400:
                raise TerminusError(f"Login failed with HTTP status {response.status}")
            data = await self._read_json(response)
            token = data.get("access_token") if isinstance(data, dict) else None
            if not token:
                token = _token_from_header(response)
            if not token:
                raise TerminusError("Login response did not contain an access token")
            self._token = token

    async def async_get_devices(self) -> list[TerminusDevice]:
        """Return all devices."""
        data = await self._request(METH_GET, "/api/devices")
        return [TerminusDevice.from_dict(item) for item in _data_list(data)]

    async def async_get_models(self) -> list[TerminusModel]:
        """Return all device models."""
        data = await self._request(METH_GET, "/api/models")
        return [TerminusModel.from_dict(item) for item in _data_list(data)]

    async def async_update_device(
        self, device_id: int, **fields: Any
    ) -> TerminusDevice:
        """Patch device attributes and return the updated device."""
        data = await self._request(
            METH_PATCH, f"/api/devices/{device_id}", json={"device": fields}
        )
        if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
            raise TerminusError("Unexpected response from Terminus device update")
        return TerminusDevice.from_dict(data["data"])

    async def async_set_sleep(
        self, device_id: int, start: time | None, stop: time | None
    ) -> TerminusDevice:
        """Set or clear the sleep schedule. Terminus needs both or neither."""
        return await self.async_update_device(
            device_id,
            sleep_start_at=format_time(start),
            sleep_stop_at=format_time(stop),
        )

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        """Perform an authenticated request, re-logging in once on a bad token."""
        if self._token is None:
            await self.async_login()
        response = await self._raw_request(method, path, json=json)
        if await _token_rejected(response):
            LOGGER.debug("Terminus rejected the access token, logging in again")
            self._token = None
            await self.async_login()
            response = await self._raw_request(method, path, json=json)
            if await _token_rejected(response):
                raise TerminusAuthenticationError(
                    "Terminus rejected the access token after a fresh login"
                )
        if response.status >= 400:
            body = (await response.text())[:300]
            raise TerminusError(
                f"{method} {path} failed with HTTP status {response.status}: {body}"
            )
        if (token := _token_from_header(response)) is not None:
            self._token = token
        return await self._read_json(response)

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> ClientResponse:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        if authenticated:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with asyncio.timeout(self._request_timeout):
                return await self._session.request(
                    method, f"{self.url}{path}", headers=headers, json=json
                )
        except (TimeoutError, ClientError, socket.gaierror) as err:
            raise TerminusConnectionError(
                f"Error communicating with Terminus at {self.url}: {err}"
            ) from err

    async def _read_json(self, response: ClientResponse) -> Any:
        try:
            return await response.json(content_type=None)
        except (ValueError, ClientError) as err:
            raise TerminusError(
                "Terminus returned a response that is not JSON"
            ) from err


async def _token_rejected(response: ClientResponse) -> bool:
    """Return True when Terminus rejected the access token.

    Terminus answers a missing or invalid token with 401, but an expired one
    with 400 and ``{"error":"expired JWT access token"}``.
    """
    if response.status == 401:
        return True
    if response.status == 400:
        return "jwt" in (await response.text()).lower()
    return False


def _token_from_header(response: ClientResponse) -> str | None:
    """Return a token echoed in the Authorization response header, if any."""
    header = response.headers.get("Authorization")
    if not header:
        return None
    return header.removeprefix("Bearer").strip() or None


def _data_list(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise TerminusError("Unexpected response from Terminus")
    return [item for item in data["data"] if isinstance(item, dict)]

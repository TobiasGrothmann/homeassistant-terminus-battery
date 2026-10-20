"""Tests for the Terminus API client (no network, fake aiohttp session)."""

from __future__ import annotations

from datetime import UTC, datetime, time
import json
from typing import Any

from aiohttp import ClientError
import pytest

from custom_components.trmnl_terminus.api import (
    TerminusAuthenticationError,
    TerminusClient,
    TerminusConnectionError,
    TerminusError,
    normalize_url,
)

from . import load_fixture

URL = "http://terminus.local:3000"
LOGIN_OK = {
    "access_token": "token-1",
    "refresh_token": "refresh-1",
    "success": "You have been logged in.",
}


class FakeResponse:
    """Minimal stand-in for aiohttp.ClientResponse."""

    def __init__(
        self,
        status: int,
        body: Any = None,
        *,
        headers: dict[str, str] | None = None,
        raw_text: str | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}
        self._raw_text = raw_text

    async def json(self, content_type: str | None = None) -> Any:
        if self._raw_text is not None:
            return json.loads(self._raw_text)
        return self._body

    async def text(self) -> str:
        if self._raw_text is not None:
            return self._raw_text
        return json.dumps(self._body)


class FakeSession:
    """Replays canned responses and records requests."""

    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, str], Any]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any = None,
    ) -> FakeResponse:
        self.calls.append((method, url, headers or {}, json))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_client(
    responses: list[FakeResponse | Exception],
) -> tuple[TerminusClient, FakeSession]:
    session = FakeSession(responses)
    client = TerminusClient(URL, "user@example.com", "secret", session)  # type: ignore[arg-type]
    return client, session


def devices_payload() -> dict[str, Any]:
    return json.loads(load_fixture("devices.json"))


async def test_login_and_get_devices() -> None:
    """Login happens lazily; devices are parsed as reported."""
    client, session = make_client(
        [FakeResponse(200, LOGIN_OK), FakeResponse(200, devices_payload())]
    )

    devices = await client.async_get_devices()

    assert [call[0:2] for call in session.calls] == [
        ("POST", f"{URL}/login"),
        ("GET", f"{URL}/api/devices"),
    ]
    login_call = session.calls[0]
    assert login_call[3] == {"login": "user@example.com", "password": "secret"}
    assert "Authorization" not in login_call[2]
    assert login_call[2]["User-Agent"]
    assert session.calls[1][2]["Authorization"] == "Bearer token-1"

    assert len(devices) == 2
    x = devices[0]
    assert x.id == 4
    assert x.label == "TRMNL"
    assert x.battery_charge == 99.0
    assert x.battery_voltage == 3.37
    assert x.charging is False
    assert x.wifi_signal == -53
    assert x.sleep_start_at is None
    assert x.sleep_enabled is False
    assert x.synced_at == datetime(2026, 10, 19, 14, 31, 31, tzinfo=UTC)

    og = devices[1]
    assert og.mac_address is None
    assert og.battery_charge == 0.0
    assert og.sleep_start_at == time(22, 30)
    assert og.sleep_stop_at == time(6, 30)
    assert og.sleep_enabled is True


async def test_login_rejected() -> None:
    """A rejected login raises an authentication error."""
    client, _ = make_client(
        [FakeResponse(401, {"error": "There was an error signing in."})]
    )
    with pytest.raises(TerminusAuthenticationError):
        await client.async_get_devices()


async def test_login_without_token() -> None:
    """A login response without a token is an error."""
    client, _ = make_client([FakeResponse(200, {"success": "ok"})])
    with pytest.raises(TerminusError):
        await client.async_login()


async def test_expired_token_triggers_single_relogin() -> None:
    """A 401 on an API call logs in again once and retries."""
    client, session = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(
                401, raw_text='["{\\"error\\":\\"Please log in to continue.\\"}"]'
            ),
            FakeResponse(200, {**LOGIN_OK, "access_token": "token-2"}),
            FakeResponse(200, devices_payload()),
        ]
    )

    devices = await client.async_get_devices()

    assert len(devices) == 2
    assert [call[0] for call in session.calls] == ["POST", "GET", "POST", "GET"]
    assert session.calls[3][2]["Authorization"] == "Bearer token-2"


async def test_expired_jwt_400_triggers_relogin() -> None:
    """Terminus answers an expired token with 400; that also re-logs in."""
    client, session = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(400, raw_text='{"error":"expired JWT access token"}'),
            FakeResponse(200, {**LOGIN_OK, "access_token": "token-2"}),
            FakeResponse(200, devices_payload()),
        ]
    )

    devices = await client.async_get_devices()

    assert len(devices) == 2
    assert [call[0] for call in session.calls] == ["POST", "GET", "POST", "GET"]
    assert session.calls[3][2]["Authorization"] == "Bearer token-2"


async def test_expired_jwt_after_relogin_is_auth_error() -> None:
    """An expired-token 400 right after a fresh login is an auth error."""
    expired = '{"error":"expired JWT access token"}'
    client, _ = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(400, raw_text=expired),
            FakeResponse(200, LOGIN_OK),
            FakeResponse(400, raw_text=expired),
        ]
    )
    with pytest.raises(TerminusAuthenticationError):
        await client.async_get_devices()


async def test_other_400_is_not_relogin() -> None:
    """A 400 unrelated to the token is a plain error without a re-login."""
    client, session = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(400, raw_text='{"error":"bad request"}'),
        ]
    )
    with pytest.raises(TerminusError, match="400"):
        await client.async_get_devices()
    assert [call[0] for call in session.calls] == ["POST", "GET"]


async def test_relogin_still_rejected() -> None:
    """A 401 after a fresh login is an authentication error."""
    client, _ = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(401, {}),
            FakeResponse(200, LOGIN_OK),
            FakeResponse(401, {}),
        ]
    )
    with pytest.raises(TerminusAuthenticationError):
        await client.async_get_devices()


async def test_server_error() -> None:
    """Non-auth HTTP errors raise a generic error with the status."""
    client, _ = make_client(
        [FakeResponse(200, LOGIN_OK), FakeResponse(503, raw_text="Server Error")]
    )
    with pytest.raises(TerminusError, match="503"):
        await client.async_get_devices()


async def test_connection_error() -> None:
    """Transport errors raise a connection error."""
    client, _ = make_client([ClientError("boom")])
    with pytest.raises(TerminusConnectionError):
        await client.async_get_devices()


async def test_unexpected_payload() -> None:
    """A payload without a data list is an error."""
    client, _ = make_client(
        [FakeResponse(200, LOGIN_OK), FakeResponse(200, {"nope": 1})]
    )
    with pytest.raises(TerminusError):
        await client.async_get_devices()


async def test_token_echoed_in_header_is_adopted() -> None:
    """A rotated token in the Authorization response header is used."""
    client, session = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(
                200,
                devices_payload(),
                headers={"Authorization": "Bearer token-rotated"},
            ),
            FakeResponse(200, devices_payload()),
        ]
    )
    await client.async_get_devices()
    await client.async_get_devices()
    assert session.calls[2][2]["Authorization"] == "Bearer token-rotated"


async def test_set_sleep_payload() -> None:
    """Sleep times are sent as HH:MM:SS, or null to clear."""
    device = devices_payload()["data"][0]
    client, session = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(
                200,
                {
                    "data": {
                        **device,
                        "sleep_start_at": "22:00:00",
                        "sleep_stop_at": "06:00:00",
                    }
                },
            ),
            FakeResponse(200, {"data": device}),
        ]
    )

    updated = await client.async_set_sleep(4, time(22, 0), time(6, 0))
    assert updated.sleep_start_at == time(22, 0)
    assert session.calls[1][0:2] == ("PATCH", f"{URL}/api/devices/4")
    assert session.calls[1][3] == {
        "device": {"sleep_start_at": "22:00:00", "sleep_stop_at": "06:00:00"}
    }

    cleared = await client.async_set_sleep(4, None, None)
    assert cleared.sleep_enabled is False
    assert session.calls[2][3] == {
        "device": {"sleep_start_at": None, "sleep_stop_at": None}
    }


async def test_get_models() -> None:
    """Models are parsed."""
    client, _ = make_client(
        [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(200, json.loads(load_fixture("models.json"))),
        ]
    )
    models = await client.async_get_models()
    assert [(m.id, m.label) for m in models] == [
        (1, "TRMNL X"),
        (2, "TRMNL OG (1-bit)"),
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://terminus.local:3000", "http://terminus.local:3000"),
        ("terminus.local:3000", "http://terminus.local:3000"),
        ("  https://terminus.example.org/  ", "https://terminus.example.org"),
        ("http://192.168.1.10:3000/devices?x=1#top", "http://192.168.1.10:3000"),
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    """URLs are reduced to scheme, host and port."""
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "ftp://nope", "http://"])
def test_normalize_url_invalid(raw: str) -> None:
    """Unusable URLs are rejected."""
    with pytest.raises(ValueError):
        normalize_url(raw)

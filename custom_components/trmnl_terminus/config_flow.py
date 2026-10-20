"""Config flow for the TRMNL Terminus integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import probatio
from yarl import URL

from .api import (
    TerminusAuthenticationError,
    TerminusClient,
    TerminusError,
    normalize_url,
)
from .const import DOMAIN, LOGGER

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        probatio.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class TerminusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for a Terminus server."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user, reauth and reconfigure steps (same form)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
            except ValueError:
                errors[CONF_URL] = "invalid_url"
            else:
                data = {
                    CONF_URL: url,
                    CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                errors = await self._async_validate(data)
                if not errors:
                    return await self._async_finish(data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, self._suggested_values(user_input)
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication after Terminus rejected the credentials."""
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration (server URL or credentials)."""
        return await self.async_step_user()

    async def _async_validate(self, data: dict[str, Any]) -> dict[str, str]:
        """Log in and list devices; return form errors if that fails."""
        client = TerminusClient(
            data[CONF_URL],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            async_get_clientsession(self.hass),
        )
        try:
            await client.async_login()
            await client.async_get_devices()
        except TerminusAuthenticationError:
            return {"base": "invalid_auth"}
        except TerminusError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error while validating Terminus connection")
            return {"base": "unknown"}
        return {}

    async def _async_finish(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the config entry."""
        url = data[CONF_URL]
        existing = await self.async_set_unique_id(url)

        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            entry = (
                self._get_reauth_entry()
                if self.source == SOURCE_REAUTH
                else self._get_reconfigure_entry()
            )
            if existing is not None and existing.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")
            return self.async_update_reload_and_abort(
                entry, data_updates=data, unique_id=url
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Terminus ({URL(url).host})",
            data=data,
        )

    def _suggested_values(self, user_input: dict[str, Any] | None) -> dict[str, Any]:
        """Pre-fill URL and email from the previous attempt or the entry."""
        if user_input is not None:
            return {
                CONF_URL: user_input.get(CONF_URL, ""),
                CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
            }
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
        elif self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
        else:
            return {}
        return {
            CONF_URL: entry.data[CONF_URL],
            CONF_USERNAME: entry.data[CONF_USERNAME],
        }

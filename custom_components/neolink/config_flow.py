"""Config flow: app discovery through the Supervisor or a manual bridge address."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import SOURCE_HASSIO, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
import voluptuous as vol

from .api import NeolinkAuthError, NeolinkClient, NeolinkError
from .const import (
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PORT,
    CONF_RTSP_USERNAME,
    DEFAULT_PORT,
    DEFAULT_RTSP_PORT,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_TOKEN, default=""): str,
        vol.Required(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): int,
        vol.Optional(CONF_RTSP_USERNAME, default=""): str,
        vol.Optional(CONF_RTSP_PASSWORD, default=""): str,
    }
)


class NeolinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Neolink bridge."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}

    async def _validate(self, data: dict[str, Any]) -> str | None:
        client = NeolinkClient(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_PORT],
            data.get(CONF_TOKEN),
        )
        try:
            await client.connect()
        except NeolinkAuthError:
            return "invalid_auth"
        except NeolinkError:
            return "cannot_connect"
        finally:
            await client.close()
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            if (error := await self._validate(user_input)) is None:
                return self.async_create_entry(
                    title=f"Neolink ({user_input[CONF_HOST]})", data=user_input
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Neolink app discovery: host, ports, token and RTSP credentials."""
        config = discovery_info.config
        data = {
            CONF_HOST: config["host"],
            CONF_PORT: int(config["port"]),
            CONF_TOKEN: config.get("token", ""),
            CONF_RTSP_PORT: int(config.get("rtsp_port", DEFAULT_RTSP_PORT)),
            CONF_RTSP_USERNAME: config.get("rtsp_username", ""),
            CONF_RTSP_PASSWORD: config.get("rtsp_password", ""),
        }
        await self.async_set_unique_id(discovery_info.uuid)
        # After a restart the app may have a new address or token: update the existing entry.
        self._abort_if_unique_id_configured(updates=data)
        # A reinstalled app (e.g. a local copy replaced by the store version) announces itself
        # with a new discovery id: take over the entry it replaces so devices and entity ids stay.
        for entry in self._async_current_entries(include_ignore=False):
            if entry.source == SOURCE_HASSIO:
                self.hass.config_entries.async_update_entry(
                    entry, unique_id=discovery_info.uuid, data={**entry.data, **data}
                )
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")
        self._discovered = data
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if (error := await self._validate(self._discovered)) is None:
                return self.async_create_entry(title="Neolink", data=self._discovered)
            errors["base"] = error
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"host": self._discovered[CONF_HOST]},
            errors=errors,
        )

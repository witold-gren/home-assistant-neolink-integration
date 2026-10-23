"""Neolink: Reolink battery and 4G cameras through the Neolink bridge WebSocket API."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NeolinkAuthError, NeolinkClient, NeolinkError

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class NeolinkData:
    """Config entry runtime data."""

    client: NeolinkClient


type NeolinkConfigEntry = ConfigEntry[NeolinkData]


async def async_setup_entry(hass: HomeAssistant, entry: NeolinkConfigEntry) -> bool:
    """Connect to the bridge and create entities for the cameras in its hello."""
    client = NeolinkClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_TOKEN),
    )
    try:
        await client.connect()
    except NeolinkAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except NeolinkError as err:
        raise ConfigEntryNotReady(str(err)) from err
    entry.runtime_data = NeolinkData(client)
    entry.async_on_unload(client.close)

    # A camera added to or removed from the app reloads the entry, so entities are recreated.
    names = set(client.cameras)

    @callback
    def _check_cameras() -> None:
        if client.connected and set(client.cameras) != names:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(client.add_listener(_check_cameras))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeolinkConfigEntry) -> bool:
    """Unload platforms; the client is closed via async_on_unload."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

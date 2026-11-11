"""Siren: on until switched off, or for a duration (the bridge switches it off by itself)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.siren import ATTR_DURATION, SirenEntity, SirenEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient
from .const import SIREN_SECONDS
from .entity import NeolinkEntity

# The longest siren the bridge accepts.
MAX_SECONDS = 900


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    # Only a bridge that reports `siren_on` (0.3.0 and later) switches the siren on and off.
    async_add_entities(
        NeolinkSiren(client, name) for name, state in client.cameras.items() if "siren_on" in state
    )


def siren_seconds(duration: Any) -> int:
    """Seconds asked for, kept within what the bridge accepts (default 30)."""
    try:
        seconds = int(duration)
    except (TypeError, ValueError):
        return SIREN_SECONDS
    return min(max(seconds, 1), MAX_SECONDS)


class NeolinkSiren(NeolinkEntity, SirenEntity):
    """The camera's siren."""

    _attr_translation_key = "siren"
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF | SirenEntityFeature.DURATION
    )

    def __init__(self, client: NeolinkClient, camera: str) -> None:
        super().__init__(client, camera, "siren_switch")

    @property
    def is_on(self) -> bool | None:
        return self.state_data.get("siren_on")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._command("siren", on=True, seconds=siren_seconds(kwargs.get(ATTR_DURATION)))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._command("siren", on=False)

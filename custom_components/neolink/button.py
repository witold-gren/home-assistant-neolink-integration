"""Restart, siren, state refresh, snapshot and the copy of the SD card (these wake the camera)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient
from .const import SYNC_HOURS
from .entity import NeolinkEntity


@dataclass(frozen=True, kw_only=True)
class NeolinkButtonDescription(ButtonEntityDescription):
    """A bridge command (`key`, or `command`) with its arguments."""

    command: str | None = None
    args: dict[str, Any] | None = None
    supported: Callable[[dict[str, Any]], bool] = lambda _: True


BUTTONS: tuple[NeolinkButtonDescription, ...] = (
    NeolinkButtonDescription(
        key="reboot", device_class=ButtonDeviceClass.RESTART, entity_category=EntityCategory.CONFIG
    ),
    NeolinkButtonDescription(key="siren", translation_key="siren"),
    # The only way to get a fresh still from a sleeping camera; the camera entity then serves it
    # from the cache.
    NeolinkButtonDescription(key="snapshot", translation_key="snapshot"),
    NeolinkButtonDescription(
        key="refresh", translation_key="refresh", entity_category=EntityCategory.DIAGNOSTIC
    ),
    # Copies the recordings of the SD card the recording folder lacks (bridge 0.3.0 and later).
    NeolinkButtonDescription(
        key="sd_sync",
        translation_key="sd_sync",
        args={"hours": SYNC_HOURS},
        supported=lambda s: "sd_sync" in s,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    async_add_entities(
        NeolinkButton(client, name, description)
        for name, state in client.cameras.items()
        for description in BUTTONS
        if description.supported(state)
    )


class NeolinkButton(NeolinkEntity, ButtonEntity):
    """One-shot command."""

    entity_description: NeolinkButtonDescription

    def __init__(
        self, client: NeolinkClient, camera: str, description: NeolinkButtonDescription
    ) -> None:
        super().__init__(client, camera, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        description = self.entity_description
        await self._command(description.command or description.key, **(description.args or {}))

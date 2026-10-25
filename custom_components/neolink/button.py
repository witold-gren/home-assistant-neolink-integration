"""Restart, siren, state refresh and snapshot (these wake the camera)."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient
from .entity import NeolinkEntity

BUTTONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="reboot", device_class=ButtonDeviceClass.RESTART, entity_category=EntityCategory.CONFIG
    ),
    ButtonEntityDescription(key="siren", translation_key="siren"),
    # The only way to get a fresh still from a sleeping camera; the camera entity then serves it
    # from the cache.
    ButtonEntityDescription(key="snapshot", translation_key="snapshot"),
    ButtonEntityDescription(
        key="refresh", translation_key="refresh", entity_category=EntityCategory.DIAGNOSTIC
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
        for name in client.cameras
        for description in BUTTONS
    )


class NeolinkButton(NeolinkEntity, ButtonEntity):
    """One-shot command."""

    def __init__(
        self, client: NeolinkClient, camera: str, description: ButtonEntityDescription
    ) -> None:
        super().__init__(client, camera, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self._command(self.entity_description.key)

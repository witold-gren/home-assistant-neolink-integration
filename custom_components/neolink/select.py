"""Infrared (night vision) mode and post-detection recording time."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient
from .entity import NeolinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    entities: list[SelectEntity] = [NeolinkIrSelect(client, name) for name in client.cameras]
    entities += [
        NeolinkPostRecordSelect(client, name)
        for name, state in client.cameras.items()
        if "post_record" in state
    ]
    async_add_entities(entities)


class NeolinkIrSelect(NeolinkEntity, SelectEntity):
    """Infrared: on, off or auto."""

    _attr_translation_key = "ir"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: NeolinkClient, camera: str) -> None:
        super().__init__(client, camera, "ir")
        self._attr_options = ["auto", "on", "off"]

    @property
    def current_option(self) -> str | None:
        value = self.state_data.get("ir")
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self._command("ir", state=option)


class NeolinkPostRecordSelect(NeolinkEntity, SelectEntity):
    """Seconds of recording after a detection (values come from the camera, e.g. 8/15/30)."""

    _attr_translation_key = "post_record"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: NeolinkClient, camera: str) -> None:
        super().__init__(client, camera, "post_record")

    @property
    def options(self) -> list[str]:
        values = self.state_data.get("post_record_options") or [8, 15, 30]
        return [f"{v} s" for v in values]

    @property
    def current_option(self) -> str | None:
        value = self.state_data.get("post_record")
        return None if value is None else f"{value} s"

    async def async_select_option(self, option: str) -> None:
        await self._command("post_record", seconds=int(option.split()[0]))

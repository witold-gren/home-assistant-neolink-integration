"""PIR sensor sensitivity."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
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
    async_add_entities(
        NeolinkPirSensitivity(client, name)
        for name, state in client.cameras.items()
        if "pir_sensitivity" in state
    )


class NeolinkPirSensitivity(NeolinkEntity, NumberEntity):
    """PIR sensitivity as in the Reolink app (1-100); changing it wakes the camera."""

    _attr_translation_key = "pir_sensitivity"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, client: NeolinkClient, camera: str) -> None:
        super().__init__(client, camera, "pir_sensitivity")

    @property
    def native_value(self) -> float | None:
        return self.state_data.get("pir_sensitivity")

    async def async_set_native_value(self, value: float) -> None:
        await self._command("pir_sensitivity", value=int(value))

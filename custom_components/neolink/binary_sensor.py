"""Camera link to the bridge, charging and motion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient
from .entity import NeolinkEntity


@dataclass(frozen=True, kw_only=True)
class NeolinkBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description."""

    value: Callable[[dict[str, Any]], bool | None]
    supported: Callable[[dict[str, Any]], bool] = lambda _: True


def _charging(state: dict[str, Any]) -> bool | None:
    battery = state.get("battery")
    return None if battery is None else battery["charge_status"] == "charging"


BINARY_SENSORS: tuple[NeolinkBinaryDescription, ...] = (
    NeolinkBinaryDescription(
        key="link",
        translation_key="link",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: bool(s.get("connected")),
    ),
    NeolinkBinaryDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_charging,
    ),
    NeolinkBinaryDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value=lambda s: s.get("motion"),
        # Only when the bridge reports motion: from push notifications (the camera may sleep) or
        # from listening while connected. Stays on for `motion_timeout` after each notification.
        supported=lambda s: bool(s.get("motion_enabled")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    async_add_entities(
        NeolinkBinarySensor(client, name, description)
        for name, state in client.cameras.items()
        for description in BINARY_SENSORS
        if description.supported(state)
    )


class NeolinkBinarySensor(NeolinkEntity, BinarySensorEntity):
    """Binary sensor from the camera state."""

    entity_description: NeolinkBinaryDescription

    def __init__(
        self, client: NeolinkClient, camera: str, description: NeolinkBinaryDescription
    ) -> None:
        super().__init__(client, camera, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value(self.state_data)

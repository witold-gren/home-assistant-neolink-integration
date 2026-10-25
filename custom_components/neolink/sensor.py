"""Battery, SD card and 4G signal sensors, plus last motion and last snapshot times."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient
from .entity import NeolinkEntity


@dataclass(frozen=True, kw_only=True)
class NeolinkSensorDescription(SensorEntityDescription):
    """Sensor description: `value` extracts the value from the camera state."""

    value: Callable[[dict[str, Any]], Any]
    supported: Callable[[dict[str, Any]], bool] = lambda _: True


def _battery(key: str, scale: float | None = None) -> Callable[[dict[str, Any]], Any]:
    def value(state: dict[str, Any]) -> Any:
        raw = (state.get("battery") or {}).get(key)
        return raw if raw is None or scale is None else raw / scale

    return value


def _storage(key: str) -> Callable[[dict[str, Any]], Any]:
    def value(state: dict[str, Any]) -> Any:
        storage = state.get("storage")
        if not storage or not storage.get("mounted"):
            return None
        if key == "used_percent":
            total = storage["total_gb"]
            return round((total - storage["free_gb"]) / total * 100, 1) if total else None
        return storage[key]

    return value


# MCC+MNC of known operators; others are shown as the numeric code.
OPERATORS = {26001: "Plus", 26002: "T-Mobile", 26003: "Orange", 26006: "Play"}


def _operator(state: dict[str, Any]) -> str | None:
    code = state.get("mobile_operator")
    return None if code is None else OPERATORS.get(code, str(code))


def _timestamp(key: str) -> Callable[[dict[str, Any]], datetime | None]:
    def value(state: dict[str, Any]) -> datetime | None:
        seconds = state.get(key)
        return None if not seconds else datetime.fromtimestamp(seconds, UTC)

    return value


# Detection type from the bridge; an unknown alarm type maps to "other".
DETECTIONS = ("person", "vehicle", "animal", "motion", "other")


def _detection(state: dict[str, Any]) -> str | None:
    kind = state.get("last_detection")
    return None if kind is None else kind if kind in DETECTIONS else "other"


SENSORS: tuple[NeolinkSensorDescription, ...] = (
    NeolinkSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=_battery("percent"),
    ),
    NeolinkSensorDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_battery("temperature"),
    ),
    NeolinkSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=_battery("voltage", 1000),
    ),
    # Time of the last motion push notification (also while the camera sleeps).
    NeolinkSensorDescription(
        key="last_motion",
        translation_key="last_motion",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=_timestamp("last_motion"),
        supported=lambda s: bool(s.get("motion_enabled")),
    ),
    # What the camera detected in the last push (Reolink ALMTYPE); only if the bridge reports it.
    NeolinkSensorDescription(
        key="last_detection",
        translation_key="last_detection",
        device_class=SensorDeviceClass.ENUM,
        options=list(DETECTIONS),
        value=_detection,
        supported=lambda s: bool(s.get("motion_enabled")) and "last_detection" in s,
    ),
    # SD card: read whenever the camera connects; only if the bridge reports it.
    NeolinkSensorDescription(
        key="storage_used",
        translation_key="storage_used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value=_storage("used_percent"),
        supported=lambda s: "storage" in s,
    ),
    NeolinkSensorDescription(
        key="storage_free",
        translation_key="storage_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_storage("free_gb"),
        supported=lambda s: "storage" in s,
    ),
    NeolinkSensorDescription(
        key="storage_total",
        translation_key="storage_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_storage("total_gb"),
        supported=lambda s: "storage" in s,
    ),
    # 4G signal: the camera sends it every few seconds while connected.
    NeolinkSensorDescription(
        key="signal_level",
        translation_key="signal_level",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.get("signal_level"),
        supported=lambda s: "signal_level" in s,
    ),
    NeolinkSensorDescription(
        key="signal_value",
        translation_key="signal_value",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda s: s.get("signal_value"),
        supported=lambda s: "signal_level" in s,
    ),
    NeolinkSensorDescription(
        key="mobile_operator",
        translation_key="mobile_operator",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_operator,
        supported=lambda s: "signal_level" in s,
    ),
    # Time of the cached snapshot: a change means a new snapshot (e.g. after motion).
    NeolinkSensorDescription(
        key="snapshot_at",
        translation_key="snapshot_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_timestamp("snapshot_at"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    async_add_entities(
        NeolinkSensor(client, name, description)
        for name, state in client.cameras.items()
        for description in SENSORS
        if description.supported(state)
    )


class NeolinkSensor(NeolinkEntity, SensorEntity):
    """Value from the latest bridge state (reading never wakes the camera)."""

    entity_description: NeolinkSensorDescription

    def __init__(
        self, client: NeolinkClient, camera: str, description: NeolinkSensorDescription
    ) -> None:
        super().__init__(client, camera, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.state_data)

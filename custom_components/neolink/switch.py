"""Status LED, PIR sensor, detection settings, live-view recording and the automatic copy of the
SD card recordings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient
from .entity import NeolinkEntity

SWITCHES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="led", translation_key="led", entity_category=EntityCategory.CONFIG
    ),
    SwitchEntityDescription(
        key="pir", translation_key="pir", entity_category=EntityCategory.CONFIG
    ),
    # Older bridges do not report these state keys, so these entities are not created.
    SwitchEntityDescription(
        key="pir_reduce_false_alarm",
        translation_key="pir_reduce_false_alarm",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="recording", translation_key="recording", entity_category=EntityCategory.CONFIG
    ),
    SwitchEntityDescription(
        key="alarm_sound", translation_key="alarm_sound", entity_category=EntityCategory.CONFIG
    ),
    # Camera push notifications: when off, HA gets no motion events.
    SwitchEntityDescription(
        key="push_enabled", translation_key="push_enabled", entity_category=EntityCategory.CONFIG
    ),
    # Watched live views written to Home Assistant's media folder by the add-on (never wakes the
    # camera). Only when the bridge records at all: it reports None without a record_dir.
    SwitchEntityDescription(
        key="record_live",
        translation_key="record_live",
        icon="mdi:record-rec",
        entity_category=EntityCategory.CONFIG,
    ),
    # The newest SD card recording copied to the media folder 5 minutes after each motion alert
    # (bridge 0.3.0 and later; None without a recording folder). Browsing and copying by hand work
    # either way.
    SwitchEntityDescription(
        key="sd_auto",
        translation_key="sd_auto",
        icon="mdi:sd",
        entity_category=EntityCategory.CONFIG,
    ),
)

# Switches the bridge reports as None when it has no recording folder.
NEEDS_FOLDER = ("record_live", "sd_auto")

# Where the add-on writes the recorded live views, relative to Home Assistant's media folder.
RECORDINGS_PATH = "neolink/{camera}"

# State key -> bridge command, where they differ.
COMMANDS = {"push_enabled": "push"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    async_add_entities(
        NeolinkSwitch(client, name, description)
        for name, state in client.cameras.items()
        for description in SWITCHES
        if description.key in state
        and (description.key not in NEEDS_FOLDER or state[description.key] is not None)
    )


class NeolinkSwitch(NeolinkEntity, SwitchEntity):
    """Switch; the command wakes the camera and the new state arrives as a bridge event."""

    def __init__(
        self, client: NeolinkClient, camera: str, description: SwitchEntityDescription
    ) -> None:
        super().__init__(client, camera, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.state_data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        # A dashboard finds the recordings of this camera here (media folder, day folders inside).
        if self.entity_description.key != "record_live":
            return None
        return {"recordings_path": RECORDINGS_PATH.format(camera=self._camera)}

    async def async_turn_on(self, **kwargs: Any) -> None:
        key = self.entity_description.key
        await self._command(COMMANDS.get(key, key), on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        key = self.entity_description.key
        await self._command(COMMANDS.get(key, key), on=False)

"""Last snapshot and last motion event snapshot from the bridge cache (never wakes the camera)."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient, NeolinkError
from .entity import NeolinkEntity

# key -> state field with the snapshot time; the event snapshot is stored after a motion push.
IMAGES: tuple[ImageEntityDescription, ...] = (
    ImageEntityDescription(key="snapshot_at", translation_key="last_snapshot"),
    ImageEntityDescription(key="event_snapshot_at", translation_key="last_event"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    async_add_entities(
        NeolinkImage(hass, client, name, description)
        for name, state in client.cameras.items()
        for description in IMAGES
        if description.key in state
    )


class NeolinkImage(NeolinkEntity, ImageEntity):
    """Snapshot from the bridge cache; a new snapshot means a new timestamp in the camera state."""

    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        hass: HomeAssistant,
        client: NeolinkClient,
        camera: str,
        description: ImageEntityDescription,
    ) -> None:
        # ImageEntity sets its own `_client` (HTTP client for URL images), which is unused here:
        # NeolinkEntity must be initialized second so that `_client` is the bridge client.
        ImageEntity.__init__(self, hass)
        NeolinkEntity.__init__(self, client, camera, description.translation_key or "")
        self.entity_description = description
        self._attr_image_last_updated = self._taken()

    def _taken(self) -> datetime | None:
        seconds = self.state_data.get(self.entity_description.key)
        return datetime.fromtimestamp(seconds, UTC) if seconds else None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._client.add_listener(self._state_changed))

    @callback
    def _state_changed(self) -> None:
        taken = self._taken()
        if taken != self._attr_image_last_updated:
            # New timestamp: HA rotates the image URL token and cards fetch the new picture.
            self._attr_image_last_updated = taken
            self._cached_image = None
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        event = self.entity_description.key == "event_snapshot_at"
        try:
            return await self._client.cached_snapshot(self._camera, event=event)
        except NeolinkError as err:
            raise HomeAssistantError(f"{self._camera}: {err}") from err

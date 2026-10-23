"""Camera: live view from the bridge RTSP server, still image only from the bridge cache.

Thumbnails and the player poster never wake a battery camera. The bridge refreshes the still by
itself whenever the camera is connected anyway (live view, commands); the "Take snapshot" button
takes a fresh one on demand.
"""

from __future__ import annotations

from urllib.parse import quote

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient, NeolinkError
from .const import (
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PORT,
    CONF_RTSP_USERNAME,
    STREAM_TIMEOUT,
)
from .entity import NeolinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    async_add_entities(NeolinkCamera(client, name, entry) for name in client.cameras)


class NeolinkCamera(NeolinkEntity, Camera):
    """Reolink camera through Neolink."""

    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, client: NeolinkClient, camera: str, entry: NeolinkConfigEntry) -> None:
        NeolinkEntity.__init__(self, client, camera, "camera")
        Camera.__init__(self)
        data = entry.data
        user, password = data.get(CONF_RTSP_USERNAME), data.get(CONF_RTSP_PASSWORD)
        auth = f"{quote(user, safe='')}:{quote(password or '', safe='')}@" if user else ""
        # `#timeout=` is read by go2rtc (default 5 s, while a sleeping 4G camera needs up to ~20 s);
        # ffmpeg sends the fragment to the server and the bridge ignores it.
        self._source = (
            f"rtsp://{auth}{data[CONF_HOST]}:{data[CONF_RTSP_PORT]}/{camera}/sub"
            f"#timeout={STREAM_TIMEOUT}"
        )

    async def stream_source(self) -> str:
        # Connecting to this URL wakes the camera; the bridge disconnects it when idle.
        return self._source

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            return await self._client.cached_snapshot(self._camera)
        except NeolinkError as err:
            raise HomeAssistantError(f"{self._camera}: {err}") from err

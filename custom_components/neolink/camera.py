"""Camera: live view from the bridge RTSP server, still image only from the bridge cache.

Thumbnails and the player poster never wake a battery camera. The bridge refreshes the still by
itself whenever the camera is connected anyway (live view, commands); the "Take snapshot" button
takes a fresh one on demand.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    CameraWebRTCProvider,
    WebRTCSendMessage,
)
from homeassistant.components.camera.webrtc import async_get_supported_provider
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeolinkConfigEntry
from .api import NeolinkClient, NeolinkError
from .const import (
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PORT,
    CONF_RTSP_USERNAME,
    CONF_STREAM_MODE,
    DEFAULT_STREAM_MODE,
    STREAM_MODE_WEBRTC,
    STREAM_TIMEOUT,
)
from .entity import NeolinkEntity
from .sd_card import sd_recordings_attribute
from .talk import talk_path

if TYPE_CHECKING:
    from webrtc_models import RTCIceCandidateInit

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    client = entry.runtime_data.client
    mode = entry.options.get(CONF_STREAM_MODE, DEFAULT_STREAM_MODE)
    camera_class = NeolinkWebRtcCamera if mode == STREAM_MODE_WEBRTC else NeolinkCamera
    async_add_entities(camera_class(client, name, entry) for name in client.cameras)


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Where a dashboard talks through the camera's speaker (see talk.py) and finds the
        # recordings on its SD card (see sd_card.py; bridge 0.3.0 and later)
        attributes: dict[str, Any] = {"talk_path": talk_path(self._camera)}
        if "sd_sync" in self.state_data:
            attributes["sd_recordings"] = sd_recordings_attribute()
        return attributes

    async def stream_source(self) -> str:
        # Connecting to this URL wakes the camera; the bridge disconnects it when idle.
        return self._source

    async def async_sync_recordings(self, hours: int, latest: bool) -> None:
        """Copy the SD card recordings of the last `hours` that Home Assistant lacks (see
        `neolink.sync_recordings`); the bridge works in the background."""
        await self._command("sd_sync", hours=hours, latest=latest)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            return await self._client.cached_snapshot(self._camera)
        except NeolinkError as err:
            raise HomeAssistantError(f"{self._camera}: {err}") from err


class NeolinkWebRtcCamera(NeolinkCamera):
    """The same camera, with WebRTC as its only live view.

    For a camera that offers both, the frontend starts an HLS and a WebRTC player at once and keeps
    the HLS one running in the background, so every live view opened two camera streams over a 4G
    camera's mobile link. A camera with its own WebRTC offer is shown with WebRTC only; the offer
    goes to the provider Home Assistant would have picked itself (go2rtc), like for any camera.
    """

    def __init__(self, client: NeolinkClient, camera: str, entry: NeolinkConfigEntry) -> None:
        super().__init__(client, camera, entry)
        # The provider of each open WebRTC session, for its candidates and its end
        self._webrtc_sessions: dict[str, CameraWebRTCProvider] = {}

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        provider = await async_get_supported_provider(self.hass, self)
        if provider is None:
            _LOGGER.warning(
                '%s: no WebRTC provider (go2rtc) for the live view; choose "%s" in the '
                "Neolink options to use HLS instead",
                self._camera,
                "auto",
            )
            raise HomeAssistantError(f"{self._camera}: WebRTC (go2rtc) is not available")
        self._webrtc_sessions[session_id] = provider
        await provider.async_handle_async_webrtc_offer(self, offer_sdp, session_id, send_message)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        if (provider := self._webrtc_sessions.get(session_id)) is None:
            raise HomeAssistantError(f"{self._camera}: unknown WebRTC session")
        await provider.async_on_webrtc_candidate(session_id, candidate)

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        if (provider := self._webrtc_sessions.pop(session_id, None)) is not None:
            provider.async_close_session(session_id)

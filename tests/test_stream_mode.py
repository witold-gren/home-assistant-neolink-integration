"""Live view mode: WebRTC only (one camera stream) or Home Assistant's HLS + WebRTC."""

from __future__ import annotations

from homeassistant.components.camera import (
    CameraWebRTCProvider,
    StreamType,
    WebRTCSendMessage,
    async_register_webrtc_provider,
)
from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from webrtc_models import RTCIceCandidateInit

from custom_components.neolink.camera import NeolinkCamera, NeolinkWebRtcCamera
from custom_components.neolink.const import CONF_STREAM_MODE

from .conftest import FakeBridge


class FakeGo2rtc(CameraWebRTCProvider):
    """Stands in for go2rtc: records what the camera hands over."""

    def __init__(self) -> None:
        self.offers: list[tuple[str, str, str]] = []
        self.candidates: list[tuple[str, str]] = []
        self.closed: list[str] = []

    @property
    def domain(self) -> str:
        return "go2rtc"

    @callback
    def async_is_supported(self, stream_source: str) -> bool:
        return stream_source.startswith("rtsp://")

    async def async_handle_async_webrtc_offer(
        self, camera, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        self.offers.append((camera.entity_id, offer_sdp, session_id))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        self.candidates.append((session_id, candidate.candidate))

    @callback
    def async_close_session(self, session_id: str) -> None:
        self.closed.append(session_id)


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_webrtc_only_by_default(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    camera = get_camera_from_entity_id(hass, "camera.g330")
    assert isinstance(camera, NeolinkWebRtcCamera)
    # The frontend gets no HLS player, so a live view opens one camera stream
    assert camera.camera_capabilities.frontend_stream_types == {StreamType.WEB_RTC}


async def test_auto_mode_keeps_home_assistants_players(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_STREAM_MODE: "auto"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    camera = get_camera_from_entity_id(hass, "camera.g330")
    assert type(camera) is NeolinkCamera
    assert StreamType.HLS in camera.camera_capabilities.frontend_stream_types


async def test_webrtc_offer_goes_to_go2rtc(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    go2rtc = FakeGo2rtc()
    async_register_webrtc_provider(hass, go2rtc)
    camera = get_camera_from_entity_id(hass, "camera.g330")

    await camera.async_handle_async_webrtc_offer("v=0 offer", "session-1", lambda _: None)
    await camera.async_on_webrtc_candidate("session-1", RTCIceCandidateInit("candidate:1"))
    camera.close_webrtc_session("session-1")

    assert go2rtc.offers == [("camera.g330", "v=0 offer", "session-1")]
    assert go2rtc.candidates == [("session-1", "candidate:1")]
    assert go2rtc.closed == ["session-1"]
    # A closed session takes no more candidates
    with pytest.raises(HomeAssistantError):
        await camera.async_on_webrtc_candidate("session-1", RTCIceCandidateInit("candidate:2"))


async def test_webrtc_offer_without_go2rtc_fails_clearly(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    camera = get_camera_from_entity_id(hass, "camera.g330")
    with pytest.raises(HomeAssistantError, match="go2rtc"):
        await camera.async_handle_async_webrtc_offer("v=0 offer", "session-1", lambda _: None)


async def test_options_change_the_live_view(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_STREAM_MODE: "auto"}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    # The entry reloaded with the camera of the new mode
    assert entry.options == {CONF_STREAM_MODE: "auto"}
    assert type(get_camera_from_entity_id(hass, "camera.g330")) is NeolinkCamera

"""Constants for the Neolink integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "neolink"

CONF_RTSP_PORT: Final = "rtsp_port"
CONF_RTSP_USERNAME: Final = "rtsp_username"
CONF_RTSP_PASSWORD: Final = "rtsp_password"

DEFAULT_PORT: Final = 3002
DEFAULT_RTSP_PORT: Final = 8554

# A battery camera on 4G (woken through the Reolink servers) usually answers in 10-20 s,
# but waking it up can take much longer, so commands wait up to 100 s.
COMMAND_TIMEOUT: Final = 100
# Seconds go2rtc waits for the first RTSP response from a waking camera.
STREAM_TIMEOUT: Final = 60
RECONNECT_DELAYS: Final = (1, 2, 5, 10, 30)

# How the live view reaches the browser (entry option). "webrtc": WebRTC only, through go2rtc, so a
# live view opens one camera stream. "auto": Home Assistant's default, the frontend starts HLS and
# WebRTC together (two camera streams sharing a 4G camera's link until one is dropped).
CONF_STREAM_MODE: Final = "stream_mode"
STREAM_MODE_WEBRTC: Final = "webrtc"
STREAM_MODE_AUTO: Final = "auto"
STREAM_MODES: Final = (STREAM_MODE_WEBRTC, STREAM_MODE_AUTO)
DEFAULT_STREAM_MODE: Final = STREAM_MODE_WEBRTC

# How far back the "Sync recordings" button looks on the SD card (every recording costs mobile
# data on a 4G camera); the neolink.sync_recordings action takes its own range.
SYNC_HOURS: Final = 7 * 24
# How long the siren entity sounds when no duration is given.
SIREN_SECONDS: Final = 30

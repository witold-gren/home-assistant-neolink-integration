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

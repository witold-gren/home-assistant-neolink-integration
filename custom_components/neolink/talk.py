"""Talk through a camera's speaker from the browser.

The browser sends its microphone as raw 16-bit PCM over a WebSocket to Home Assistant, which needs
the user's login (the page asks for a signed path, so the socket carries no header). Home
Assistant relays the frames to the bridge's `/talk/<camera>`, which encodes them for the camera.
The text "stop", or closing the socket, ends the talk; the last message is the outcome,
`{"ok": true}` or `{"ok": false, "error": "busy" | "no_speaker" | "unreachable" | "failed"}`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp
from aiohttp import WSMsgType, web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TALK_URL = "/api/neolink/talk/{camera}"
DEFAULT_RATE = 48_000
MIN_RATE = 8_000
MAX_RATE = 48_000
# How long the bridge may take to answer once the talk ended.
ANSWER_TIMEOUT_S = 15


def talk_path(camera: str) -> str:
    """Where a dashboard talks through `camera` (signed, plus `?rate=<Hz>`)."""
    return TALK_URL.format(camera=camera)


def talk_rate(value: Any) -> int:
    """Return the browser's sample rate, kept within what the bridge takes."""
    try:
        rate = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RATE
    return rate if MIN_RATE <= rate <= MAX_RATE else DEFAULT_RATE


def answer(text: str) -> dict[str, Any]:
    """The bridge's last message, or a failure when it is not one."""
    failed = {"ok": False, "error": "failed"}
    try:
        outcome = json.loads(text)
    except ValueError:
        return failed
    return outcome if isinstance(outcome, dict) and "ok" in outcome else failed


async def relay_talk(
    browser: web.WebSocketResponse, bridge: aiohttp.ClientWebSocketResponse
) -> dict[str, Any]:
    """Pass the browser's frames to the bridge until either side ends; return the outcome."""

    async def from_bridge() -> dict[str, Any]:
        async for message in bridge:
            if message.type == WSMsgType.TEXT:
                return answer(message.data)
        return {"ok": False, "error": "unreachable"}

    outcome = asyncio.ensure_future(from_bridge())
    try:
        async for message in browser:
            if outcome.done():  # the bridge refused or failed while the browser was still talking
                break
            if message.type == WSMsgType.BINARY:
                await bridge.send_bytes(message.data)
            elif (message.type == WSMsgType.TEXT and message.data == "stop") or message.type in (
                WSMsgType.ERROR,
                WSMsgType.CLOSE,
            ):
                break
        if not outcome.done() and not bridge.closed:
            await bridge.send_str("stop")
        return await asyncio.wait_for(outcome, ANSWER_TIMEOUT_S)
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.warning("talk: the bridge did not answer: %s", err)
        return {"ok": False, "error": "unreachable"}
    finally:
        outcome.cancel()


class NeolinkTalkView(HomeAssistantView):
    """`GET /api/neolink/talk/<camera>?rate=<Hz>`: a WebSocket of PCM s16le mono."""

    url = TALK_URL
    name = "api:neolink:talk"
    requires_auth = True

    async def get(self, request: web.Request, camera: str) -> web.StreamResponse:
        """Relay one talk to the camera's bridge."""
        hass = request.app[KEY_HASS]
        client = next(
            (
                entry.runtime_data.client
                for entry in hass.config_entries.async_loaded_entries(DOMAIN)
                if camera in entry.runtime_data.client.cameras
            ),
            None,
        )
        if client is None:
            return web.Response(status=404, text="unknown camera")
        browser = web.WebSocketResponse(heartbeat=30)
        await browser.prepare(request)
        try:
            bridge = await client.talk(camera, talk_rate(request.query.get("rate")))
        except aiohttp.ClientError as err:
            _LOGGER.warning("talk: cannot reach the bridge: %s", err)
            outcome: dict[str, Any] = {"ok": False, "error": "unreachable"}
        else:
            async with bridge:
                outcome = await relay_talk(browser, bridge)
        if not browser.closed:
            await browser.send_str(json.dumps(outcome))
            await browser.close()
        return browser


def async_register_talk(hass: HomeAssistant) -> None:
    """Register the talk endpoint once, whatever number of entries are set up."""
    key = f"{DOMAIN}_talk_view"
    if hass.data.get(key):
        return
    hass.http.register_view(NeolinkTalkView())
    hass.data[key] = True

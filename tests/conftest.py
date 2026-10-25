"""Fake Neolink bridge speaking the fork protocol (hello, commands, state events, /snapshot)."""

from __future__ import annotations

import asyncio
import copy
from typing import Any
from unittest.mock import patch

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neolink.const import (
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PORT,
    CONF_RTSP_USERNAME,
    DOMAIN,
)

TOKEN = "secret"
JPEG = b"\xff\xd8fake-jpeg\xff\xd9"

CAMERA = {
    "name": "G330",
    "uid": "95270003TESTUID1",
    "connected": False,
    "model": "Reolink Go Plus",
    "firmware": "v3.0.0.662_21102000",
    "hardware": "BIPC_523MIX32M21B194MP",
    "serial": None,
    "battery": {
        "percent": 100,
        "charge_status": "charging",
        "adapter_status": "adapter",
        "voltage": 4114,
        "current": -643,
        "temperature": 32,
        "low_power": False,
    },
    "led": True,
    "ir": "auto",
    "pir": True,
    "motion": None,
    "motion_enabled": False,
    "last_motion": None,
    "last_detection": None,
    "snapshot_at": 1760700000,
    "event_snapshot_at": None,
    "pir_sensitivity": 41,
    "pir_reduce_false_alarm": True,
    "recording": True,
    "post_record": 15,
    "post_record_options": [8, 15, 30],
    "alarm_sound": False,
    "push_enabled": True,
    "storage": {"total_gb": 57.0, "free_gb": 37.566, "formatted": True, "mounted": True},
    "signal_level": 5,
    "signal_value": 25,
    "mobile_operator": 26006,
    "updated": 0,
}


class FakeBridge:
    """A real HTTP/WebSocket server on localhost."""

    def __init__(self) -> None:
        self.cameras: dict[str, dict[str, Any]] = {"G330": copy.deepcopy(CAMERA)}
        self.commands: list[dict[str, Any]] = []
        self.snapshots: list[dict[str, str]] = []
        self.cached: bytes | None = JPEG
        self.event: bytes | None = None
        self.sockets: list[web.WebSocketResponse] = []
        self.closing = False
        app = web.Application()
        app.router.add_get("/ws", self._ws)
        app.router.add_get("/snapshot/{name}", self._snapshot)
        self.server = TestServer(app)

    @property
    def port(self) -> int:
        return self.server.port

    def _authorized(self, request: web.Request) -> bool:
        return (
            request.headers.get("Authorization") == f"Bearer {TOKEN}"
            or request.query.get("token") == TOKEN
        )

    async def _ws(self, request: web.Request) -> web.StreamResponse:
        if self.closing:
            raise web.HTTPServiceUnavailable
        if not self._authorized(request):
            raise web.HTTPUnauthorized
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.sockets.append(ws)
        await ws.send_json(
            {"type": "hello", "version": "test", "cameras": list(self.cameras.values())}
        )
        async for msg in ws:
            if msg.type is not WSMsgType.TEXT:
                continue
            req = msg.json()
            self.commands.append(req)
            await ws.send_json(await self._handle(req))
        self.sockets.remove(ws)
        return ws

    async def _handle(self, req: dict[str, Any]) -> dict[str, Any]:
        cam = self.cameras.get(req.get("camera", ""))
        if cam is None:
            return {"type": "result", "id": req["id"], "success": False, "error": "unknown camera"}
        args = req.get("args", {})
        if req["command"] in ("led", "pir", "pir_reduce_false_alarm", "recording", "alarm_sound"):
            cam[req["command"]] = args["on"]
        elif req["command"] == "push":
            cam["push_enabled"] = args["on"]
        elif req["command"] == "pir_sensitivity":
            cam["pir_sensitivity"] = args["value"]
        elif req["command"] == "post_record":
            cam["post_record"] = args["seconds"]
        elif req["command"] == "ir":
            cam["ir"] = args["state"]
        elif req["command"] == "siren" and cam.get("fail"):
            return {"type": "result", "id": req["id"], "success": False, "error": "camera asleep"}
        await self.push(cam["name"])
        return {"type": "result", "id": req["id"], "success": True, "result": cam}

    async def _snapshot(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            raise web.HTTPUnauthorized
        self.snapshots.append(dict(request.query))
        if request.query.get("event") == "true":
            if self.event is None:
                raise web.HTTPNotFound(text="no event snapshot")
            return web.Response(body=self.event, content_type="image/jpeg")
        if self.cached is None:
            raise web.HTTPNotFound(text="no cached snapshot")
        return web.Response(body=self.cached, content_type="image/jpeg")

    async def push(self, name: str) -> None:
        """Send a state event to all clients, like the fork does."""
        for ws in list(self.sockets):
            await ws.send_json(
                {"type": "event", "event": "state", "camera": name, "state": self.cameras[name]}
            )

    async def drop_clients(self) -> None:
        for ws in list(self.sockets):
            await ws.close()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let HA load custom_components in tests."""


@pytest.fixture(autouse=True)
def fast_reconnect():
    with patch("custom_components.neolink.api.RECONNECT_DELAYS", (0.01,)):
        yield


@pytest.fixture
async def bridge(socket_enabled: None) -> FakeBridge:
    fake = FakeBridge()
    await fake.server.start_server()
    yield fake
    # The integration client reconnects: refuse new connections, drop clients, then close.
    fake.closing = True
    await fake.drop_clients()
    await fake.server.close()


@pytest.fixture
def entry(bridge: FakeBridge) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Neolink",
        unique_id="addon-uuid",
        data={
            "host": "127.0.0.1",
            "port": bridge.port,
            "token": TOKEN,
            CONF_RTSP_PORT: 8564,
            CONF_RTSP_USERNAME: "ha",
            CONF_RTSP_PASSWORD: "p@ss word",
        },
    )


async def settle(hass) -> None:
    """Let socket events reach HA."""
    for _ in range(5):
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()

"""WebSocket API client for the Neolink bridge (fork with the ws-rtsp mode)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import itertools
import logging
from typing import Any

import aiohttp

from .const import COMMAND_TIMEOUT, RECONNECT_DELAYS

_LOGGER = logging.getLogger(__name__)

type CameraState = dict[str, Any]


class NeolinkError(Exception):
    """Bridge connection error or rejected command."""


class NeolinkAuthError(NeolinkError):
    """The bridge rejected the token."""


class NeolinkClient:
    """A single WebSocket connection: camera state, events and commands."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        token: str | None,
    ) -> None:
        self._session = session
        self._base = f"http://{host}:{port}"
        self._token = token or None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self.cameras: dict[str, CameraState] = {}
        self.version: str | None = None
        self.connected = False

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` on every state change; return a function that removes it."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def connect(self) -> None:
        """First connection: wait for `hello` and raise errors (config flow, entry setup)."""
        await self._open()
        self._task = asyncio.create_task(self._run(), name="neolink-ws")

    async def _open(self) -> None:
        try:
            ws = await self._session.ws_connect(
                f"{self._base}/ws", headers=self._headers, heartbeat=30
            )
        except aiohttp.WSServerHandshakeError as err:
            if err.status == 401:
                raise NeolinkAuthError("invalid token") from err
            raise NeolinkError(f"handshake failed: {err.status}") from err
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise NeolinkError(f"cannot connect to {self._base}: {err}") from err
        try:
            hello = await ws.receive_json(timeout=15)
        except (TimeoutError, ValueError, TypeError) as err:
            await ws.close()
            raise NeolinkError("no hello from the bridge") from err
        if hello.get("type") != "hello":
            await ws.close()
            raise NeolinkError(f"unexpected first message: {hello.get('type')}")
        self._ws = ws
        self.version = hello.get("version")
        self.cameras = {c["name"]: c for c in hello.get("cameras", [])}
        self.connected = True
        self._notify()

    async def _run(self) -> None:
        """Receive messages; after a disconnect, reconnect with an increasing delay."""
        attempt = 0
        while not self._stopping:
            if self._ws is not None:
                attempt = 0
                await self._receive(self._ws)
                self._ws = None
                self.connected = False
                self._fail_pending(NeolinkError("connection lost"))
                self._notify()
            if self._stopping:
                break
            delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)]
            attempt += 1
            await asyncio.sleep(delay)
            with contextlib.suppress(NeolinkError):
                await self._open()

    async def _receive(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        async for msg in ws:
            if msg.type is not aiohttp.WSMsgType.TEXT:
                continue
            try:
                data = msg.json()
            except ValueError:
                continue
            kind = data.get("type")
            if kind == "event" and data.get("event") == "state":
                self.cameras[data["camera"]] = data["state"]
                self._notify()
            elif kind == "result":
                future = self._pending.pop(data.get("id"), None)
                if future is not None and not future.done():
                    if data.get("success"):
                        future.set_result(data.get("result"))
                    else:
                        future.set_exception(NeolinkError(data.get("error") or "command failed"))

    def _fail_pending(self, err: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(err)
        self._pending.clear()

    async def command(self, command: str, camera: str | None = None, **args: Any) -> Any:
        """Send a command and wait for the result (a battery camera may need to wake up)."""
        if self._ws is None:
            raise NeolinkError("not connected to the bridge")
        request_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        payload: dict[str, Any] = {"id": request_id, "command": command, "args": args}
        if camera is not None:
            payload["camera"] = camera
        try:
            await self._ws.send_json(payload)
            async with asyncio.timeout(COMMAND_TIMEOUT):
                return await future
        except TimeoutError as err:
            raise NeolinkError(f"{command}: no answer within {COMMAND_TIMEOUT}s") from err
        finally:
            self._pending.pop(request_id, None)

    async def cached_snapshot(self, camera: str, event: bool = False) -> bytes | None:
        """Latest cached snapshot from the bridge (never wakes the camera); None if none yet.

        `event`: the snapshot taken after the last motion notification.
        """
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                resp = await self._session.get(
                    f"{self._base}/snapshot/{camera}",
                    params={"event": "true"} if event else {"cached": "true"},
                    headers=self._headers,
                )
                if resp.status == 404:
                    return None
                if resp.status != 200:
                    raise NeolinkError(f"snapshot: HTTP {resp.status} {await resp.text()}")
                return await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NeolinkError(f"snapshot failed: {err}") from err

    async def close(self) -> None:
        """Close the connection and stop reconnecting."""
        self._stopping = True
        if self._ws is not None:
            await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._fail_pending(NeolinkError("client closed"))

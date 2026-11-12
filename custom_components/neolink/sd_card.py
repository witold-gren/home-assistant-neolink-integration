"""The recordings on a camera's SD card for dashboards.

A camera entity tells where in its `sd_recordings` attribute: `{"list": "neolink/sd_recordings",
"download": "neolink/sd_download"}`.

- `neolink/sd_recordings` (`entity_id`, `refresh`, optional `thumbnails`): the list the bridge
  keeps, at once; `refresh: true` makes the bridge search the card again in the background (it
  wakes the camera), `thumbnails` asks for the covers of these files. Each recording: `file`
  (`YYYY-MM-DD/HHMMSS-HHMMSS.mp4`, as in the media folder), `start`, `end` (the camera's local
  time), `kinds`, `size`, `local`, `downloading` and `thumbnail` (a signed URL, or null until the
  bridge has the cover).
- `neolink/sd_download` (`entity_id`, `files`): copies these recordings to the media folder, one
  after another, in the background.

Nothing on the card is ever deleted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Any

from aiohttp import web
from homeassistant.components import websocket_api
from homeassistant.components.camera import DATA_COMPONENT
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .api import NeolinkError
from .const import DOMAIN

LIST_COMMAND = f"{DOMAIN}/sd_recordings"
DOWNLOAD_COMMAND = f"{DOMAIN}/sd_download"
THUMBNAIL_URL = "/api/neolink/sd_thumbnail/{camera}/{day}/{file}"
# How long a thumbnail link stays valid (a dashboard asks for the list every few seconds).
THUMBNAIL_LINK = timedelta(hours=1)
FILE = re.compile(r"^\d{4}-\d{2}-\d{2}/\d{6}-\d{6}\.mp4$")


def sd_recordings_attribute() -> dict[str, str]:
    """What a camera tells a dashboard about its SD card."""
    return {"list": LIST_COMMAND, "download": DOWNLOAD_COMMAND}


def thumbnail_path(camera: str, file: str) -> str:
    """The path of a recording's thumbnail (`file` as the list names it)."""
    day, name = file.split("/", 1)
    return THUMBNAIL_URL.format(camera=camera, day=day, file=name.removesuffix(".mp4") + ".jpg")


def _camera(hass: HomeAssistant, entity_id: str) -> Any:
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None or entity.platform.platform_name != DOMAIN:
        raise HomeAssistantError(f"{entity_id} is not a Neolink camera")
    return entity


def listing(
    hass: HomeAssistant, camera: str, bridge: dict[str, Any], refresh_token_id: str | None
) -> dict[str, Any]:
    """The bridge's list as the dashboard contract has it."""
    updated = bridge.get("updated")
    return {
        "updated": datetime.fromtimestamp(updated, UTC).isoformat() if updated else None,
        "refreshing": bool(bridge.get("refreshing")),
        "error": bridge.get("error"),
        "recordings": [
            {
                "file": r["file"],
                "start": r["start"],
                "end": r["end"],
                "kinds": r.get("kinds"),
                "size": r.get("size"),
                "local": bool(r.get("local")),
                "downloading": bool(r.get("downloading")),
                # Why the last copy of this file failed (bridge 0.3.1 and later), else None
                "copy_error": r.get("copy_error"),
                "thumbnail": async_sign_path(
                    hass,
                    thumbnail_path(camera, r["file"]),
                    THUMBNAIL_LINK,
                    refresh_token_id=refresh_token_id,
                )
                if r.get("thumbnail")
                else None,
            }
            for r in bridge.get("recordings", [])
        ],
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): LIST_COMMAND,
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("refresh", default=False): bool,
        vol.Optional("thumbnails"): [vol.Match(FILE)],
    }
)
@websocket_api.async_response
async def ws_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The recordings on the card."""
    try:
        camera = _camera(hass, msg["entity_id"])
        args: dict[str, Any] = {"refresh": msg["refresh"]}
        if msg.get("thumbnails"):
            args["thumbnails"] = msg["thumbnails"]
        bridge = await camera._client.command("sd_recordings", camera._camera, **args)
    except (HomeAssistantError, NeolinkError) as err:
        connection.send_error(msg["id"], "sd_recordings_failed", str(err))
        return
    connection.send_result(
        msg["id"], listing(hass, camera._camera, bridge, connection.refresh_token_id)
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): DOWNLOAD_COMMAND,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("files"): vol.All([vol.Match(FILE)], vol.Length(min=1)),
    }
)
@websocket_api.async_response
async def ws_download(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Copy recordings of the card to the media folder."""
    try:
        camera = _camera(hass, msg["entity_id"])
        await camera._client.command("sd_sync", camera._camera, files=msg["files"])
    except (HomeAssistantError, NeolinkError) as err:
        connection.send_error(msg["id"], "sd_download_failed", str(err))
        return
    connection.send_result(msg["id"], {"started": True})


class NeolinkSdThumbnailView(HomeAssistantView):
    """`GET /api/neolink/sd_thumbnail/<camera>/<day>/<HHMMSS-HHMMSS>.jpg`."""

    url = "/api/neolink/sd_thumbnail/{camera}/{day}/{file}"
    name = "api:neolink:sd_thumbnail"
    requires_auth = True

    async def get(self, request: web.Request, camera: str, day: str, file: str) -> web.Response:
        """The cover the bridge keeps, never waking the camera."""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not re.fullmatch(
            r"\d{6}-\d{6}\.jpg", file
        ):
            return web.Response(status=400)
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
        try:
            jpeg = await client.sd_thumbnail(camera, day, file)
        except NeolinkError as err:
            return web.Response(status=502, text=str(err))
        if jpeg is None:
            return web.Response(status=404, text="no thumbnail yet")
        return web.Response(
            body=jpeg, content_type="image/jpeg", headers={"Cache-Control": "max-age=86400"}
        )


@callback
def async_register_sd_card(hass: HomeAssistant) -> None:
    """Register the commands and the view once."""
    key = f"{DOMAIN}_sd_card"
    if hass.data.get(key):
        return
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_download)
    hass.http.register_view(NeolinkSdThumbnailView())
    hass.data[key] = True

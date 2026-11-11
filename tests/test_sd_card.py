"""The recordings on the SD card for dashboards: list, download and thumbnails."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neolink.sd_card import thumbnail_path

from .conftest import JPEG, FakeBridge, settle
from .test_init import setup

RECORDINGS = [
    {
        "file": "2026-10-15/122559-122609.mp4",
        "start": "2026-10-15T12:25:59",
        "end": "2026-10-15T12:26:09",
        "kinds": "pir",
        "size": 5501986,
        "local": False,
        "downloading": False,
        "thumbnail": True,
    },
    {
        "file": "2026-11-10/132042-132112.mp4",
        "start": "2026-11-10T13:20:42",
        "end": "2026-11-10T13:21:12",
        "kinds": "other",
        "size": 13519975,
        "local": True,
        "downloading": False,
        "thumbnail": False,
    },
]


async def setup_card(hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry) -> None:
    bridge.cameras["G330"].update(siren_on=False, sd_sync=None)
    bridge.sd_list = {"updated": 1794406699, "refreshing": True, "recordings": RECORDINGS}
    bridge.sd_thumbnails["2026-10-15/122559-122609.jpg"] = JPEG
    await setup(hass, entry)


async def test_the_camera_tells_where_its_card_is(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup_card(hass, bridge, entry)
    assert hass.states.get("camera.g330").attributes["sd_recordings"] == {
        "list": "neolink/sd_recordings",
        "download": "neolink/sd_download",
    }


async def test_an_older_bridge_has_no_card_attribute(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert "sd_recordings" not in hass.states.get("camera.g330").attributes


async def test_the_list_has_signed_thumbnails(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_ws_client
) -> None:
    await setup_card(hass, bridge, entry)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "neolink/sd_recordings",
            "entity_id": "camera.g330",
            "refresh": True,
            "thumbnails": ["2026-10-15/122559-122609.mp4"],
        }
    )
    reply = await client.receive_json()
    assert reply["success"], reply
    result = reply["result"]
    assert result["updated"] == "2026-11-11T14:18:19+00:00"
    assert result["refreshing"] is True
    first, second = result["recordings"]
    assert first["thumbnail"].startswith(
        "/api/neolink/sd_thumbnail/G330/2026-10-15/122559-122609.jpg?authSig="
    )
    assert second["thumbnail"] is None
    assert (second["local"], second["start"]) == (True, "2026-11-10T13:20:42")
    assert bridge.commands[-1]["args"] == {
        "refresh": True,
        "thumbnails": ["2026-10-15/122559-122609.mp4"],
    }


async def test_download_copies_the_chosen_files(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_ws_client
) -> None:
    await setup_card(hass, bridge, entry)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "neolink/sd_download",
            "entity_id": "camera.g330",
            "files": ["2026-10-15/122559-122609.mp4"],
        }
    )
    reply = await client.receive_json()
    assert reply["success"], reply
    assert reply["result"] == {"started": True}
    await settle(hass)
    assert (bridge.commands[-1]["command"], bridge.commands[-1]["args"]) == (
        "sd_sync",
        {"files": ["2026-10-15/122559-122609.mp4"]},
    )
    # Only file names as the list gives them
    await client.send_json_auto_id(
        {"type": "neolink/sd_download", "entity_id": "camera.g330", "files": ["../../etc"]}
    )
    assert not (await client.receive_json())["success"]


async def test_a_camera_of_another_integration_is_refused(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_ws_client
) -> None:
    await setup_card(hass, bridge, entry)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "neolink/sd_recordings", "entity_id": "camera.unknown"})
    reply = await client.receive_json()
    assert reply["error"]["code"] == "sd_recordings_failed"


async def test_the_thumbnail_view(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_client
) -> None:
    await setup_card(hass, bridge, entry)
    client = await hass_client()
    resp = await client.get(thumbnail_path("G330", "2026-10-15/122559-122609.mp4"))
    assert resp.status == 200
    assert await resp.read() == JPEG
    resp = await client.get(thumbnail_path("G330", "2026-11-10/132042-132112.mp4"))
    assert resp.status == 404
    resp = await client.get("/api/neolink/sd_thumbnail/G330/x/..%2Fy.jpg")
    assert resp.status in (400, 404)


async def test_the_auto_copy_switch(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    bridge.cameras["G330"].update(siren_on=False, sd_sync=None, sd_auto=False)
    await setup(hass, entry)
    assert hass.states.get("switch.g330_auto_copy_recordings").state == "off"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.g330_auto_copy_recordings"}, blocking=True
    )
    await settle(hass)
    assert (bridge.commands[-1]["command"], bridge.commands[-1]["args"]) == (
        "sd_auto",
        {"on": True},
    )
    assert hass.states.get("switch.g330_auto_copy_recordings").state == "on"


async def test_no_auto_copy_without_a_recording_folder(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    bridge.cameras["G330"].update(sd_sync=None, sd_auto=None)
    await setup(hass, entry)
    assert hass.states.get("switch.g330_auto_copy_recordings") is None

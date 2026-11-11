"""The siren on and off, and copying the recordings of the SD card (bridge 0.3.0 and later)."""

from __future__ import annotations

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neolink.siren import siren_seconds

from .conftest import FakeBridge, settle
from .test_init import setup


def sent(bridge: FakeBridge) -> list[tuple[str, dict]]:
    return [(c["command"], c["args"]) for c in bridge.commands]


async def test_the_siren_switches_on_for_a_while_and_off(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    bridge.cameras["G330"].update(siren_on=False, sd_sync=None)
    await setup(hass, entry)
    assert hass.states.get("siren.g330_siren").state == STATE_OFF
    await hass.services.async_call(
        "siren", "turn_on", {"entity_id": "siren.g330_siren", "duration": 10}, blocking=True
    )
    await settle(hass)
    assert hass.states.get("siren.g330_siren").state == STATE_ON
    await hass.services.async_call(
        "siren", "turn_off", {"entity_id": "siren.g330_siren"}, blocking=True
    )
    await settle(hass)
    assert hass.states.get("siren.g330_siren").state == STATE_OFF
    assert sent(bridge) == [("siren", {"on": True, "seconds": 10}), ("siren", {"on": False})]
    # The button still sounds it once
    assert hass.states.get("button.g330_siren") is not None


def test_siren_seconds_stay_within_the_bridge() -> None:
    assert siren_seconds(None) == 30
    assert siren_seconds("x") == 30
    assert siren_seconds(0) == 1
    assert siren_seconds(5000) == 900


async def test_an_older_bridge_has_no_siren_entity_and_no_sync(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert hass.states.get("siren.g330_siren") is None
    assert hass.states.get("button.g330_sync_recordings") is None
    assert hass.states.get("sensor.g330_recordings_sync") is None


async def test_the_button_syncs_the_last_week(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    bridge.cameras["G330"].update(siren_on=False, sd_sync=None)
    await setup(hass, entry)
    assert hass.states.get("sensor.g330_recordings_sync").state == "idle"
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.g330_sync_recordings"}, blocking=True
    )
    await settle(hass)
    assert sent(bridge) == [("sd_sync", {"hours": 168})]
    assert hass.states.get("sensor.g330_recordings_sync").state == "syncing"


async def test_the_action_copies_the_newest_recording(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    bridge.cameras["G330"].update(siren_on=False, sd_sync=None)
    await setup(hass, entry)
    await hass.services.async_call(
        "neolink",
        "sync_recordings",
        {"entity_id": "camera.g330", "hours": 2, "latest": True},
        blocking=True,
    )
    await settle(hass)
    assert sent(bridge) == [("sd_sync", {"hours": 2, "latest": True})]


async def test_the_sensor_tells_how_the_sync_went(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    bridge.cameras["G330"].update(siren_on=False, sd_sync=None)
    await setup(hass, entry)
    bridge.cameras["G330"]["sd_sync"] = {
        "running": False,
        "total": 3,
        "done": 2,
        "failed": 1,
        "last_file": "2026-11-10/132042-132112.mp4",
        "finished": 1794406699,
        "error": "the download did not finish within 300s",
    }
    await bridge.push("G330")
    await settle(hass)
    state = hass.states.get("sensor.g330_recordings_sync")
    assert state.state == "failed"
    assert state.attributes["copied"] == 2
    assert state.attributes["failed"] == 1
    assert state.attributes["last_file"] == "2026-11-10/132042-132112.mp4"
    assert state.attributes["finished"] == "2026-11-11T14:18:19+00:00"

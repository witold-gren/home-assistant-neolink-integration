"""Entry setup, entities, events, commands and reconnecting to the bridge."""

from __future__ import annotations

from homeassistant.components.camera import async_get_image, async_get_stream_source
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neolink.const import DOMAIN

from .conftest import JPEG, FakeBridge, settle


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_from_hello(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "95270003TESTUID1")})
    assert device is not None
    assert (device.model, device.sw_version, device.manufacturer) == (
        "Reolink Go Plus",
        "v3.0.0.662_21102000",
        "Reolink",
    )
    assert hass.states.get("sensor.g330_battery").state == "100"
    assert hass.states.get("sensor.g330_battery_temperature").state == "32"
    assert hass.states.get("binary_sensor.g330_charging").state == STATE_ON
    assert hass.states.get("binary_sensor.g330_camera_link").state == STATE_OFF
    assert hass.states.get("switch.g330_status_led").state == STATE_ON
    assert hass.states.get("switch.g330_pir_sensor").state == STATE_ON
    assert hass.states.get("select.g330_infrared").state == "auto"
    # Motion only when the bridge listens for it; voltage is disabled by default.
    assert hass.states.get("binary_sensor.g330_motion") is None
    assert hass.states.get("sensor.g330_last_motion") is None
    assert hass.states.get("sensor.g330_last_snapshot").state == "2025-10-17T11:20:00+00:00"
    assert er.async_get(hass).async_get("sensor.g330_battery_voltage").disabled


async def test_state_event_updates(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    bridge.cameras["G330"].update(
        connected=True, battery={**bridge.cameras["G330"]["battery"], "percent": 87}
    )
    await bridge.push("G330")
    await settle(hass)
    assert hass.states.get("binary_sensor.g330_camera_link").state == STATE_ON
    assert hass.states.get("sensor.g330_battery").state == "87"


async def test_commands(hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.g330_status_led"}, blocking=True
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.g330_infrared", "option": "off"},
        blocking=True,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.g330_restart"}, blocking=True
    )
    await settle(hass)
    sent = [(c["command"], c["camera"], c["args"]) for c in bridge.commands]
    assert sent == [
        ("led", "G330", {"on": False}),
        ("ir", "G330", {"state": "off"}),
        ("reboot", "G330", {}),
    ]
    assert hass.states.get("switch.g330_status_led").state == STATE_OFF
    assert hass.states.get("select.g330_infrared").state == "off"


async def test_command_error(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    bridge.cameras["G330"]["fail"] = True
    with pytest.raises(HomeAssistantError, match="camera asleep"):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.g330_siren"}, blocking=True
        )


async def test_camera(hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    # RTSP credentials from the app discovery, with special characters URL-encoded.
    assert (
        await async_get_stream_source(hass, "camera.g330")
        == "rtsp://ha:p%40ss%20word@127.0.0.1:8564/G330/sub#timeout=60"
    )
    image = await async_get_image(hass, "camera.g330")
    assert image.content == JPEG
    assert bridge.snapshots[-1] == {"cached": "true"}
    # Without a cached snapshot the bridge returns 404 and HA gets no image (camera keeps sleeping).
    bridge.cached = None
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.g330")


async def test_push_motion(hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry) -> None:
    bridge.cameras["G330"].update(motion_enabled=True, motion=False)
    await setup(hass, entry)
    assert hass.states.get("binary_sensor.g330_motion").state == STATE_OFF
    assert hass.states.get("sensor.g330_last_motion").state == "unknown"
    # Push notification: the bridge turns motion on and stores the time, off after a timeout.
    bridge.cameras["G330"].update(motion=True, last_motion=1760710000)
    await bridge.push("G330")
    await settle(hass)
    assert hass.states.get("binary_sensor.g330_motion").state == STATE_ON
    assert hass.states.get("sensor.g330_last_motion").state == "2025-10-17T14:06:40+00:00"
    assert hass.states.get("sensor.g330_last_detection").state == "unknown"
    # Detection type from the push (ALMTYPE); an unknown type -> "other".
    bridge.cameras["G330"].update(last_detection="vehicle")
    await bridge.push("G330")
    await settle(hass)
    assert hass.states.get("sensor.g330_last_detection").state == "vehicle"
    bridge.cameras["G330"].update(last_detection="visitor")
    await bridge.push("G330")
    await settle(hass)
    assert hass.states.get("sensor.g330_last_detection").state == "other"
    bridge.cameras["G330"].update(motion=False)
    await bridge.push("G330")
    await settle(hass)
    assert hass.states.get("binary_sensor.g330_motion").state == STATE_OFF


async def test_snapshot_button(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.g330_take_snapshot"}, blocking=True
    )
    # Fresh still only on demand: the command wakes the camera, the camera entity reads the cache.
    assert bridge.commands[-1]["command"] == "snapshot"


async def test_reconnect(hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry) -> None:
    await setup(hass, entry)
    await bridge.drop_clients()
    await settle(hass)
    # After a disconnect the client reconnects (no delay in tests) and entities come back.
    assert hass.states.get("sensor.g330_battery").state == "100"
    assert len(bridge.sockets) == 1


async def test_unavailable_when_bridge_down(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    bridge.closing = True
    await bridge.drop_clients()
    await settle(hass)
    assert hass.states.get("sensor.g330_battery").state == STATE_UNAVAILABLE


async def test_new_camera_reloads_entry(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    bridge.cameras["Garden"] = {
        **bridge.cameras["G330"],
        "name": "Garden",
        "uid": "95270003TESTUID2",
    }
    await bridge.push("Garden")
    await settle(hass)
    assert hass.states.get("sensor.garden_battery").state == "100"


async def test_settings_entities(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert hass.states.get("number.g330_pir_sensitivity").state == "41"
    assert hass.states.get("switch.g330_reduce_false_alarms").state == STATE_ON
    assert hass.states.get("switch.g330_recording").state == STATE_ON
    assert hass.states.get("switch.g330_alarm_sound_on_detection").state == STATE_OFF
    select = hass.states.get("select.g330_post_detection_recording")
    assert select.state == "15 s"
    assert select.attributes["options"] == ["8 s", "15 s", "30 s"]

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.g330_pir_sensitivity", "value": 60},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.g330_post_detection_recording", "option": "30 s"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.g330_alarm_sound_on_detection"}, blocking=True
    )
    await settle(hass)
    assert [(c["command"], c["args"]) for c in bridge.commands[-3:]] == [
        ("pir_sensitivity", {"value": 60}),
        ("post_record", {"seconds": 30}),
        ("alarm_sound", {"on": True}),
    ]
    assert hass.states.get("number.g330_pir_sensitivity").state == "60"
    assert hass.states.get("select.g330_post_detection_recording").state == "30 s"
    assert hass.states.get("switch.g330_alarm_sound_on_detection").state == STATE_ON


async def test_images(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_client
) -> None:
    await setup(hass, entry)
    client = await hass_client()
    # Last snapshot from the bridge cache; no event yet.
    assert hass.states.get("image.g330_last_snapshot").state == "2025-10-17T11:20:00+00:00"
    assert hass.states.get("image.g330_last_event").state == "unknown"
    resp = await client.get("/api/image_proxy/image.g330_last_snapshot")
    assert resp.status == 200 and await resp.read() == JPEG
    assert bridge.snapshots[-1] == {"cached": "true"}

    # After motion the bridge stores the event snapshot and reports its time.
    bridge.event = b"event-jpeg"
    bridge.cameras["G330"]["event_snapshot_at"] = 1760710000
    await bridge.push("G330")
    await settle(hass)
    assert hass.states.get("image.g330_last_event").state == "2025-10-17T14:06:40+00:00"
    resp = await client.get("/api/image_proxy/image.g330_last_event")
    assert resp.status == 200 and await resp.read() == b"event-jpeg"
    assert bridge.snapshots[-1] == {"event": "true"}


async def test_storage_signal_push(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert hass.states.get("sensor.g330_sd_card_used").state == "34.1"
    assert hass.states.get("sensor.g330_sd_card_free").state == "37.566"
    assert hass.states.get("sensor.g330_sd_card_capacity").state == "57.0"
    assert hass.states.get("sensor.g330_4g_signal").state == "5"
    assert hass.states.get("sensor.g330_mobile_operator").state == "Play"
    assert er.async_get(hass).async_get("sensor.g330_4g_signal_value").disabled
    assert hass.states.get("switch.g330_push_notifications").state == STATE_ON
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.g330_push_notifications"}, blocking=True
    )
    await settle(hass)
    assert bridge.commands[-1]["command"] == "push"
    assert hass.states.get("switch.g330_push_notifications").state == STATE_OFF
    # Card removed: unknown instead of zeros.
    bridge.cameras["G330"]["storage"] = {**bridge.cameras["G330"]["storage"], "mounted": False}
    await bridge.push("G330")
    await settle(hass)
    assert hass.states.get("sensor.g330_sd_card_used").state == "unknown"

"""Talking through the camera's speaker: the dashboard contract and the relay to the bridge."""

from __future__ import annotations

from aiohttp import WSMsgType
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neolink.talk import answer, is_state, talk_rate

from .conftest import FakeBridge
from .test_init import setup

PCM = b"\x01\x00\x02\x00" * 480


async def talk(hass_client, path: str, frames: int) -> tuple[list[dict], dict | None]:
    """Talk like the dashboard: binary PCM frames, then "stop". Returns the states heard on the way
    and the outcome (the message with `ok`)."""
    client = await hass_client()
    states: list[dict] = []
    async with client.ws_connect(path) as ws:
        for _ in range(frames):
            await ws.send_bytes(PCM)
        await ws.send_str("stop")
        async for message in ws:
            if message.type is not WSMsgType.TEXT:
                break
            data = message.json()
            if "ok" in data:
                return states, data
            states.append(data)
    return states, None


async def test_the_camera_says_where_to_talk(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert hass.states.get("camera.g330").attributes["talk_path"] == "/api/neolink/talk/G330"


async def test_the_microphone_reaches_the_bridge(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_client
) -> None:
    await setup(hass, entry)
    states, outcome = await talk(hass_client, "/api/neolink/talk/G330?rate=16000", frames=3)
    # The page hears the camera waking and answering before the outcome
    assert states == [{"state": "connecting"}, {"state": "connected"}]
    assert outcome == {"ok": True}
    assert bridge.talks == [{"camera": "G330", "rate": "16000", "frames": [PCM, PCM, PCM]}]


async def test_a_refusal_of_the_bridge_reaches_the_page(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_client
) -> None:
    await setup(hass, entry)
    bridge.talk_error = "busy"
    states, outcome = await talk(hass_client, "/api/neolink/talk/G330?rate=48000", frames=1)
    assert states == [{"state": "connecting"}]
    assert outcome == {"ok": False, "error": "busy"}


async def test_an_unknown_camera_is_not_found(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_client
) -> None:
    await setup(hass, entry)
    client = await hass_client()
    response = await client.get("/api/neolink/talk/Garden?rate=48000")
    assert response.status == 404


async def test_talking_needs_a_login(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry, hass_client_no_auth
) -> None:
    await setup(hass, entry)
    client = await hass_client_no_auth()
    response = await client.get("/api/neolink/talk/G330?rate=48000")
    assert response.status == 401
    assert bridge.talks == []


@pytest.mark.parametrize(
    ("value", "rate"),
    [("16000", 16000), ("48000", 48000), ("96000", 48000), ("x", 48000), (None, 48000)],
)
def test_rates_the_bridge_takes(value, rate) -> None:
    assert talk_rate(value) == rate


def test_states_are_told_from_the_outcome() -> None:
    assert is_state('{"state": "connecting"}')
    assert not is_state('{"ok": true}')
    assert not is_state('{"ok": false, "state": "connected"}')
    assert not is_state("garbage")


def test_answers_that_are_not_an_outcome_are_failures() -> None:
    assert answer('{"ok": true}') == {"ok": True}
    assert answer("garbage") == {"ok": False, "error": "failed"}
    assert answer("[1]") == {"ok": False, "error": "failed"}

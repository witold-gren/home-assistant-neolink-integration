"""Entity ids are English in a Polish installation; the shown names stay translated."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import FakeBridge
from .test_init import setup


def _polish_entity_ids(hass: HomeAssistant, entry_id: str) -> list[str]:
    """Entity ids that end with the Polish name (what HA builds in a Polish installation)."""
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry_id)
    assert entries
    return [
        e.entity_id
        for e in entries
        if e.original_name
        and e.entity_id.split(".")[1].endswith(slugify(e.original_name))
        and not e.entity_id.split(".")[1].endswith(slugify(e.object_id_base or ""))
    ]


async def test_entity_ids_are_english(
    hass: HomeAssistant, bridge: FakeBridge, entry: MockConfigEntry
) -> None:
    hass.config.language = "pl"
    await setup(hass, entry)

    assert _polish_entity_ids(hass, entry.entry_id) == []
    battery = hass.states.get("sensor.g330_battery")  # device class name, no key
    assert battery.attributes["friendly_name"] == "G330 Bateria"
    temperature = hass.states.get("sensor.g330_battery_temperature")  # translation key
    assert temperature.attributes["friendly_name"] == "G330 Temperatura baterii"
    assert hass.states.get("button.g330_restart") is not None

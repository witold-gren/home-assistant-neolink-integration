"""Config flow: manual setup and app discovery through the Supervisor."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neolink.const import DOMAIN

from .conftest import TOKEN, FakeBridge


def user_input(port: int, token: str = TOKEN) -> dict:
    return {
        "host": "127.0.0.1",
        "port": port,
        "token": token,
        "rtsp_port": 8564,
        "rtsp_username": "",
        "rtsp_password": "",
    }


async def test_user_flow(hass: HomeAssistant, bridge: FakeBridge) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(bridge.port, "wrong")
    )
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input(1))
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(bridge.port)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["token"] == TOKEN


def discovery(port: int) -> HassioServiceInfo:
    return HassioServiceInfo(
        config={
            "host": "127.0.0.1",
            "port": port,
            "token": TOKEN,
            "rtsp_port": 8564,
            "rtsp_username": "ha",
            "rtsp_password": "x",
        },
        name="Neolink",
        slug="local_neolink",
        uuid="addon-uuid",
    )


async def test_hassio_discovery(hass: HomeAssistant, bridge: FakeBridge) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=discovery(bridge.port)
    )
    assert result["step_id"] == "hassio_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["rtsp_username"] == "ha"
    assert result["result"].unique_id == "addon-uuid"


async def test_hassio_discovery_updates_existing(hass: HomeAssistant, bridge: FakeBridge) -> None:
    existing = MockConfigEntry(
        domain=DOMAIN, unique_id="addon-uuid", data={**user_input(1), "token": "old"}
    )
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=discovery(bridge.port)
    )
    assert result["type"] is FlowResultType.ABORT
    assert existing.data["token"] == TOKEN and existing.data["port"] == bridge.port


async def test_hassio_discovery_takes_over_reinstalled_app(
    hass: HomeAssistant, bridge: FakeBridge
) -> None:
    existing = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_HASSIO,
        unique_id="old-addon-uuid",
        data={**user_input(1), "token": "old"},
    )
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=discovery(bridge.port)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing.unique_id == "addon-uuid"
    assert existing.data["port"] == bridge.port
    assert existing.data["token"] == TOKEN
    assert existing.data["rtsp_port"] == 8564
    assert existing.data["rtsp_username"] == "ha"
    assert existing.data["rtsp_password"] == "x"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

"""Common entity base: camera device and updates from bridge events."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .api import CameraState, NeolinkClient, NeolinkError
from .const import DOMAIN
from .entity_ids import english_object_id


class NeolinkEntity(Entity):
    """Entity of a single camera; state comes from `client.cameras[name]`."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: NeolinkClient, camera: str, key: str) -> None:
        self._client = client
        self._camera = camera
        state = client.cameras[camera]
        device_id = state.get("uid") or camera
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=camera,
            manufacturer="Reolink",
            model=state.get("model") or "Neolink",
            sw_version=state.get("firmware"),
            hw_version=state.get("hardware"),
            serial_number=state.get("serial"),
        )

    @property
    def suggested_object_id(self) -> str | None:
        """English name for the entity id in every HA language (the shown name is translated)."""
        return english_object_id(
            self.platform.domain,
            self.translation_key,
            self.device_class,
            super().suggested_object_id,
        )

    @property
    def state_data(self) -> CameraState:
        """Latest camera state from the bridge."""
        return self._client.cameras.get(self._camera, {})

    @property
    def available(self) -> bool:
        # A camera disconnected while idle still has its last values: only the bridge link matters.
        return self._client.connected and self._camera in self._client.cameras

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._client.add_listener(self.async_write_ha_state))

    async def _command(self, command: str, **args: Any) -> None:
        try:
            await self._client.command(command, self._camera, **args)
        except NeolinkError as err:
            raise HomeAssistantError(f"{self._camera}: {err}") from err

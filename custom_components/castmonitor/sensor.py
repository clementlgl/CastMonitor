"""Sensor platform for CastMonitor."""

from __future__ import annotations

import logging
import time
from typing import Any

import pychromecast
from pychromecast.controllers.media import MediaStatus

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_HOST, CONF_NAME, CONF_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CastMonitor sensor from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    name = entry.data[CONF_NAME]
    title_sensor = CastMonitorTitleSensor(host, port, name)
    state_sensor = CastMonitorSensor(hass, host, port, name, title_sensor)
    async_add_entities([state_sensor, title_sensor])


def _player_state_from_media_status(
    media_status: MediaStatus | None, app_name: str | None
) -> str:
    """Compute a clean state string from a pychromecast MediaStatus."""
    if media_status is None:
        return "stopped"
    player_state = (getattr(media_status, "player_state", "") or "").upper()
    if player_state == "PLAYING":
        return "playing"
    if player_state == "PAUSED":
        return "paused"
    if player_state == "UNKNOWN" and str(app_name or "").lower().startswith("vlc"):
        return "playing"
    return "stopped"


def _title_from_media_status(media_status: MediaStatus | None) -> str | None:
    """Extract the best available title from MediaStatus."""
    if media_status is None:
        return None

    title = getattr(media_status, "title", None)
    if title:
        return title

    media_metadata = getattr(media_status, "media_metadata", None) or {}
    if isinstance(media_metadata, dict):
        for key in ("title", "episode", "seriesTitle", "albumName", "artist"):
            value = media_metadata.get(key)
            if value:
                return str(value)

    content_id = getattr(media_status, "content_id", None)
    if content_id:
        return str(content_id)

    return None


class CastMonitorSensor(SensorEntity):
    """Expose playback state for a single Chromecast device (push-based)."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, host: str, port: int, name: str, title_sensor: "CastMonitorTitleSensor") -> None:
        self.hass = hass
        self._host = host
        self._port = port
        self._device_name = name
        self._title_sensor = title_sensor
        self._attr_unique_id = f"castmonitor_{host.replace('.', '_')}_{port}"
        self._attr_name = f"{name} Player"
        self._attr_native_value = "stopped"
        self._app_name: str | None = None
        self._title: str | None = None
        self._cast: pychromecast.Chromecast | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name=name,
            manufacturer="Google",
            model="Chromecast",
        )

    @property
    def suggested_object_id(self) -> str:
        """Use device name as slug so entity_id is sensor.<device_name>_player."""
        return f"{self._device_name.lower().replace(' ', '_')}_player"

    @property
    def icon(self) -> str:
        if self._attr_native_value == "playing":
            return "mdi:cast-connected"
        return "mdi:cast"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "app_name": self._app_name,
            "title": self._title,
            "ip": self._host,
            "port": self._port,
        }

    async def async_added_to_hass(self) -> None:
        """Open the persistent connection and register listeners."""
        await self.hass.async_add_executor_job(self._connect)

    async def async_will_remove_from_hass(self) -> None:
        """Close the persistent connection."""
        await self.hass.async_add_executor_job(self._disconnect)

    # ------------------------------------------------------------------
    # Internal — executor helpers
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Open connection and attach listeners. Runs in executor."""
        try:
            cast = pychromecast.get_chromecast_from_host(
                (self._host, self._port, None, self._device_name, None)
            )
            cast.wait(timeout=10)
        except Exception as err:
            _LOGGER.warning(
                "CastMonitor: cannot connect to %s:%s — %s", self._host, self._port, err
            )
            self.hass.loop.call_soon_threadsafe(self._set_unreachable)
            return

        self._cast = cast
        cast.register_status_listener(_CastStatusListener(self))
        cast.register_connection_listener(_ConnectionListener(self))
        cast.media_controller.register_status_listener(_MediaStatusListener(self))
        cast.media_controller.update_status()

        # Wait for the async status response before reading it
        time.sleep(1)

        self.hass.loop.call_soon_threadsafe(
            self._apply_cast_state, cast, cast.media_controller.status
        )

    def _disconnect(self) -> None:
        """Disconnect gracefully. Runs in executor."""
        cast = self._cast
        self._cast = None
        if cast is not None:
            try:
                cast.disconnect(timeout=3)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # State helpers — called from the HA event loop via call_soon_threadsafe
    # ------------------------------------------------------------------

    def _set_unreachable(self) -> None:
        self._attr_native_value = "unreachable"
        self._app_name = None
        self._title = None
        self._title_sensor.set_title(None)
        self.async_write_ha_state()

    def _apply_cast_state(
        self,
        cast: pychromecast.Chromecast,
        media_status: MediaStatus | None,
    ) -> None:
        app_name = (
            getattr(cast, "app_display_name", None)
            or getattr(cast, "app_id", None)
            or None
        )
        self._app_name = app_name
        self._title = _title_from_media_status(media_status)
        self._title_sensor.set_title(self._title)
        self._attr_native_value = _player_state_from_media_status(media_status, app_name)
        if self._attr_native_value == "stopped" and getattr(cast, "is_idle", False):
            self._attr_native_value = "idle"
        self.async_write_ha_state()

    def _apply_media_status(self, status: MediaStatus) -> None:
        cast = self._cast
        if cast is not None:
            self._app_name = (
                getattr(cast, "app_display_name", None)
                or getattr(cast, "app_id", None)
                or self._app_name
            )
        self._title = _title_from_media_status(status)
        self._title_sensor.set_title(self._title)
        self._attr_native_value = _player_state_from_media_status(status, self._app_name)
        self.async_write_ha_state()

    def _update_app_name(self, app_name: str | None) -> None:
        self._app_name = app_name
        self.async_write_ha_state()

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt from the HA event loop."""
        self.hass.async_create_task(self._async_reconnect())

    async def _async_reconnect(self) -> None:
        """Reconnect after a short delay."""
        import asyncio  # noqa: PLC0415
        await asyncio.sleep(15)
        if self._cast is None:
            await self.hass.async_add_executor_job(self._connect)


class CastMonitorTitleSensor(SensorEntity):
    """Expose the current media title for a Chromecast device."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_icon = "mdi:music-note"

    def __init__(self, host: str, port: int, name: str) -> None:
        self._attr_unique_id = f"castmonitor_{host.replace('.', '_')}_{port}_title"
        self._attr_name = f"{name} Title"
        self._attr_native_value = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name=name,
            manufacturer="Google",
            model="Chromecast",
        )

    @property
    def suggested_object_id(self) -> str:
        return f"{self._attr_name.lower().replace(' ', '_')}"

    def set_title(self, title: str | None) -> None:
        """Called by the state sensor whenever the title changes."""
        self._attr_native_value = title
        if self.hass is not None:
            self.async_write_ha_state()


class _CastStatusListener:
    """Receives cast-level status updates (app name, volume) from pychromecast thread."""

    def __init__(self, sensor: CastMonitorSensor) -> None:
        self._sensor = sensor

    def new_cast_status(self, status: Any) -> None:
        app_name = getattr(status, "display_name", None) or getattr(status, "app_id", None)
        self._sensor.hass.loop.call_soon_threadsafe(
            self._sensor._update_app_name, app_name
        )


class _MediaStatusListener:
    """Receives media status updates from pychromecast (runs in pychromecast thread)."""

    def __init__(self, sensor: CastMonitorSensor) -> None:
        self._sensor = sensor

    def new_media_status(self, status: MediaStatus) -> None:
        self._sensor.hass.loop.call_soon_threadsafe(
            self._sensor._apply_media_status, status
        )

    def load_media_failed(self, item: Any, error_code: int) -> None:
        pass


class _ConnectionListener:
    """Receives connection status updates (runs in pychromecast thread)."""

    def __init__(self, sensor: CastMonitorSensor) -> None:
        self._sensor = sensor

    def new_connection_status(self, status: Any) -> None:
        conn_status = getattr(status, "status", status)
        s = str(conn_status).upper()
        if "CONNECTED" in s and "DIS" not in s:
            cast = self._sensor._cast
            if cast is not None:
                self._sensor.hass.loop.call_soon_threadsafe(
                    self._sensor._apply_cast_state,
                    cast,
                    cast.media_controller.status,
                )
        elif any(x in s for x in ("DISCONNECTED", "FAILED", "LOST")):
            self._sensor.hass.loop.call_soon_threadsafe(self._sensor._set_unreachable)
            self._sensor.hass.loop.call_soon_threadsafe(self._sensor._schedule_reconnect)

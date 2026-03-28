"""Sensor platform for CastMonitor."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import pychromecast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_HOST, CONF_NAME, CONF_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

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
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    async_add_entities([CastMonitorSensor(host, port, name, scan_interval)], True)


class CastMonitorSensor(SensorEntity):
    """Expose playback state for a single Chromecast device."""

    _attr_has_entity_name = False

    def __init__(self, host: str, port: int, name: str, scan_interval_seconds: int) -> None:
        self._host = host
        self._port = port
        self._scan_interval_seconds = scan_interval_seconds
        self._attr_name = name
        self._attr_unique_id = f"castmonitor_{host.replace('.', '_')}_{port}"
        self._attr_native_value = "stopped"
        self._app_name: str | None = None
        self._title: str | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name=name,
            manufacturer="Google",
            model="Chromecast",
        )

    @property
    def icon(self) -> str:
        if self._attr_native_value == "playing":
            return "mdi:cast-connected"
        return "mdi:cast"

    @property
    def scan_interval(self) -> timedelta:
        return timedelta(seconds=self._scan_interval_seconds)

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "app_name": self._app_name,
            "title": self._title,
            "ip": self._host,
            "port": self._port,
        }

    async def async_update(self) -> None:
        """Fetch playback state from the Chromecast device."""
        state, app_name, title = await self.hass.async_add_executor_job(
            self._sync_fetch
        )
        self._attr_native_value = state
        self._app_name = app_name
        self._title = title

    def _sync_fetch(self) -> tuple[str, str | None, str | None]:
        """Connect to the device and read its playback state. Runs in executor."""
        cast = None
        try:
            cast = pychromecast.get_chromecast_from_host(
                (self._host, self._port, None, self._attr_name, None)
            )
            cast.wait(timeout=5)

            app_name = (
                getattr(cast, "app_display_name", None)
                or getattr(cast, "app_id", None)
                or "Unknown"
            )

            media_controller = getattr(cast, "media_controller", None)
            media_status = (
                getattr(media_controller, "status", None) if media_controller else None
            )
            player_state = (
                getattr(media_status, "player_state", "") or ""
            ).upper()

            if player_state == "PLAYING":
                state = "playing"
            elif player_state == "PAUSED":
                state = "paused"
            elif player_state == "UNKNOWN" and str(app_name).lower().startswith("vlc"):
                state = "playing"
            elif getattr(cast, "is_idle", False):
                state = "idle"
            else:
                state = "stopped"

            title = getattr(media_status, "title", None)
            return state, app_name, title

        except Exception as err:
            _LOGGER.debug("Device %s:%s read error: %s", self._host, self._port, err)
            return "unreachable", None, None
        finally:
            if cast and hasattr(cast, "disconnect"):
                try:
                    cast.disconnect(timeout=3)
                except Exception:
                    pass


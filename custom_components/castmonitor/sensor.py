"""Sensor platform for CastMonitor."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import pychromecast
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the CastMonitor sensor from YAML."""
    scan_interval = config[CONF_SCAN_INTERVAL]
    async_add_entities([CastMonitorSensor(scan_interval)], True)


class CastMonitorSensor(SensorEntity):
    """Expose active Chromecast playback count and details."""

    _attr_name = "CastMonitor Active Streams"
    _attr_icon = "mdi:cast-connected"

    def __init__(self, scan_interval: timedelta) -> None:
        self._attr_native_value = 0
        self._scan_interval = scan_interval
        self._devices: list[dict[str, Any]] = []

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed playback states per device."""
        return {
            "playing_count": self._attr_native_value,
            "device_count": len(self._devices),
            "devices": self._devices,
        }

    @property
    def should_poll(self) -> bool:
        """Polling is enabled."""
        return True

    @property
    def scan_interval(self) -> timedelta:
        """Return entity polling interval."""
        return self._scan_interval

    async def async_update(self) -> None:
        """Fetch data from Chromecast devices."""
        devices = await self.hass.async_add_executor_job(self._sync_scan)
        self._devices = devices
        self._attr_native_value = sum(1 for item in devices if item.get("state") == "playing")

    def _sync_scan(self) -> list[dict[str, Any]]:
        """Run blocking Chromecast discovery and status collection."""
        results: list[dict[str, Any]] = []

        try:
            chromecasts, _browser = pychromecast.discovery.discover_chromecasts(timeout=5)
        except Exception as err:
            _LOGGER.error("Discovery failed: %s", err)
            return results

        for cast_info in chromecasts:
            device = {
                "device_name": cast_info.friendly_name,
                "ip": cast_info.host,
                "app_name": "Unknown",
                "state": "stopped",
                "title": None,
            }

            cast = None
            try:
                host_tuple = (cast_info.host, cast_info.port, None, cast_info.friendly_name, cast_info.host)
                cast = pychromecast.get_chromecast_from_host(host_tuple)
                cast.wait()

                app_name = getattr(cast, "app_display_name", None) or getattr(cast, "app_id", None) or "Unknown"
                device["app_name"] = app_name

                media_controller = getattr(cast, "media_controller", None)
                media_status = getattr(media_controller, "status", None) if media_controller else None
                player_state = (getattr(media_status, "player_state", "") or "").upper()

                if player_state == "PLAYING":
                    device["state"] = "playing"
                elif player_state == "PAUSED":
                    device["state"] = "paused"
                elif getattr(cast, "is_idle", False):
                    device["state"] = "idle"
                else:
                    device["state"] = "stopped"

                device["title"] = getattr(media_status, "title", None)

                if player_state == "UNKNOWN" and str(app_name).lower().startswith("vlc"):
                    device["state"] = "playing"

            except Exception as err:
                _LOGGER.debug("Device %s read error: %s", cast_info.host, err)
                device["state"] = "unreachable"
            finally:
                if cast and hasattr(cast, "disconnect"):
                    try:
                        cast.disconnect(timeout=5)
                    except Exception:
                        pass

            results.append(device)

        return results

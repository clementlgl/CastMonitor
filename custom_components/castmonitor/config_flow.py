"""Config flow for CastMonitor."""

from __future__ import annotations

import logging

import pychromecast
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow

from .const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CastMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CastMonitor."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            name = user_input[CONF_NAME].strip()

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(
                    _validate_connection, host, port, name
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_PORT: port, CONF_NAME: name},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


def _validate_connection(host: str, port: int, name: str) -> None:
    """Try connecting to a Chromecast to validate the host/port. Runs in executor."""
    cast = pychromecast.get_chromecast_from_host((host, port, None, name, None))
    try:
        cast.wait(timeout=5)
    finally:
        try:
            cast.disconnect(timeout=3)
        except Exception:
            pass

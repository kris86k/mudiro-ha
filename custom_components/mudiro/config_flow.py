"""Config and options flow for Mudiro."""

from __future__ import annotations

import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_ADDRESS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

MAC_RE = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")


class MudiroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for one Mudiro heater."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Ask for the heater's BLE address and polling interval."""
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not MAC_RE.fullmatch(address):
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Mudiro",
                    data={
                        CONF_ADDRESS: address,
                        CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): str,
                vol.Required(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return MudiroOptionsFlow()


class MudiroOptionsFlow(config_entries.OptionsFlow):
    """Handle Mudiro options."""

    async def async_step_init(self, user_input=None):
        """Allow changing the read/poll interval from Home Assistant."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Current Home Assistant exposes the entry through this property
        # after the options flow has been initialized.
        current_interval = int(
            self.config_entry.options.get(
                CONF_POLL_INTERVAL,
                self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            )
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_POLL_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

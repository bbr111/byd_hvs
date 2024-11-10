"""ConfigFlow for BYD HVS Battery."""

import logging

import bydhvs
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DEFAULT_IP_ADDRESS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SHOW_CELL_TEMPERATURE,
    SHOW_CELL_VOLTAGE,
)

_LOGGER = logging.getLogger(__name__)


class BYDHVSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BYD HVS Battery."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            ip_address = user_input["ip_address"]
            port = user_input.get("port", DEFAULT_PORT)
            scan_interval = user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)

            # Validate the polling interval
            if scan_interval < 10:
                errors["scan_interval"] = "too_low"
            else:
                # Attempt to connect to the battery
                byd_hvs = bydhvs.BYDHVS(ip_address, port)
                try:
                    await byd_hvs.poll()
                    serial_number = byd_hvs.hvsSerial
                except bydhvs.BYDHVSTimeoutError as e:
                    _LOGGER.error("Timeout connecting to the BYD battery: %s", e)
                    errors["base"] = "timeout"
                except bydhvs.BYDHVSConnectionError as e:
                    _LOGGER.error("Error connecting to the BYD battery: %s", e)
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(serial_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"BYD Battery {(serial_number)}",
                        data=user_input,
                    )

        data_schema = vol.Schema(
            {
                vol.Required("ip_address", default=DEFAULT_IP_ADDRESS): str,
                vol.Optional("port", default=DEFAULT_PORT): int,
                vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): int,
                vol.Optional(SHOW_CELL_VOLTAGE, default=True): bool,
                vol.Optional(SHOW_CELL_TEMPERATURE, default=True): bool,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Handle Config Flow Options."""
        return BYDHVSOptionsFlowHandler(config_entry)


class BYDHVSOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle BYD HVS Battery options."""

    def __init__(self, config_entry) -> None:
        """Initialize BYDHVS options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage BYDHVS options."""
        errors = {}
        if user_input is not None:
            scan_interval = user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)

            # Validate the polling interval
            if scan_interval < 10:
                errors["base"] = "too_low"
            else:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={
                        **self._config_entry.data,
                        "scan_interval": scan_interval,
                        SHOW_CELL_VOLTAGE: user_input.get(SHOW_CELL_VOLTAGE, True),
                        SHOW_CELL_TEMPERATURE: user_input.get(
                            SHOW_CELL_TEMPERATURE, True
                        ),
                    },
                )
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "scan_interval",
                    default=self._config_entry.data.get(
                        "scan_interval", DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
                vol.Optional(
                    SHOW_CELL_VOLTAGE,
                    default=self._config_entry.data.get(SHOW_CELL_VOLTAGE, True),
                ): bool,
                vol.Optional(
                    SHOW_CELL_TEMPERATURE,
                    default=self._config_entry.data.get(SHOW_CELL_TEMPERATURE, True),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )

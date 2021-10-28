"""Config flow for Aurora ABB PowerOne integration."""
import logging

from aurorapy.client import AuroraError, AuroraSerialClient
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_ADDRESS, CONF_PORT

from .const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_ADDRESS,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    MAX_ADDRESS,
    MIN_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


def validate_and_connect(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    comport = data[CONF_PORT]
    address = data[CONF_ADDRESS]
    _LOGGER.debug("Intitialising com port=%s", comport)
    ret = {}
    ret["title"] = DEFAULT_INTEGRATION_TITLE
    try:
        client = AuroraSerialClient(address, comport, parity="N", timeout=1)
        client.connect()
        ret[ATTR_SERIAL_NUMBER] = client.serial_number()
        ret[ATTR_MODEL] = f"{client.version()} ({client.pn()})"
        ret[ATTR_FIRMWARE] = client.firmware(1)
        _LOGGER.info("Returning device info=%s", ret)
    except AuroraError as err:
        _LOGGER.warning("Could not connect to device=%s", comport)
        raise err
    finally:
        if client.serline.isOpen():
            client.close()

    # Return info we want to store in the config entry.
    return ret


def scan_comports():
    """Find and store available com ports for the GUI dropdown."""
    comports = serial.tools.list_ports.comports(include_links=True)
    comportslist = []
    for port in comports:
        comportslist.append(port.device)
        _LOGGER.debug("COM port option: %s", port.device)
    if len(comportslist) > 0:
        return comportslist, comportslist[0]
    _LOGGER.warning("No com ports found.  Need a valid RS485 device to communicate")
    return None, None


class AuroraABBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aurora ABB PowerOne."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialise the config flow."""
        self.config = None
        self._comportslist = None
        self._defaultcomport = None

    async def async_step_import(self, config: dict):
        """Import a configuration from config.yaml."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        conf = {}
        conf[ATTR_SERIAL_NUMBER] = "sn_unknown_yaml"
        conf[ATTR_MODEL] = "model_unknown_yaml"
        conf[ATTR_FIRMWARE] = "fw_unknown_yaml"
        conf[CONF_PORT] = config["device"]
        conf[CONF_ADDRESS] = config["address"]
        # config["name"] from yaml is ignored.

        await self.async_set_unique_id(self.flow_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=DEFAULT_INTEGRATION_TITLE, data=conf)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialised by the user."""

        errors = {}
        if self._comportslist is None:
            result = await self.hass.async_add_executor_job(scan_comports)
            self._comportslist, self._defaultcomport = result
            if self._defaultcomport is None:
                return self.async_abort(reason="no_serial_ports")

        # Handle the initial step.
        if user_input is not None:
            try:
                info = await self.hass.async_add_executor_job(
                    validate_and_connect, self.hass, user_input
                )
                info.update(user_input)
                # Bomb out early if someone has already set up this device.
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=info)

            except OSError as error:
                if error.errno == 19:  # No such device.
                    errors["base"] = "invalid_serial_port"
            except AuroraError as error:
                if "could not open port" in str(error):
                    errors["base"] = "cannot_open_serial_port"
                elif "No response after" in str(error):
                    errors["base"] = "cannot_connect"  # could be dark
                else:
                    _LOGGER.error(
                        "Unable to communicate with Aurora ABB Inverter at %s: %s %s",
                        user_input[CONF_PORT],
                        type(error),
                        error,
                    )
                    errors["base"] = "cannot_connect"
        # If no user input, must be first pass through the config.  Show  initial form.
        config_options = {
            vol.Required(CONF_PORT, default=self._defaultcomport): vol.In(
                self._comportslist
            ),
            vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): vol.In(
                range(MIN_ADDRESS, MAX_ADDRESS + 1)
            ),
        }
        schema = vol.Schema(config_options)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

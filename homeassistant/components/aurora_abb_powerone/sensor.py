"""Support for Aurora ABB PowerOne Solar Photvoltaic (PV) inverter."""

import logging

from aurorapy.client import AuroraError, AuroraSerialClient
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_NAME,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import InvalidStateError
import homeassistant.helpers.config_validation as cv

from .aurora_device import AuroraDevice
from .const import DEFAULT_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_ADDRESS, default=DEFAULT_ADDRESS): cv.positive_int,
        vol.Optional(CONF_NAME, default="Solar PV"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up based on configuration.yaml (DEPRECATED)."""
    _LOGGER.warning(
        "Loading aurora_abb_powerone via platform config is deprecated; The configuration"
        " has been migrated to a config entry and can be safely removed from configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up aurora_abb_powerone sensor based on a config entry."""
    entities = []

    sensortypes = [
        {"parameter": "instantaneouspower", "name": "Power Output"},
        {"parameter": "temperature", "name": "Temperature"},
    ]
    client = hass.data[DOMAIN][config_entry.unique_id]
    data = config_entry.data

    for sens in sensortypes:
        entities.append(AuroraSensor(client, data, sens["name"], sens["parameter"]))

    _LOGGER.debug("async_setup_entry adding %d entities", len(entities))
    async_add_entities(entities, True)


class AuroraSensor(AuroraDevice, SensorEntity):
    """Representation of a Sensor on a Aurora ABB PowerOne Solar inverter."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, client: AuroraSerialClient, data, name, typename):
        """Initialize the sensor."""
        super().__init__(client, data)
        if typename == "instantaneouspower":
            self.type = typename
            self._attr_native_unit_of_measurement = POWER_WATT
            self._attr_device_class = DEVICE_CLASS_POWER
        elif typename == "temperature":
            self.type = typename
            self._attr_native_unit_of_measurement = TEMP_CELSIUS
            self._attr_device_class = DEVICE_CLASS_TEMPERATURE
        else:
            raise InvalidStateError(f"Unrecognised typename '{typename}'")
        self._attr_name = f"{name}"
        self.availableprev = True

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            self.availableprev = self._attr_available
            self.client.connect()
            if self.type == "instantaneouspower":
                # read ADC channel 3 (grid power output)
                power_watts = self.client.measure(3, True)
                self._attr_native_value = round(power_watts, 1)
            elif self.type == "temperature":
                temperature_c = self.client.measure(21)
                self._attr_native_value = round(temperature_c, 1)
            self._attr_available = True

        except AuroraError as error:
            self._attr_state = None
            self._attr_native_value = None
            self._attr_available = False
            # aurorapy does not have different exceptions (yet) for dealing
            # with timeout vs other comms errors.
            # This means the (normal) situation of no response during darkness
            # raises an exception.
            # aurorapy (gitlab) pull request merged 29/5/2019. When >0.2.6 is
            # released, this could be modified to :
            # except AuroraTimeoutError as e:
            # Workaround: look at the text of the exception
            if "No response after" in str(error):
                _LOGGER.debug("No response from inverter (could be dark)")
            else:
                raise error
        finally:
            if self._attr_available != self.availableprev:
                if self._attr_available:
                    _LOGGER.info("Communication with %s back online", self.name)
                else:
                    _LOGGER.warning(
                        "Communication with %s lost",
                        self.name,
                    )
            if self.client.serline.isOpen():
                self.client.close()

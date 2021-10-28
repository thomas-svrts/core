"""Top level class for AuroraABBPowerOneSolarPV inverters and sensors."""
import logging

from aurorapy.client import AuroraSerialClient

from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


class AuroraDevice(Entity):
    """Representation of an Aurora ABB PowerOne device."""

    def __init__(self, client: AuroraSerialClient, data) -> None:
        """Initialise the basic device."""
        self._data = data
        self.type = "device"
        self.client = client
        self._available = True

    @property
    def unique_id(self) -> str:
        """Return the unique id for this device."""
        serial = self._data[ATTR_SERIAL_NUMBER]
        return f"{serial}_{self.type}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self._data[ATTR_SERIAL_NUMBER])},
            "manufacturer": MANUFACTURER,
            "model": self._data[ATTR_MODEL],
            "name": self._data.get(ATTR_DEVICE_NAME, DEFAULT_DEVICE_NAME),
            "sw_version": self._data[ATTR_FIRMWARE],
        }

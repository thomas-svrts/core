"""Provides functionality to notify people."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    DOMAIN,
)
from .legacy import (  # noqa: F401
    BaseNotificationService,
    async_reload,
    async_reset_platform,
    async_setup_legacy,
)

# Platform specific data
ATTR_TITLE_DEFAULT = "Home Assistant"

PLATFORM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): cv.string, vol.Optional(CONF_NAME): cv.string},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the notify services."""
    await async_setup_legacy(hass, config)

    return True

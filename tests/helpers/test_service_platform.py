"""Test the service platform helper."""
import asyncio
import logging
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_integration import ServiceIntegration
from homeassistant.helpers.service_platform import (
    SLOW_SETUP_WARNING,
    AddServicesCallback,
)

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_integration,
    mock_platform,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"
ENTRY_DOMAIN = "entry_domain"
PLATFORM = "test_platform"


async def test_platform_warn_slow_setup(hass):
    """Warn we log when platform setup takes a long time."""
    mock_setup_entry = AsyncMock()
    mock_integration(hass, MockModule(ENTRY_DOMAIN))
    mock_platform(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    with patch.object(hass.loop, "call_later") as mock_call:
        await service_integration.async_setup()
        assert await service_integration.async_setup_entry(entry)
        await hass.async_block_till_done()
        assert mock_call.called

        # mock_calls[0] is the warning message for integration setup
        # mock_calls[3] is the warning message for platform setup
        timeout, logger_method = mock_call.mock_calls[3][1][:2]

        assert timeout == SLOW_SETUP_WARNING
        assert logger_method == _LOGGER.warning
        assert mock_call().cancel.called


async def test_platform_error_slow_setup(hass, caplog):
    """Don't block startup more than SLOW_SETUP_MAX_WAIT."""
    called = []

    async def mock_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_services: AddServicesCallback,
    ) -> None:
        called.append(1)
        await asyncio.sleep(1)

    mock_integration(hass, MockModule(ENTRY_DOMAIN))
    mock_platform(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})

    with patch("homeassistant.helpers.service_platform.SLOW_SETUP_MAX_WAIT", 0):
        await service_integration.async_setup()
        assert not await service_integration.async_setup_entry(entry)
        await hass.async_block_till_done()

    assert len(called) == 1
    assert f"{DOMAIN}.{ENTRY_DOMAIN}" not in hass.config.components
    assert (
        f"Setup of platform {ENTRY_DOMAIN} is taking longer than 0 seconds"
        in caplog.text
    )

"""Test the service platform helper."""
import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_integration import ServiceIntegration
from homeassistant.helpers.service_platform import (
    SLOW_SETUP_WARNING,
    AddServicesCallback,
    ServiceDescription,
)

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    MockPlatformService,
    mock_integration,
    mock_platform,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"
ENTRY_DOMAIN = "entry_domain"
MOCK_SERVICES_YAML = {
    "mock": {
        "name": "Mock a service",
        "description": "This service mocks a service.",
        "fields": {},
    }
}
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


@pytest.mark.parametrize(
    "parallel_updates_constant, parallel_updates",
    [(None, asyncio.Semaphore(1)), (0, None), (2, asyncio.Semaphore(2))],
)
async def test_parallel_updates(hass, parallel_updates_constant, parallel_updates):
    """Test platform parallel_updates limit."""
    test_domain_integration = mock_integration(hass, MockModule(DOMAIN))
    test_domain_integration.file_path = Path("mock_path")
    mock_setup_entry = AsyncMock()
    mock_integration(hass, MockModule(ENTRY_DOMAIN))
    platform = mock_platform(
        hass,
        f"{ENTRY_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=mock_setup_entry),
    )
    entry = MockConfigEntry(domain=ENTRY_DOMAIN)
    service_integration = ServiceIntegration(hass, _LOGGER, DOMAIN, {DOMAIN: None})
    platform.PARALLEL_UPDATES = parallel_updates_constant

    await service_integration.async_setup()
    assert await service_integration.async_setup_entry(entry)
    await hass.async_block_till_done()

    async_add_services = mock_setup_entry.mock_calls[0][1][2]
    with patch(
        "homeassistant.helpers.service.load_yaml", return_value=MOCK_SERVICES_YAML
    ):
        async_add_services(
            [
                MockPlatformService(
                    service_name="test_service_mock",
                    service_description=ServiceDescription(
                        "mock",
                        "test_service_mock",
                        "Test a service",
                        "Description for testing a service",
                    ),
                    service_schema=vol.Schema({}),
                )
            ]
        )
        await hass.async_block_till_done()

    platform_services = list(service_integration.services)
    assert platform_services

    platform_service = platform_services[0]
    assert type(platform_service.parallel_updates) == type(parallel_updates)
    assert getattr(platform_service.parallel_updates, "_value", None) == getattr(
        parallel_updates, "_value", None
    )

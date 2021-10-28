"""Test websocket API."""
import pytest

from homeassistant.components.hassio.const import (
    ATTR_DATA,
    ATTR_ENDPOINT,
    ATTR_METHOD,
    ATTR_WS_EVENT,
    EVENT_SUPERVISOR_EVENT,
    WS_ID,
    WS_TYPE,
    WS_TYPE_API,
    WS_TYPE_SUBSCRIBE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from tests.common import async_mock_signal


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock):
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {"supervisor": "222", "homeassistant": "0.110.0", "hassos": None},
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "data": {
                    "chassis": "vm",
                    "operating_system": "Debian GNU/Linux 10 (buster)",
                    "kernel": "4.19.0-6-amd64",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )


async def test_ws_subscription(hassio_env, hass: HomeAssistant, hass_ws_client):
    """Test websocket subscription."""
    assert await async_setup_component(hass, "hassio", {})
    client = await hass_ws_client(hass)
    await client.send_json({WS_ID: 5, WS_TYPE: WS_TYPE_SUBSCRIBE})
    response = await client.receive_json()
    assert response["success"]

    calls = async_mock_signal(hass, EVENT_SUPERVISOR_EVENT)
    async_dispatcher_send(hass, EVENT_SUPERVISOR_EVENT, {"lorem": "ipsum"})

    response = await client.receive_json()
    assert response["event"]["lorem"] == "ipsum"
    assert len(calls) == 1

    await client.send_json(
        {
            WS_ID: 6,
            WS_TYPE: "supervisor/event",
            ATTR_DATA: {ATTR_WS_EVENT: "test", "lorem": "ipsum"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert len(calls) == 2

    response = await client.receive_json()
    assert response["event"]["lorem"] == "ipsum"

    # Unsubscribe
    await client.send_json({WS_ID: 7, WS_TYPE: "unsubscribe_events", "subscription": 5})
    response = await client.receive_json()
    assert response["success"]


async def test_websocket_supervisor_api(
    hassio_env, hass: HomeAssistant, hass_ws_client, aioclient_mock
):
    """Test Supervisor websocket api."""
    assert await async_setup_component(hass, "hassio", {})
    websocket_client = await hass_ws_client(hass)
    aioclient_mock.post(
        "http://127.0.0.1/backups/new/partial",
        json={"result": "ok", "data": {"slug": "sn_slug"}},
    )

    await websocket_client.send_json(
        {
            WS_ID: 1,
            WS_TYPE: WS_TYPE_API,
            ATTR_ENDPOINT: "/backups/new/partial",
            ATTR_METHOD: "post",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["result"]["slug"] == "sn_slug"

    await websocket_client.send_json(
        {
            WS_ID: 2,
            WS_TYPE: WS_TYPE_API,
            ATTR_ENDPOINT: "/supervisor/info",
            ATTR_METHOD: "get",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["result"]["version_latest"] == "1.0.0"


async def test_websocket_supervisor_api_error(
    hassio_env, hass: HomeAssistant, hass_ws_client, aioclient_mock
):
    """Test Supervisor websocket api error."""
    assert await async_setup_component(hass, "hassio", {})
    websocket_client = await hass_ws_client(hass)
    aioclient_mock.get(
        "http://127.0.0.1/ping",
        json={"result": "error", "message": "example error"},
    )

    await websocket_client.send_json(
        {
            WS_ID: 1,
            WS_TYPE: WS_TYPE_API,
            ATTR_ENDPOINT: "/ping",
            ATTR_METHOD: "get",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["error"]["message"] == "example error"

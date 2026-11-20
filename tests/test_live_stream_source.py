"""Live view uses getStreamUrl for every camera."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.const import API_ENDPOINT_LIST_DEVICE_DETAILS
from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient


@pytest.fixture
def ha_manager() -> ImouHaDeviceManager:
    client = ImouOpenApiClient("app", "secret", "api.example.com")
    return ImouHaDeviceManager(ImouDeviceManager(client))


def _camera(source: str) -> ImouHaDevice:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_source(source)
    return device


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["bind", "share", ""])
async def test_live_uses_get_stream_url(ha_manager, source: str) -> None:
    device = _camera(source)
    ha_manager.delegate.async_get_rtsp_stream_url = AsyncMock(
        return_value={"url": "rtsp://cdn.example/live"}
    )
    ha_manager.delegate.async_get_stream_url = AsyncMock()
    ha_manager.delegate.async_create_stream_url = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "HD", "https")

    assert url == "rtsp://cdn.example/live"
    ha_manager.delegate.async_get_stream_url.assert_not_awaited()
    ha_manager.delegate.async_create_stream_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_picks_sd_stream_id(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_get_rtsp_stream_url = AsyncMock(
        return_value={"url": "rtsp://cdn.example/sd"}
    )

    url = await ha_manager.async_get_device_stream(device, "SD", "https")

    assert url == "rtsp://cdn.example/sd"
    ha_manager.delegate.async_get_rtsp_stream_url.assert_awaited_once_with(
        "IPC1", "0", 1, None
    )


@pytest.mark.asyncio
async def test_device_detail_page_propagates_source_to_all_channels() -> None:
    client = ImouOpenApiClient("app", "secret", "api.example.com")

    async def fake_request(endpoint: str, params: dict) -> dict:
        assert endpoint == API_ENDPOINT_LIST_DEVICE_DETAILS
        if params.get("page") == 1:
            return {
                "count": 2,
                "deviceList": [
                    {
                        "deviceId": "DUAL1",
                        "deviceName": "Dual",
                        "deviceStatus": "online",
                        "brand": "lechange",
                        "deviceModel": "LC-TA4D",
                        "source": "bind",
                        "multiFlag": True,
                        "channelList": [
                            {"channelId": "0", "channelName": "Pan"},
                            {"channelId": "1", "channelName": "Fixed"},
                        ],
                    },
                    {
                        "deviceId": "SHARE1",
                        "deviceName": "Shared",
                        "deviceStatus": "online",
                        "brand": "lechange",
                        "deviceModel": "IPC",
                        "source": "share",
                        "channelList": [
                            {"channelId": "0", "channelName": "Main"},
                        ],
                    },
                ],
            }
        return {"count": 0, "deviceList": []}

    client.async_request_api = AsyncMock(side_effect=fake_request)
    manager = ImouHaDeviceManager(ImouDeviceManager(client))
    devices = await manager.async_get_devices(skip_device_ids={"DUAL1", "SHARE1"})

    by_key = {(d.device_id, d.channel_id): d.source for d in devices}
    assert by_key == {
        ("DUAL1", "0"): "bind",
        ("DUAL1", "1"): "bind",
        ("SHARE1", "0"): "share",
    }

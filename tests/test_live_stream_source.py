"""Owner cameras prefer FLV, then HLS; shared cameras keep getStreamUrl."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.const import (
    API_ENDPOINT_LIST_DEVICE_DETAILS,
    ERROR_CODE_LIVE_ALREADY_EXIST,
    ERROR_CODE_LIVE_NOT_EXIST,
)
from pyimouapi.device import ImouDeviceManager
from pyimouapi.exceptions import RequestFailedException
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


def _streams() -> dict:
    return {
        "streams": [
            {"streamId": 1, "hls": "https://cdn.example/sd.m3u8"},
            {"streamId": 0, "hls": "http://cdn.example/hd.m3u8"},
        ]
    }


@pytest.mark.asyncio
async def test_bind_prefers_realtime_flv(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_create_device_realtime_flv = AsyncMock(
        return_value={"url": "https://flv.example/live.flv"}
    )
    ha_manager.delegate.async_get_stream_url = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "HD", "http")

    assert url == "https://flv.example/live.flv"
    ha_manager.delegate.async_get_stream_url.assert_not_awaited()
    ha_manager.delegate.async_create_device_realtime_flv.assert_awaited_once_with(
        "IPC1", "0", prefer_hd=True
    )


@pytest.mark.asyncio
async def test_bind_queries_flv_when_create_says_it_exists(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_create_device_realtime_flv = AsyncMock(
        side_effect=RequestFailedException(
            "exists", api_code=ERROR_CODE_LIVE_ALREADY_EXIST
        )
    )
    ha_manager.delegate.async_query_device_realtime_flv = AsyncMock(
        return_value={"url": "https://flv.example/live.flv"}
    )
    ha_manager.delegate.async_get_stream_url = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "SD", "http")

    assert url == "https://flv.example/live.flv"
    ha_manager.delegate.async_query_device_realtime_flv.assert_awaited_once_with(
        "IPC1", "0", prefer_hd=False
    )
    ha_manager.delegate.async_get_stream_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_bind_falls_back_to_hls_when_flv_unavailable(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_create_device_realtime_flv = AsyncMock(
        side_effect=RequestFailedException("unsupported", api_code="DV1026")
    )
    ha_manager.delegate.async_get_stream_url = AsyncMock(
        side_effect=RequestFailedException(
            "missing", api_code=ERROR_CODE_LIVE_NOT_EXIST
        )
    )
    ha_manager.delegate.async_create_stream_url = AsyncMock(return_value=_streams())
    ha_manager.delegate.async_get_rtsp_stream_url = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "HD", "http")

    assert url == "http://cdn.example/hd.m3u8"
    ha_manager.delegate.async_get_rtsp_stream_url.assert_not_awaited()
    ha_manager.delegate.async_create_stream_url.assert_awaited_once_with("IPC1", "0")


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["share", ""])
async def test_non_bind_uses_get_stream_url(ha_manager, source: str) -> None:
    device = _camera(source)
    ha_manager.delegate.async_get_rtsp_stream_url = AsyncMock(
        return_value={"url": "rtsp://cdn.example/live"}
    )
    ha_manager.delegate.async_get_stream_url = AsyncMock()
    ha_manager.delegate.async_create_device_realtime_flv = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "HD", "http")

    assert url == "rtsp://cdn.example/live"
    ha_manager.delegate.async_get_stream_url.assert_not_awaited()
    ha_manager.delegate.async_create_device_realtime_flv.assert_not_awaited()


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

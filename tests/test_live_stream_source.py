"""bind cameras use getLiveStreamInfo; other sources keep getStreamUrl."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.const import (
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
            {"streamId": 0, "hls": "https://cdn.example/hd.m3u8"},
        ]
    }


@pytest.mark.asyncio
async def test_bind_creates_when_live_is_missing(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_get_stream_url = AsyncMock(
        side_effect=RequestFailedException(
            "missing", api_code=ERROR_CODE_LIVE_NOT_EXIST
        )
    )
    ha_manager.delegate.async_create_stream_url = AsyncMock(return_value=_streams())
    ha_manager.delegate.async_get_rtsp_stream_url = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "HD", "https")

    assert url == "https://cdn.example/hd.m3u8"
    ha_manager.delegate.async_get_rtsp_stream_url.assert_not_awaited()
    ha_manager.delegate.async_create_stream_url.assert_awaited_once_with("IPC1", "0")


@pytest.mark.asyncio
async def test_bind_queries_again_when_create_says_it_exists(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_get_stream_url = AsyncMock(
        side_effect=[
            RequestFailedException("missing", api_code=ERROR_CODE_LIVE_NOT_EXIST),
            _streams(),
        ]
    )
    ha_manager.delegate.async_create_stream_url = AsyncMock(
        side_effect=RequestFailedException(
            "exists", api_code=ERROR_CODE_LIVE_ALREADY_EXIST
        )
    )

    url = await ha_manager.async_get_device_stream(device, "SD", "https")

    assert url == "https://cdn.example/sd.m3u8"
    assert ha_manager.delegate.async_get_stream_url.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["share", ""])
async def test_non_bind_uses_get_stream_url(ha_manager, source: str) -> None:
    device = _camera(source)
    ha_manager.delegate.async_get_rtsp_stream_url = AsyncMock(
        return_value={"url": "rtsp://cdn.example/live"}
    )
    ha_manager.delegate.async_get_stream_url = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "HD", "https")

    assert url == "rtsp://cdn.example/live"
    ha_manager.delegate.async_get_stream_url.assert_not_awaited()

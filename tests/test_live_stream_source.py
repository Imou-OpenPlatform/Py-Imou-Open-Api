"""Owner cameras use cloud HLS; shared cameras keep getStreamUrl."""

import logging
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
            {"streamId": 1, "hls": "http://cdn.example/sd.m3u8"},
            {"streamId": 0, "hls": "http://cdn.example/hd.m3u8"},
        ]
    }


@pytest.mark.asyncio
async def test_bind_uses_cloud_hls(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_get_stream_url = AsyncMock(return_value=_streams())
    ha_manager.delegate.async_create_device_realtime_flv = AsyncMock()

    url = await ha_manager.async_get_device_stream(device, "HD", "http")

    assert url == "http://cdn.example/hd.m3u8"
    ha_manager.delegate.async_get_stream_url.assert_awaited_once_with("IPC1", "0")
    ha_manager.delegate.async_create_device_realtime_flv.assert_not_awaited()


@pytest.mark.parametrize(
    ("resolution", "protocol", "expected"),
    [
        ("HD", "http", "http://cdn.example/hd.m3u8"),
        ("HD", "https", "https://cdn.example/hd.m3u8"),
        ("SD", "http", "http://cdn.example/sd.m3u8"),
        ("SD", "https", "https://cdn.example/sd.m3u8"),
        ("HD", "", "https://cdn.example/hd.m3u8"),
        ("SD", "", "https://cdn.example/sd.m3u8"),
    ],
)
def test_pick_hls_url_matches_resolution_and_protocol(
    resolution: str, protocol: str, expected: str
) -> None:
    data = {
        "streams": [
            {"streamId": 0, "hls": "https://cdn.example/hd.m3u8"},
            {"streamId": 1, "hls": "https://cdn.example/sd.m3u8"},
            {"streamId": 0, "hls": "http://cdn.example/hd.m3u8"},
            {"streamId": 1, "hls": "http://cdn.example/sd.m3u8"},
        ]
    }

    assert ImouHaDeviceManager._pick_hls_url(data, resolution, protocol) == expected


@pytest.mark.parametrize(
    ("resolution", "protocol"),
    [("HD", "https"), ("SD", "https"), ("HD", "rtmp")],
)
def test_pick_hls_url_does_not_fall_back_on_protocol_mismatch(
    resolution: str, protocol: str
) -> None:
    with pytest.raises(RequestFailedException, match="live stream not found"):
        ImouHaDeviceManager._pick_hls_url(_streams(), resolution, protocol)


@pytest.mark.parametrize(("resolution", "stream_id"), [("HD", 1), ("SD", 0)])
def test_pick_hls_url_does_not_fall_back_on_resolution_mismatch(
    resolution: str, stream_id: int
) -> None:
    data = {"streams": [{"streamId": stream_id, "hls": "http://cdn.example/a.m3u8"}]}

    with pytest.raises(RequestFailedException, match="live stream not found"):
        ImouHaDeviceManager._pick_hls_url(data, resolution, "")


@pytest.mark.asyncio
async def test_bind_protocol_defaults_to_any_matching_stream(ha_manager) -> None:
    device = _camera("bind")
    ha_manager.delegate.async_get_stream_url = AsyncMock(return_value=_streams())

    assert await ha_manager.async_get_device_stream(device, "HD") == (
        "http://cdn.example/hd.m3u8"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "url", "safe_host"),
    [
        (
            "bind",
            "https://user:password@cdn.example:8443/hd/path-secret"
            "?token=query-secret#fragment-secret",
            "cdn.example:8443",
        ),
        (
            "share",
            "rtsp://user:password@cdn.example:554/path-secret"
            "?token=query-secret#fragment-secret",
            "cdn.example:554",
        ),
    ],
)
async def test_stream_debug_log_keeps_only_safe_host(
    ha_manager,
    caplog: pytest.LogCaptureFixture,
    source: str,
    url: str,
    safe_host: str,
) -> None:
    device = _camera(source)
    if source == "bind":
        ha_manager.delegate.async_get_stream_url = AsyncMock(
            return_value={"streams": [{"streamId": 0, "hls": url}]}
        )
    else:
        ha_manager.delegate.async_get_rtsp_stream_url = AsyncMock(
            return_value={"url": url}
        )

    with caplog.at_level(logging.DEBUG, logger="pyimouapi"):
        result = await ha_manager.async_get_device_stream(
            device, "HD", "https" if source == "bind" else ""
        )

    assert result == url
    assert safe_host in caplog.text
    for secret in ("user:password", "path-secret", "query-secret", "fragment-secret"):
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_bind_creates_hls_when_live_missing(ha_manager) -> None:
    device = _camera("bind")
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
async def test_bind_reuses_hls_when_create_says_it_exists(ha_manager) -> None:
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

    url = await ha_manager.async_get_device_stream(device, "SD", "http")

    assert url == "http://cdn.example/sd.m3u8"
    assert ha_manager.delegate.async_get_stream_url.await_count == 2


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

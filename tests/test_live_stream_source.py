"""Owner cameras use cloud HLS; shared cameras keep getStreamUrl."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    ERROR_CODE_LIVE_ALREADY_EXIST,
    ERROR_CODE_LIVE_NOT_EXIST,
    PARAM_HD,
)
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


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


def _manager() -> ImouHaDeviceManager:
    return ImouHaDeviceManager(MagicMock())


@pytest.mark.asyncio
async def test_bind_uses_cloud_hls() -> None:
    device = _camera("bind")
    manager = _manager()
    manager.delegate.async_get_stream_url = AsyncMock(return_value=_streams())
    manager.delegate.async_get_rtsp_stream_url = AsyncMock()

    url = await manager.async_get_device_stream(device, "HD", "http")

    assert url == "http://cdn.example/hd.m3u8"
    manager.delegate.async_get_stream_url.assert_awaited_once_with("IPC1", "0")
    manager.delegate.async_get_rtsp_stream_url.assert_not_awaited()


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
async def test_bind_protocol_defaults_to_any_matching_stream() -> None:
    device = _camera("bind")
    manager = _manager()
    manager.delegate.async_get_stream_url = AsyncMock(return_value=_streams())

    assert await manager.async_get_device_stream(device, PARAM_HD) == (
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
    caplog: pytest.LogCaptureFixture,
    source: str,
    url: str,
    safe_host: str,
) -> None:
    device = _camera(source)
    manager = _manager()
    if source == "bind":
        manager.delegate.async_get_stream_url = AsyncMock(
            return_value={"streams": [{"streamId": 0, "hls": url}]}
        )
    else:
        manager.delegate.async_get_rtsp_stream_url = AsyncMock(
            return_value={"url": url}
        )

    with caplog.at_level(logging.DEBUG, logger="pyimouapi"):
        result = await manager.async_get_device_stream(
            device, "HD", "https" if source == "bind" else ""
        )

    assert result == url
    assert safe_host in caplog.text
    for secret in ("user:password", "path-secret", "query-secret", "fragment-secret"):
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_bind_creates_hls_when_live_missing() -> None:
    device = _camera("bind")
    manager = _manager()
    manager.delegate.async_get_stream_url = AsyncMock(
        side_effect=RequestFailedException(f"{ERROR_CODE_LIVE_NOT_EXIST}:missing")
    )
    manager.delegate.async_create_stream_url = AsyncMock(return_value=_streams())
    manager.delegate.async_get_rtsp_stream_url = AsyncMock()

    url = await manager.async_get_device_stream(device, "HD", "http")

    assert url == "http://cdn.example/hd.m3u8"
    manager.delegate.async_get_rtsp_stream_url.assert_not_awaited()
    manager.delegate.async_create_stream_url.assert_awaited_once_with("IPC1", "0")


@pytest.mark.asyncio
async def test_bind_reuses_hls_when_create_says_it_exists() -> None:
    device = _camera("bind")
    manager = _manager()
    manager.delegate.async_get_stream_url = AsyncMock(
        side_effect=[
            RequestFailedException(f"{ERROR_CODE_LIVE_NOT_EXIST}:missing"),
            _streams(),
        ]
    )
    manager.delegate.async_create_stream_url = AsyncMock(
        side_effect=RequestFailedException(f"{ERROR_CODE_LIVE_ALREADY_EXIST}:exists")
    )

    url = await manager.async_get_device_stream(device, "SD", "http")

    assert url == "http://cdn.example/sd.m3u8"
    assert manager.delegate.async_get_stream_url.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["share", ""])
async def test_non_bind_uses_get_stream_url(source: str) -> None:
    device = _camera(source)
    manager = _manager()
    manager.delegate.async_get_rtsp_stream_url = AsyncMock(
        return_value={"url": "rtsp://cdn.example/live"}
    )
    manager.delegate.async_get_stream_url = AsyncMock()
    manager.delegate.async_create_stream_url = AsyncMock()

    url = await manager.async_get_device_stream(device, "HD", "http")

    assert url == "rtsp://cdn.example/live"
    manager.delegate.async_get_stream_url.assert_not_awaited()
    manager.delegate.async_create_stream_url.assert_not_awaited()

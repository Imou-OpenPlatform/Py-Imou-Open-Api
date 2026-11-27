"""deviceSnapDetect response parsing."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    API_ENDPOINT_DETECT_DEVICE_SNAP,
    API_ENDPOINT_DEVICE_SNAP_DETECT,
)
from pyimouapi.device import ImouDeviceManager
from pyimouapi.snap_detect import (
    DeviceSnapDetectResult,
    SnapDetectTarget,
    parse_detect_device_snap_data,
    parse_device_snap_detect_data,
)


def test_parse_empty_data() -> None:
    result = parse_device_snap_detect_data({})
    assert result == DeviceSnapDetectResult(None, False, ())


def test_parse_full_response() -> None:
    payload = {
        "url": "https://example.test/snap.jpg",
        "detectResult": "1",
        "targets": [
            {
                "targetType": "human",
                "confidence": "0.92",
                "targetRegion": {"x": 10, "width": 20, "height": 30},
            },
            {
                "targetType": "vehicle",
                "confidence": 0.8,
                "targetRegion": {"x": 1, "width": 2, "height": 3},
            },
        ],
    }
    result = parse_device_snap_detect_data(payload)
    assert result.url == "https://example.test/snap.jpg"
    assert result.detect_result is True
    assert len(result.targets) == 2
    assert result.targets[0] == SnapDetectTarget(
        "human", "0.92", {"x": 10, "width": 20, "height": 30}
    )
    assert parse_detect_device_snap_data(payload) == result


@pytest.mark.asyncio
async def test_detect_device_snap_calls_endpoint() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock(
        return_value={"url": "https://example.test/snap.jpg"}
    )
    manager = ImouDeviceManager(client)

    result = await manager.async_detect_device_snap("dev-1", "0")

    assert result == {"url": "https://example.test/snap.jpg"}
    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_DETECT_DEVICE_SNAP,
        {"deviceId": "dev-1", "channelId": "0"},
    )
    assert API_ENDPOINT_DETECT_DEVICE_SNAP == "/openapi/detectDeviceSnap"
    assert API_ENDPOINT_DEVICE_SNAP_DETECT == "/openapi/detectDeviceSnap"
    assert manager.async_device_snap_detect == manager.async_detect_device_snap

"""deviceSnapDetect response parsing."""

from pyimouapi.snap_detect import (
    DeviceSnapDetectResult,
    SnapDetectTarget,
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

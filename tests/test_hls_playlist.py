"""HLS playlist helpers for Imou record playback."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.device import ImouDeviceManager
from pyimouapi.playback.hls import (
    async_create_device_record_hls,
    normalize_imou_hls_segment_url,
    parse_hls_media_segment_urls,
    pick_hls_variant_playlist_url,
    validate_record_playback_window,
)


@pytest.mark.parametrize("record_type", ["localRecord", "cloudRecord"])
@pytest.mark.parametrize(
    ("begin_time", "end_time"),
    [
        ("2026-11-01 00:00:00", "2026-11-01 23:59:59"),
        ("2026-11-01 00:06:55", "2026-11-01 00:06:56"),
        ("2024-02-29 12:00:00", "2024-02-29 12:00:01"),
    ],
)
def test_validate_record_playback_window_accepts_valid_same_day_window(
    record_type: str, begin_time: str, end_time: str
) -> None:
    validate_record_playback_window(begin_time, end_time, record_type)


@pytest.mark.parametrize(
    ("begin_time", "end_time", "message"),
    [
        ("2026-11-01 00:06:55", "2026-11-01 00:06:55", "before end_time"),
        ("2026-11-01 00:06:56", "2026-11-01 00:06:55", "before end_time"),
        ("2026-11-01 23:59:00", "2026-11-02 00:01:00", "same calendar day"),
    ],
)
def test_validate_record_playback_window_rejects_invalid_window(
    begin_time: str, end_time: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_record_playback_window(begin_time, end_time, "cloudRecord")


@pytest.mark.parametrize(
    ("begin_time", "end_time"),
    [
        ("2026-02-29 12:00:00", "2026-02-29 12:00:01"),
        ("2026-11-01T00:00:00", "2026-11-01 00:00:01"),
        ("2026-11-01 00:00:00", "2026-11-01T00:00:01"),
        ("2026-11-01 00:00:00+08:00", "2026-11-01 00:00:01"),
        ("2026-11-01 00:00:00", "2026-11-01 00:00:01Z"),
        (" 2026-11-01 00:00:00", "2026-11-01 00:00:01"),
        ("2026-11-01 00:00:00", "2026-11-01 00:00:01 "),
        ("2026-1-01 00:00:00", "2026-01-01 00:00:01"),
        ("2026-11-01 00:00:00 extra", "2026-11-01 00:00:01"),
        (None, "2026-11-01 00:00:01"),
        ("2026-11-01 00:00:00", 1),
    ],
)
def test_validate_record_playback_window_rejects_malformed_times(
    begin_time: object, end_time: object
) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD HH:MM:SS"):
        validate_record_playback_window(begin_time, end_time, "localRecord")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "record_type",
    ["localrecord", "LocalRecord", "cloudrecord", "CloudRecord", "unknown", "", None],
)
def test_validate_record_playback_window_rejects_unknown_record_type(
    record_type: object,
) -> None:
    with pytest.raises(ValueError, match="localRecord or cloudRecord"):
        validate_record_playback_window(  # type: ignore[arg-type]
            "2026-11-01 00:00:00",
            "2026-11-01 00:00:01",
            record_type,
        )


@pytest.mark.parametrize("record_type", ["localRecord", "cloudRecord"])
async def test_invalid_window_does_not_request_hls(
    record_type: str,
) -> None:
    client = AsyncMock()

    with pytest.raises(ValueError, match="same calendar day"):
        await async_create_device_record_hls(
            client,
            device_id="device",
            channel_id="0",
            begin_time="2026-11-01 23:59:00",
            end_time="2026-11-02 00:01:00",
            record_type=record_type,
        )

    client.async_request_api.assert_not_awaited()


@pytest.mark.parametrize("record_type", ["localRecord", "cloudRecord"])
async def test_device_manager_invalid_window_does_not_request_hls(
    record_type: str,
) -> None:
    client = AsyncMock()
    manager = ImouDeviceManager(client)

    with pytest.raises(ValueError, match="before end_time"):
        await manager.async_create_device_record_hls(
            "device",
            "0",
            begin_time="2026-11-01 00:01:00",
            end_time="2026-11-01 00:01:00",
            record_type=record_type,
        )

    client.async_request_api.assert_not_awaited()


@pytest.mark.parametrize(
    ("record_type", "file_name"),
    [("localRecord", "/record/file.dav"), ("cloudRecord", None)],
)
async def test_valid_hls_request_payload_is_unchanged(
    record_type: str, file_name: str | None
) -> None:
    client = AsyncMock()
    client.async_request_api.return_value = {"url": "https://example.test/record.m3u8"}

    result = await async_create_device_record_hls(
        client,
        device_id="device",
        channel_id="0",
        begin_time="2026-11-01 00:06:55",
        end_time="2026-11-01 00:08:10",
        record_type=record_type,
        stream_id=1,
        file_name=file_name,
    )

    assert result == "https://example.test/record.m3u8"
    expected = {
        "deviceId": "device",
        "channelId": "0",
        "beginTime": "2026-11-01 00:06:55",
        "endTime": "2026-11-01 00:08:10",
        "recordType": record_type,
        "streamId": 1,
    }
    if file_name is not None:
        expected["fileName"] = file_name
    client.async_request_api.assert_awaited_once_with(
        "/openapi/createDeviceRecordHls", expected
    )


def test_normalize_imou_segment_url() -> None:
    url = "https://example.test/seg?a=1&userid=35664364_seg_0.ts?proto=https&uid=abc"
    assert normalize_imou_hls_segment_url(url).endswith("uid=abc")
    assert ".ts?" not in normalize_imou_hls_segment_url(url)


def test_parse_hls_media_segment_urls() -> None:
    body = "\n".join(
        [
            "#EXTM3U",
            "#EXTINF:2,",
            "https://example.test/one.ts?proto=https",
            "#EXTINF:2,",
            "https://example.test/two.ts?x=1&proto=y",
        ]
    )
    segments = parse_hls_media_segment_urls(body)
    assert len(segments) == 2
    assert segments[0] == "https://example.test/one.ts&proto=https"


def test_parse_hls_relative_segment_urls() -> None:
    body = "\n".join(["#EXTM3U", "#EXTINF:2,", "seg0.ts?proto=https"])
    base = "https://cdn.example.test/path/index.m3u8?token=1"
    segments = parse_hls_media_segment_urls(body, base)
    assert segments == ["https://cdn.example.test/path/seg0.ts&proto=https"]


def test_parse_hls_segment_ts_in_query_only() -> None:
    body = "\n".join(
        [
            "#EXTINF:2,",
            "https://example.test/seg?a=1&userid=35664364_seg_0.ts?proto=https",
        ]
    )
    segments = parse_hls_media_segment_urls(body)
    assert len(segments) == 1
    assert ".ts&" in segments[0] or ".ts?" not in segments[0]


def test_pick_hls_variant_playlist_url() -> None:
    body = "\n".join(
        [
            "#EXTM3U",
            "#EXT-X-STREAM-INF:BANDWIDTH=800000",
            "chunks.m3u8",
        ]
    )
    variant = pick_hls_variant_playlist_url(
        body, "https://cdn.example.test/vod/master.m3u8"
    )
    assert variant == "https://cdn.example.test/vod/chunks.m3u8"

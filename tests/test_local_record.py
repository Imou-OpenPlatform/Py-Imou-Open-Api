"""Local recording parser tests."""

import logging
from unittest.mock import AsyncMock

import pytest
from pyimouapi.device import ImouDeviceManager
from pyimouapi.local_record import (
    async_local_record_list,
    coerce_local_playback_times,
    day_time_window,
    local_record_display_title,
    parse_local_bitmap_days,
    parse_local_record_list,
)


def test_parse_local_bitmap_from_output_data() -> None:
    days = parse_local_bitmap_days(
        {"outputData": {"bitmap": "1100"}}, year=2026, month=1
    )
    assert days == [1, 2]


def test_parse_local_records() -> None:
    payload = {
        "outputData": {
            "records": [
                {
                    "fileName": "a",
                    "beginTime": "2026-01-02 08:00:00",
                    "endTime": "2026-01-02 08:10:00",
                    "fileLength": 42,
                }
            ]
        }
    }
    rows = parse_local_record_list(payload)
    assert rows[0].file_name == "a"
    assert rows[0].file_length == 42
    assert rows[0].thumb_url is None


def test_parse_local_records_keeps_a_cover_url() -> None:
    payload = {
        "outputData": {
            "records": [
                {
                    "fileName": "a",
                    "beginTime": "2026-01-02 08:00:00",
                    "endTime": "2026-01-02 08:10:00",
                    "thumbUrl": "https://example.test/cover.jpg",
                    "picId": 0,
                }
            ]
        }
    }
    rows = parse_local_record_list(payload)
    assert rows[0].thumb_url == "https://example.test/cover.jpg"


def test_day_time_window() -> None:
    begin, end = day_time_window(2026, 3, 5)
    assert begin == "2026-03-05 00:00:00"
    assert end == "2026-03-05 23:59:59"


def test_coerce_playback_times_from_dav_path() -> None:
    path = "/mnt/sd/2026-11-01/001/dav/00/00.06.55-00.08.10[M][0@0][0].dav"
    window = coerce_local_playback_times(path, path, path)
    assert window == ("2026-11-01 00:06:55", "2026-11-01 00:08:10")
    assert local_record_display_title(path, path, path) == "00:06:55 - 00:08:10"


def test_parse_local_records_with_dav_path_times() -> None:
    path = "/mnt/sd/2026-11-01/001/dav/00/00.06.55-00.08.10[M][0@0][0].dav"
    rows = parse_local_record_list(
        {
            "outputData": {
                "records": [
                    {
                        "fileName": path,
                        "beginTime": path,
                        "endTime": path,
                    }
                ]
            }
        }
    )
    assert len(rows) == 1
    assert rows[0].begin_time == "2026-11-01 00:06:55"
    assert rows[0].end_time == "2026-11-01 00:08:10"


def _local_record(
    index: int,
    *,
    begin_time: str | None = None,
    end_time: str | None = None,
    file_name: str | None = None,
) -> dict[str, str]:
    return {
        "fileName": file_name or f"clip-{index}.mp4",
        "beginTime": begin_time or f"2026-11-01 00:00:{index:02d}",
        "endTime": end_time or f"2026-11-01 00:00:{index + 1:02d}",
    }


@pytest.mark.asyncio
async def test_list_local_record_segments_pages_by_maximum_end_time() -> None:
    manager = ImouDeviceManager(AsyncMock())
    dav_path = "/mnt/sd/2026-11-01/001/dav/00/00.06.55-00.08.10[M][0@0][0].dav"
    first_page = [_local_record(index) for index in range(29)]
    first_page.insert(
        7,
        _local_record(
            99,
            begin_time=dav_path,
            end_time=dav_path,
            file_name=dav_path,
        ),
    )
    duplicate = dict(first_page[3])
    second_page = [
        duplicate,
        _local_record(
            100,
            begin_time="2026-11-01 00:08:10",
            end_time="2026-11-01 00:08:20",
        ),
    ]
    manager.async_local_record_list = AsyncMock(
        side_effect=[
            {"outputData": {"sessionId": "session-a", "records": first_page}},
            {"outputData": {"sessionId": "session-b", "records": second_page}},
        ]
    )

    segments = await manager.async_list_local_record_segments(
        "did",
        "3",
        begin_time="2026-11-01 00:00:00",
        end_time="2026-11-01 23:59:59",
        product_id="pid",
        limit=30,
    )

    assert len(segments) == 31
    assert segments[7].end_time == "2026-11-01 00:08:10"
    assert manager.async_local_record_list.await_count == 2
    for call in manager.async_local_record_list.await_args_list:
        assert call.args == ("did", "3")
        assert call.kwargs["product_id"] == "pid"
        assert "session_id" not in call.kwargs
    second_call = manager.async_local_record_list.await_args_list[1]
    assert second_call.kwargs == {
        "begin_time": "2026-11-01 00:08:10",
        "end_time": "2026-11-01 23:59:59",
        "limit": 30,
        "product_id": "pid",
    }


@pytest.mark.asyncio
async def test_list_local_record_segments_stops_when_cursor_does_not_advance(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ImouDeviceManager(AsyncMock())
    page = [
        _local_record(
            index,
            begin_time="2026-11-01 00:00:00",
            end_time="2026-11-01 00:00:00",
        )
        for index in range(30)
    ]
    manager.async_local_record_list = AsyncMock(
        return_value={"outputData": {"records": page}}
    )

    with caplog.at_level(logging.WARNING, logger="pyimouapi.device"):
        segments = await manager.async_list_local_record_segments(
            "did",
            "0",
            begin_time="2026-11-01 00:00:00",
            end_time="2026-11-01 01:00:00",
            limit=30,
        )

    assert len(segments) == 30
    assert manager.async_local_record_list.await_count == 1
    assert "cursor did not advance" in caplog.text


@pytest.mark.asyncio
async def test_list_local_record_segments_stops_on_malformed_full_page(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ImouDeviceManager(AsyncMock())
    page = [
        {
            "fileName": f"bad-{index}",
            "beginTime": "not-a-time",
            "endTime": "also-not-a-time",
        }
        for index in range(30)
    ]
    manager.async_local_record_list = AsyncMock(
        return_value={"outputData": {"records": page}}
    )

    with caplog.at_level(logging.WARNING, logger="pyimouapi.device"):
        segments = await manager.async_list_local_record_segments(
            "did",
            "0",
            begin_time="2026-11-01 00:00:00",
            end_time="2026-11-01 01:00:00",
            limit=30,
        )

    assert segments == []
    assert manager.async_local_record_list.await_count == 1
    assert "no usable end time" in caplog.text


@pytest.mark.asyncio
async def test_list_local_record_segments_has_window_based_page_limit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ImouDeviceManager(AsyncMock())
    pages = [
        [
            _local_record(
                index + page_number * 30,
                begin_time=f"2026-11-01 00:00:0{page_number}",
                end_time=f"2026-11-01 00:00:0{page_number + 1}",
            )
            for index in range(30)
        ]
        for page_number in range(2)
    ]
    manager.async_local_record_list = AsyncMock(
        side_effect=[{"outputData": {"records": page}} for page in pages]
    )

    with caplog.at_level(logging.WARNING, logger="pyimouapi.device"):
        await manager.async_list_local_record_segments(
            "did",
            "0",
            begin_time="2026-11-01 00:00:00",
            end_time="2026-11-01 00:00:30",
            limit=30,
        )

    assert manager.async_local_record_list.await_count == 2
    assert "2-page safety limit" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("begin_time", "end_time"),
    [
        ("2026-11-01 00:00:00", "2026-11-01 00:00:00"),
        ("2026-11-01 00:00:01", "2026-11-01 00:00:00"),
        ("2026-11-01T00:00:00+08:00", "2026-11-01 01:00:00"),
        ("2026-11-01 00:00:00", "2026-11-01T01:00:00+08:00"),
    ],
)
async def test_list_local_record_segments_skips_invalid_window(
    begin_time: str, end_time: str
) -> None:
    manager = ImouDeviceManager(AsyncMock())
    manager.async_local_record_list = AsyncMock()

    segments = await manager.async_list_local_record_segments(
        "did",
        "0",
        begin_time=begin_time,
        end_time=end_time,
    )

    assert segments == []
    manager.async_local_record_list.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_local_record_segments_propagates_api_errors() -> None:
    manager = ImouDeviceManager(AsyncMock())
    manager.async_local_record_list = AsyncMock(
        side_effect=RuntimeError("SD card unavailable")
    )

    with pytest.raises(RuntimeError, match="SD card unavailable"):
        await manager.async_list_local_record_segments(
            "did",
            "0",
            begin_time="2026-11-01 00:00:00",
            end_time="2026-11-01 01:00:00",
        )


@pytest.mark.asyncio
async def test_local_record_list_forwards_channel_and_product() -> None:
    client = AsyncMock()
    client.async_request_api.return_value = {}

    await async_local_record_list(
        client,
        device_id="did",
        channel_id="3",
        product_id="pid",
        begin_time="2026-11-01 00:00:00",
        end_time="2026-11-01 01:00:00",
        limit=30,
    )

    params = client.async_request_api.await_args.args[1]
    assert params["deviceId"] == "did"
    assert params["channelId"] == "3"
    assert params["productId"] == "pid"
    assert params["inputData"]["limit"] == 30


@pytest.mark.asyncio
async def test_local_record_bitmap_forwards_product() -> None:
    client = AsyncMock()
    client.async_request_api.return_value = {}
    manager = ImouDeviceManager(client)

    await manager.async_local_record_bitmap(
        "did", "3", year=2026, month=11, product_id="pid"
    )

    params = client.async_request_api.await_args.args[1]
    assert params["deviceId"] == "did"
    assert params["channelId"] == "3"
    assert params["productId"] == "pid"
    assert params["serviceId"] == "record.file.bitmap"
    assert params["inputData"] == {"type": "0", "year": 2026, "month": 11}

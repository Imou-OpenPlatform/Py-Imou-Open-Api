"""Paged queryCloudRecords helper."""

import logging
from unittest.mock import AsyncMock

import pytest
from pyimouapi.cloud_record import RECORD_QUERY_PAGE_SIZE
from pyimouapi.device import ImouDeviceManager


def _record(
    record_id: str | None,
    begin_time: str,
    end_time: str,
    *,
    file_name: str | None = None,
) -> dict[str, str]:
    record = {
        "beginTime": begin_time,
        "endTime": end_time,
    }
    if record_id is not None:
        record["recordId"] = record_id
    if file_name is not None:
        record["fileName"] = file_name
    return record


def _full_page() -> list[dict[str, str]]:
    return [
        _record(
            str(index),
            f"2026-01-01 10:{index // 60:02d}:{index % 60:02d}",
            f"2026-01-01 10:{(index + 1) // 60:02d}:{(index + 1) % 60:02d}",
        )
        for index in range(RECORD_QUERY_PAGE_SIZE)
    ]


@pytest.mark.asyncio
async def test_list_cloud_record_segments_fetches_second_page_and_deduplicates() -> (
    None
):
    manager = ImouDeviceManager(AsyncMock())
    first_page = _full_page()
    second_page = [
        first_page[50],
        _record(
            "second-page",
            "2026-01-01 10:01:40",
            "2026-01-01 10:01:41",
        ),
    ]
    manager.async_query_cloud_records = AsyncMock(
        side_effect=[{"records": first_page}, {"records": second_page}]
    )

    segments = await manager.async_list_cloud_record_segments(
        "did",
        "0",
        begin_time="2026-01-01 10:00:00",
        end_time="2026-01-01 11:00:00",
    )

    assert [segment.record_id for segment in segments] == [
        *(str(index) for index in range(RECORD_QUERY_PAGE_SIZE)),
        "second-page",
    ]
    assert manager.async_query_cloud_records.await_count == 2
    assert (
        manager.async_query_cloud_records.await_args_list[1].kwargs["begin_time"]
        == "2026-01-01 10:01:40"
    )


@pytest.mark.asyncio
async def test_list_cloud_record_segments_uses_maximum_end_time_in_unsorted_page() -> (
    None
):
    manager = ImouDeviceManager(AsyncMock())
    first_page = _full_page()
    first_page[-1], first_page[50] = first_page[50], first_page[-1]
    manager.async_query_cloud_records = AsyncMock(
        side_effect=[{"records": first_page}, {"records": []}]
    )

    await manager.async_list_cloud_record_segments(
        "did",
        "0",
        begin_time="2026-01-01 10:00:00",
        end_time="2026-01-01 11:00:00",
    )

    assert (
        manager.async_query_cloud_records.await_args_list[1].kwargs["begin_time"]
        == "2026-01-01 10:01:40"
    )


@pytest.mark.asyncio
async def test_list_cloud_record_segments_stops_when_cursor_does_not_advance(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ImouDeviceManager(AsyncMock())
    page = [
        _record(
            str(index),
            "2026-01-01 09:59:00",
            "2026-01-01 10:00:00",
        )
        for index in range(RECORD_QUERY_PAGE_SIZE)
    ]
    manager.async_query_cloud_records = AsyncMock(return_value={"records": page})

    with caplog.at_level(logging.WARNING, logger="pyimouapi.device"):
        await manager.async_list_cloud_record_segments(
            "did",
            "0",
            begin_time="2026-01-01 10:00:00",
            end_time="2026-01-01 11:00:00",
        )

    assert manager.async_query_cloud_records.await_count == 1
    assert "cursor did not advance" in caplog.text


@pytest.mark.asyncio
async def test_list_cloud_record_segments_stops_on_malformed_page_times(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ImouDeviceManager(AsyncMock())
    page = [
        _record(str(index), "not-a-time", "also-not-a-time")
        for index in range(RECORD_QUERY_PAGE_SIZE)
    ]
    manager.async_query_cloud_records = AsyncMock(return_value={"records": page})

    with caplog.at_level(logging.WARNING, logger="pyimouapi.device"):
        segments = await manager.async_list_cloud_record_segments(
            "did",
            "0",
            begin_time="2026-01-01 10:00:00",
            end_time="2026-01-01 11:00:00",
        )

    assert len(segments) == RECORD_QUERY_PAGE_SIZE
    assert manager.async_query_cloud_records.await_count == 1
    assert "no usable end time" in caplog.text


@pytest.mark.asyncio
async def test_list_cloud_record_segments_deduplicates_records_without_ids() -> None:
    manager = ImouDeviceManager(AsyncMock())
    first_page = _full_page()
    first_page[0] = _record(
        None,
        "2026-01-01 10:00:00",
        "2026-01-01 10:00:01",
        file_name="clip.mp4",
    )
    duplicate = dict(first_page[0])
    manager.async_query_cloud_records = AsyncMock(
        side_effect=[
            {"records": first_page},
            {
                "records": [
                    duplicate,
                    _record(
                        None,
                        "2026-01-01 10:01:40",
                        "2026-01-01 10:01:41",
                        file_name="next.mp4",
                    ),
                    _record(
                        None,
                        "2026-01-01 10:01:40",
                        "2026-01-01 10:01:41",
                        file_name="alternate.mp4",
                    ),
                ]
            },
        ]
    )

    segments = await manager.async_list_cloud_record_segments(
        "did",
        "0",
        begin_time="2026-01-01 10:00:00",
        end_time="2026-01-01 11:00:00",
    )

    without_ids = [segment for segment in segments if not segment.record_id]
    assert [(segment.begin_time, segment.end_time) for segment in without_ids] == [
        ("2026-01-01 10:00:00", "2026-01-01 10:00:01"),
        ("2026-01-01 10:01:40", "2026-01-01 10:01:41"),
        ("2026-01-01 10:01:40", "2026-01-01 10:01:41"),
    ]


@pytest.mark.asyncio
async def test_list_cloud_record_segments_stops_at_window_end() -> None:
    manager = ImouDeviceManager(AsyncMock())
    page = _full_page()
    page[-1] = _record(
        "boundary",
        "2026-01-01 10:59:59",
        "2026-01-01 11:00:00",
    )
    manager.async_query_cloud_records = AsyncMock(return_value={"records": page})

    segments = await manager.async_list_cloud_record_segments(
        "did",
        "0",
        begin_time="2026-01-01 10:00:00",
        end_time="2026-01-01 11:00:00",
    )

    assert segments[-1].record_id == "boundary"
    assert manager.async_query_cloud_records.await_count == 1


@pytest.mark.asyncio
async def test_list_cloud_record_segments_stops_on_short_page() -> None:
    manager = ImouDeviceManager(AsyncMock())
    single_short_page = {
        "records": [
            {
                "recordId": "1",
                "beginTime": "2026-01-01 10:00:00",
                "endTime": "2026-01-01 10:01:00",
            }
        ]
    }
    manager.async_query_cloud_records = AsyncMock(side_effect=[single_short_page])
    segments = await manager.async_list_cloud_record_segments(
        "did",
        "0",
        begin_time="2026-01-01 00:00:00",
        end_time="2026-01-01 23:59:59",
    )
    assert len(segments) == 1
    assert len(single_short_page["records"]) < RECORD_QUERY_PAGE_SIZE
    assert segments[0].record_id == "1"
    assert segments[0].begin_time == "2026-01-01 10:00:00"
    assert segments[0].end_time == "2026-01-01 10:01:00"
    assert manager.async_query_cloud_records.await_count == 1
    first_call = manager.async_query_cloud_records.await_args_list[0]
    assert first_call.kwargs["begin_time"] == "2026-01-01 00:00:00"
    assert first_call.kwargs["end_time"] == "2026-01-01 23:59:59"
    assert first_call.kwargs["count"] == RECORD_QUERY_PAGE_SIZE


@pytest.mark.asyncio
async def test_list_cloud_record_segments_propagates_api_errors() -> None:
    manager = ImouDeviceManager(AsyncMock())
    manager.async_query_cloud_records = AsyncMock(
        side_effect=RuntimeError("cloud unavailable")
    )

    with pytest.raises(RuntimeError, match="cloud unavailable"):
        await manager.async_list_cloud_record_segments(
            "did",
            "0",
            begin_time="2026-01-01 10:00:00",
            end_time="2026-01-01 11:00:00",
        )

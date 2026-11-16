"""Paged queryCloudRecords helper."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.device import ImouDeviceManager


@pytest.mark.asyncio
async def test_list_cloud_record_segments_stops_on_short_page() -> None:
    manager = ImouDeviceManager(AsyncMock())
    manager.async_query_cloud_records = AsyncMock(
        return_value={
            "records": [
                {
                    "recordId": "1",
                    "beginTime": "2026-01-01 10:00:00",
                    "endTime": "2026-01-01 10:01:00",
                }
            ]
        }
    )
    segments = await manager.async_list_cloud_record_segments(
        "did",
        "0",
        begin_time="2026-01-01 00:00:00",
        end_time="2026-01-01 23:59:59",
    )
    assert len(segments) == 1
    assert segments[0].record_id == "1"
    assert segments[0].begin_time == "2026-01-01 10:00:00"
    assert segments[0].end_time == "2026-01-01 10:01:00"
    assert manager.async_query_cloud_records.await_count == 1
    first_call = manager.async_query_cloud_records.await_args_list[0]
    assert first_call.kwargs["begin_time"] == "2026-01-01 00:00:00"
    assert first_call.kwargs["end_time"] == "2026-01-01 23:59:59"

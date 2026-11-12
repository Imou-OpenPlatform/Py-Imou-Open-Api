"""Paged queryCloudRecords helper."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.device import ImouDeviceManager


@pytest.mark.asyncio
async def test_list_cloud_record_segments_pages() -> None:
    manager = ImouDeviceManager(AsyncMock())
    manager.async_query_cloud_records = AsyncMock(
        side_effect=[
            {
                "records": [
                    {
                        "recordId": "1",
                        "beginTime": "2026-01-01 10:00:00",
                        "endTime": "2026-01-01 10:01:00",
                    }
                ]
            },
            {"records": []},
        ]
    )
    segments = await manager.async_list_cloud_record_segments(
        "did",
        "0",
        begin_time="2026-01-01 00:00:00",
        end_time="2026-01-01 23:59:59",
    )
    assert len(segments) == 1
    assert manager.async_query_cloud_records.await_count == 2
    second_call = manager.async_query_cloud_records.await_args_list[1]
    assert second_call.kwargs["begin_time"] == "2026-01-01 10:01:00"

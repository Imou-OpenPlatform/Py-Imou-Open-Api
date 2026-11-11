"""Local recording via record.file.* capability services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability.client import async_service_invoke
from .cloud_record import parse_cloud_record_bitmap_days
from .openapi import ImouOpenApiClient

SERVICE_RECORD_FILE_BITMAP = "record.file.bitmap"
SERVICE_RECORD_FILE_LIST = "record.file.list"
LOCAL_RECORD_TYPE_ALL = "0"
DEFAULT_LOCAL_LIST_LIMIT = 50


@dataclass(frozen=True, slots=True)
class LocalRecordSegment:
    """One local recording file entry."""

    file_name: str
    begin_time: str
    end_time: str
    file_length: int | None = None


def _output_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    output = payload.get("outputData")
    return dict(output) if isinstance(output, dict) else {}


def parse_local_bitmap_days(output_data: Any, *, year: int, month: int) -> list[int]:
    """Parse record.file.bitmap outputData into days with recordings."""
    data = _output_data(output_data)
    bitmap = data.get("bitmap")
    if bitmap is None:
        bitmap = data.get("mask")
    if not isinstance(bitmap, str):
        return []
    return parse_cloud_record_bitmap_days(bitmap, year=year, month=month)


def parse_local_record_list(output_data: Any) -> list[LocalRecordSegment]:
    """Parse record.file.list outputData records array."""
    data = _output_data(output_data)
    records_raw = data.get("records")
    if not isinstance(records_raw, list):
        return []
    segments: list[LocalRecordSegment] = []
    for item in records_raw:
        if not isinstance(item, dict):
            continue
        file_name = str(item.get("fileName") or "").strip()
        begin_time = str(item.get("beginTime") or "").strip()
        end_time = str(item.get("endTime") or "").strip()
        if not begin_time or not end_time:
            continue
        if not file_name:
            file_name = f"{begin_time}_{end_time}"
        length_raw = item.get("fileLength")
        file_length = None
        if length_raw is not None and str(length_raw).strip() != "":
            try:
                file_length = int(length_raw)
            except (TypeError, ValueError):
                file_length = None
        segments.append(
            LocalRecordSegment(
                file_name=file_name,
                begin_time=begin_time,
                end_time=end_time,
                file_length=file_length,
            )
        )
    return segments


def day_time_window(year: int, month: int, day: int) -> tuple[str, str]:
    """Return begin/end strings for a calendar day."""
    begin = f"{year:04d}-{month:02d}-{day:02d} 00:00:00"
    end = f"{year:04d}-{month:02d}-{day:02d} 23:59:59"
    return begin, end


async def async_local_record_bitmap(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    channel_id: str,
    year: int,
    month: int,
    record_type: str = LOCAL_RECORD_TYPE_ALL,
) -> dict[str, Any]:
    """Invoke record.file.bitmap."""
    data = await async_service_invoke(
        client,
        device_id=device_id,
        channel_id=channel_id,
        service_id=SERVICE_RECORD_FILE_BITMAP,
        input_data={"type": record_type, "year": year, "month": month},
    )
    return data


async def async_local_record_list(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    channel_id: str,
    begin_time: str,
    end_time: str,
    limit: int = DEFAULT_LOCAL_LIST_LIMIT,
    record_type: str = LOCAL_RECORD_TYPE_ALL,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Invoke record.file.list."""
    bounded = max(30, min(100, int(limit)))
    input_data: dict[str, Any] = {
        "type": record_type,
        "beginTime": begin_time,
        "endTime": end_time,
        "limit": bounded,
    }
    if session_id:
        input_data["sessionId"] = session_id
    return await async_service_invoke(
        client,
        device_id=device_id,
        channel_id=channel_id,
        service_id=SERVICE_RECORD_FILE_LIST,
        input_data=input_data,
    )

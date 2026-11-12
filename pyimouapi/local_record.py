"""Local recording via record.file.* capability services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .capability.client import async_service_invoke
from .cloud_record import parse_cloud_record_bitmap_days
from .openapi import ImouOpenApiClient

SERVICE_RECORD_FILE_BITMAP = "record.file.bitmap"
SERVICE_RECORD_FILE_LIST = "record.file.list"
LOCAL_RECORD_TYPE_ALL = "0"
DEFAULT_LOCAL_LIST_LIMIT = 50

_HLS_TIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
_DAV_CLIP_RANGE = re.compile(
    r"(?P<bh>\d{2})\.(?P<bm>\d{2})\.(?P<bs>\d{2})-(?P<eh>\d{2})\.(?P<em>\d{2})\.(?P<es>\d{2})"
)
_DATE_IN_PATH = re.compile(r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})")


def _is_hls_window_time(value: str) -> bool:
    """True when value matches createDeviceRecordHls beginTime/endTime."""
    return bool(_HLS_TIME.match(value)) and ".dav" not in value.lower()


def _format_hls_time(
    year: int, month: int, day: int, hour: int, minute: int, second: int
) -> str:
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


def coerce_local_playback_times(
    file_name: str, begin_time: str, end_time: str
) -> tuple[str, str] | None:
    """Map list fields to same-day begin/end strings for createDeviceRecordHls."""
    if _is_hls_window_time(begin_time) and _is_hls_window_time(end_time):
        return begin_time, end_time
    path = file_name or begin_time
    if not path:
        return None
    clip = _DAV_CLIP_RANGE.search(path)
    date_match = _DATE_IN_PATH.search(path)
    if clip is None or date_match is None:
        return None
    year = int(date_match.group("y"))
    month = int(date_match.group("m"))
    day = int(date_match.group("d"))
    begin = _format_hls_time(
        year,
        month,
        day,
        int(clip.group("bh")),
        int(clip.group("bm")),
        int(clip.group("bs")),
    )
    end = _format_hls_time(
        year,
        month,
        day,
        int(clip.group("eh")),
        int(clip.group("em")),
        int(clip.group("es")),
    )
    return begin, end


def local_record_display_title(file_name: str, begin_time: str, end_time: str) -> str:
    """Short browse label instead of a full SD-card path."""
    window = coerce_local_playback_times(file_name, begin_time, end_time)
    if window is not None:
        begin, end = window
        return f"{begin[11:19]} - {end[11:19]}"
    if file_name:
        leaf = file_name.rsplit("/", 1)[-1]
        return leaf or file_name
    return begin_time or end_time


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
        if not file_name and (not begin_time or not end_time):
            continue
        if not file_name:
            file_name = f"{begin_time}_{end_time}"
        window = coerce_local_playback_times(file_name, begin_time, end_time)
        if window is None:
            continue
        begin_time, end_time = window
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

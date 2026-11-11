"""Cloud recording Open API helpers."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from typing import Any

RECORD_QUERY_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class CloudRecordSegment:
    """One cloud recording clip."""

    record_id: str
    begin_time: str
    end_time: str
    thumb_url: str | None = None
    encrypt_mode: int | None = None
    record_type: str | None = None


def parse_cloud_record_bitmap_days(bitmap: str, *, year: int, month: int) -> list[int]:
    """Return day-of-month values that have cloud recordings (1-based)."""
    if not bitmap or month < 1 or month > 12 or year < 1:
        return []
    days_in_month = calendar.monthrange(year, month)[1]
    trimmed = bitmap.strip()[:days_in_month]
    days: list[int] = []
    for index, ch in enumerate(trimmed, start=1):
        if ch == "1":
            days.append(index)
    return days


def parse_cloud_records_data(data: Any) -> list[CloudRecordSegment]:
    """Parse ``queryCloudRecords`` ``data`` payload."""
    if not isinstance(data, dict):
        return []
    records_raw = data.get("records")
    if not isinstance(records_raw, list):
        return []
    segments: list[CloudRecordSegment] = []
    for item in records_raw:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get("recordId") or "").strip()
        begin_time = str(item.get("beginTime") or "").strip()
        end_time = str(item.get("endTime") or "").strip()
        if not record_id or not begin_time or not end_time:
            continue
        thumb = item.get("thumbUrl")
        thumb_url = str(thumb).strip() if thumb else None
        encrypt_raw = item.get("encryptMode")
        encrypt_mode = None
        if encrypt_raw is not None and str(encrypt_raw).strip() != "":
            try:
                encrypt_mode = int(encrypt_raw)
            except (TypeError, ValueError):
                encrypt_mode = None
        record_type = item.get("type")
        type_str = str(record_type).strip() if record_type else None
        segments.append(
            CloudRecordSegment(
                record_id=record_id,
                begin_time=begin_time,
                end_time=end_time,
                thumb_url=thumb_url,
                encrypt_mode=encrypt_mode,
                record_type=type_str,
            )
        )
    return segments

"""Cloud recording parser tests."""

from pyimouapi.cloud_record import (
    parse_cloud_record_bitmap_days,
    parse_cloud_records_data,
)


def test_bitmap_days() -> None:
    days = parse_cloud_record_bitmap_days("101", year=2026, month=2)
    assert days == [1, 3]


def test_parse_cloud_records() -> None:
    payload = {
        "records": [
            {
                "recordId": "abc",
                "beginTime": "2026-01-01 10:00:00",
                "endTime": "2026-01-01 10:05:00",
                "thumbUrl": "https://example/thumb.jpg",
            }
        ]
    }
    segments = parse_cloud_records_data(payload)
    assert len(segments) == 1
    assert segments[0].record_id == "abc"
    assert segments[0].thumb_url == "https://example/thumb.jpg"

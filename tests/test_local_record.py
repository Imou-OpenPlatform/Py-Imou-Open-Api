"""Local recording parser tests."""

from pyimouapi.local_record import (
    day_time_window,
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


def test_day_time_window() -> None:
    begin, end = day_time_window(2026, 3, 5)
    assert begin == "2026-03-05 00:00:00"
    assert end == "2026-03-05 23:59:59"

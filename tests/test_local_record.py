"""Local recording parser tests."""

from pyimouapi.local_record import (
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

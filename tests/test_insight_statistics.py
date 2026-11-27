"""Insight statistics parsing tests."""

from pyimouapi.insight.statistics import (
    detection_totals,
    format_briefing_markdown,
    parse_alarm_message_statistics,
)


def test_parse_statistics_and_markdown() -> None:
    briefing = parse_alarm_message_statistics(
        {
            "statistics": [
                {
                    "date": "20260327",
                    "totalcount": 20,
                    "humanAlarm": 2,
                    "carAlarm": 1,
                    "petAlarm": 10,
                    "motionAlarm": 3,
                }
            ],
            "aiStatisticsAnalysisResult": [
                {
                    "analysisDay": "20260327",
                    "riskStatementInfo": [
                        {
                            "startHour": "00",
                            "endHour": "05",
                            "riskEventDoc": "A person near the door",
                        }
                    ],
                }
            ],
        }
    )
    assert len(briefing.daily) == 1
    assert briefing.daily[0].pet == 10
    assert briefing.daily[0].total == 20
    assert briefing.daily[0].package == 0
    text = format_briefing_markdown(briefing)
    assert "20260327" in text
    assert "A person near the door" in text
    assert "Risk count: 0" in text


def test_big_model_labels_fill_detections_and_events() -> None:
    briefing = parse_alarm_message_statistics(
        {
            "statistics": [
                {
                    "date": "20261118",
                    "totalcount": 4,
                    "bigModelStatisticsLabels": [
                        {"labelType": "ELDERLY_APPEAR", "count": 2},
                        {"label": "PACKAGE_APPEAR", "count": 0},
                        "PET_ACTIVITY",
                        {"name": "CHILD_HOME", "num": 1},
                    ],
                }
            ],
            "aiStatisticsAnalysisResult": [
                {
                    "analysisDay": "20261118",
                    "riskStatementInfo": [
                        {
                            "startHour": "18",
                            "endHour": "20",
                            "count": "3",
                            "riskEventDoc": "有人在门口停留",
                        }
                    ],
                    "msgAnalysisInfo": [
                        {
                            "labelType": "humanAlarm",
                            "alarmDateTimeArr": ["2026-11-18 18:15:00"],
                            "timeDistribute": [0, 0, 0, 0, 0, 0, 0, 0, 0, 3],
                        }
                    ],
                }
            ],
        }
    )
    row = briefing.daily[0]
    assert [event.count for event in row.events] == [2, 0, 1, 1]
    totals = detection_totals(row.events)
    assert totals["elderly"] == 2
    assert totals["package"] == 0
    assert totals["pet"] == 1
    assert totals["child"] == 1
    assert row.risks[0].count == 3
    assert row.risks[0].text == "有人在门口停留"
    assert row.timings[0].buckets[9] == 3

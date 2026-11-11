"""Insight statistics parsing tests."""

from pyimouapi.insight.statistics import (
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
    text = format_briefing_markdown(briefing)
    assert "20260327" in text
    assert "A person near the door" in text

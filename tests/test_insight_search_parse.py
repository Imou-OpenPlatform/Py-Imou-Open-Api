"""searchAiAlarmMessageByPage response parsing."""

from pyimouapi.insight.search import parse_search_ai_alarms


def test_parse_keeps_type_copy_and_pictures() -> None:
    _, hits = parse_search_ai_alarms(
        {
            "alarms": [
                {
                    "alarmId": 1,
                    "localDate": "2026-11-16 10:04:32",
                    "alarmType": "llmCloudMsg",
                    "aiCopyWriting": "Một người",
                    "aiTag": ["human"],
                    "securityRiskLevel": 1,
                    "thumbUrl": "https://example.test/thumb.jpg",
                    "picurlArray": ["https://example.test/full.jpg"],
                }
            ]
        }
    )
    assert len(hits) == 1
    hit = hits[0]
    assert hit.alarm_type == "llmCloudMsg"
    assert hit.ai_copywriting == "Một người"
    assert hit.ai_tags == ("human",)
    assert hit.thumb_url == "https://example.test/thumb.jpg"
    assert hit.picture_urls == ("https://example.test/full.jpg",)

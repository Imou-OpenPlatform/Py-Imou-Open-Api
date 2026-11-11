"""Insight cloud parsing tests."""

from pyimouapi.insight.cloud import parse_device_cloud_data


def test_ai_insight_active_when_strategy_type_six() -> None:
    snap = parse_device_cloud_data(
        {
            "hasDefault": True,
            "strategyType": "6",
            "strategyStatus": 1,
            "name": "7-day insight",
        }
    )
    assert snap.ai_insight_active
    assert snap.cloud_storage_label == "insight"


def test_no_plan() -> None:
    snap = parse_device_cloud_data({"hasDefault": False})
    assert snap.cloud_storage_label == "none"
    assert not snap.ai_insight_active

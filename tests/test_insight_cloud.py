"""Insight cloud parsing tests."""

from pyimouapi.insight.cloud import (
    ai_insight_cloud_label_from_service,
    ai_insight_label_from_status,
    cloud_storage_label_from_cs_status,
    parse_device_cloud_data,
)


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
    assert snap.cloud_storage_label == "active"


def test_ai_insight_active_without_has_default() -> None:
    snap = parse_device_cloud_data({"strategyType": "6", "strategyStatus": 1})
    assert snap.ai_insight_active


def test_ai_insight_cloud_label_from_service() -> None:
    active = parse_device_cloud_data({"strategyType": "6", "strategyStatus": 1})
    assert ai_insight_cloud_label_from_service(active) == "active"
    other = parse_device_cloud_data({"strategyType": "1", "strategyStatus": 1})
    assert ai_insight_cloud_label_from_service(other) == "inactive"


def test_no_plan() -> None:
    snap = parse_device_cloud_data({"hasDefault": False})
    assert snap.cloud_storage_label == "inactive"
    assert not snap.ai_insight_active


def test_expired_plan() -> None:
    snap = parse_device_cloud_data(
        {"hasDefault": True, "strategyStatus": 2, "strategyType": "6"}
    )
    assert snap.cloud_storage_label == "inactive"
    assert not snap.ai_insight_active


def test_cs_status_maps_onto_cloud_storage_states() -> None:
    """Device-list csStatus uses the same states as AI Insight."""
    assert cloud_storage_label_from_cs_status("notExist") == "inactive"
    assert cloud_storage_label_from_cs_status("off") == "inactive"
    assert cloud_storage_label_from_cs_status("using") == "active"
    assert cloud_storage_label_from_cs_status("on") == "active"
    assert cloud_storage_label_from_cs_status("expired") == "inactive"
    assert cloud_storage_label_from_cs_status(None) == "unavailable"
    assert cloud_storage_label_from_cs_status("mystery") == "unavailable"


def test_ai_insight_status_maps_onto_sensor_states() -> None:
    """Device-list aiInsightStatus is the AI Insight sensor."""
    assert ai_insight_label_from_status("on") == "active"
    assert ai_insight_label_from_status("using") == "active"
    assert ai_insight_label_from_status("off") == "inactive"
    assert ai_insight_label_from_status("notExist") == "inactive"
    assert ai_insight_label_from_status(None) == "unavailable"

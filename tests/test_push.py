"""Tests for pyimouapi.push Open Platform payload helpers."""

from __future__ import annotations

import pytest
from pyimouapi.push import (
    event_ref_lookup_key,
    iot_property_values,
    is_alarm_msg_type,
    is_iot_non_event,
    normalize_push_payload,
    pic_urls_from_payload,
    preferred_pic_url,
)


@pytest.mark.parametrize(
    ("msg_type", "expected"),
    [
        ("closeCamera", False),
        ("openCamera", False),
        ("online", False),
        ("iotProperty", False),
        ("iotAction", False),
        ("electricity", False),
        ("low_battery_alarm", False),
        ("iotEvent", True),
        ("e_storageEmpty", False),
        ("e_storageAbnormal", False),
        ("e_upgradeSuccess", False),
        ("e_upgradeFail", False),
        ("upgrading", False),
        ("upgrade_success", False),
        ("home", False),
        ("leave", False),
        ("no_defend", False),
        ("e_matchApSucc", False),
        ("e_multiVideoAiPerArea", True),
        ("e_std_aorAlarm", True),
        ("e_videoMotion", True),
        ("whiteLightOn", False),
        ("sirenOn", True),
        ("sirenOff", True),
        ("bindDevice", False),
        ("videoMotion", True),
        ("human", True),
        ("abAlarmSound", True),
        ("mobileDetect", True),
        ("alarmLocal", True),
        ("totallyUnknownType", True),
        (None, False),
    ],
)
def test_is_alarm_msg_type(msg_type: str | None, expected: bool) -> None:
    """Hybrid classification: denylist non-alarms; unknown types are alarms."""
    assert is_alarm_msg_type(msg_type) is expected


def test_normalize_iot_event_keeps_top_level_msg_type() -> None:
    """iotEvent keeps top-level msgType; still exposes pid/outputData/channel."""
    payload = {
        "msgType": "iotEvent",
        "pid": "mhpf7Dsz",
        "did": "TESTQWERXXXX",
        "dname": "Gate",
        "alarmId": "116257862023505xxxx",
        "token": "tok",
        "time": "20230111T111629",
        "content": {
            "outputData": {"foo": 1},
            "event": "33000",
            "monitor": {"channel": 0, "action": 1},
        },
    }
    event = normalize_push_payload(payload)

    assert event["msg_type"] == "iotEvent"
    assert event["msg_type_name"] == "iotEvent"
    assert event["product_id"] == "mhpf7Dsz"
    assert event["device_id"] == "TESTQWERXXXX"
    assert event["channel_id"] == 0
    assert event["alarm_id"] == "116257862023505xxxx"
    assert event["outputData"] == {"foo": 1}
    assert event["raw"] is payload
    assert event["raw"]["msgType"] == "iotEvent"
    assert "device_name" not in event
    assert "is_alarm" not in event


def test_normalize_does_not_use_dname_as_device_id() -> None:
    """Display name alone must not become device_id."""
    event = normalize_push_payload({"msgType": "human", "dname": "Gate"})
    assert event["device_id"] is None
    assert event["name"] == "Gate"


def test_pic_urls_accepts_pic_url_arr() -> None:
    """Some pushes use picUrlArr instead of picUrlArray."""
    assert pic_urls_from_payload({"picUrlArr": ["https://example/a.jpg"]}) == [
        "https://example/a.jpg"
    ]


def test_pic_urls_accepts_pic_url_list_and_string() -> None:
    """picUrl may be a list of URLs or a single string."""
    assert pic_urls_from_payload(
        {"picUrl": ["https://example/big.jpg", "https://example/small.jpg"]}
    ) == ["https://example/big.jpg", "https://example/small.jpg"]
    assert pic_urls_from_payload({"picUrl": "https://example/only.jpg"}) == [
        "https://example/only.jpg"
    ]


def test_pic_urls_prefers_thumb_url_over_other_fields() -> None:
    """thumbUrl is tried first because it is typically the smallest still."""
    assert pic_urls_from_payload(
        {
            "thumbUrl": "https://example/thumb.jpg",
            "picUrlArray": ["https://example/big.jpg", "https://example/small.jpg"],
            "picUrlArr": ["https://example/arr.jpg"],
            "picUrl": ["https://example/pic.jpg"],
        }
    ) == ["https://example/thumb.jpg"]


def test_normalize_paas_device_id_and_channel() -> None:
    """PaaS aliases deviceId / channelId."""
    event = normalize_push_payload(
        {"msgType": "human", "deviceId": "SN1", "channelId": "0"}
    )
    assert event["device_id"] == "SN1"
    assert event["channel_id"] == "0"
    assert event["msg_type"] == "human"


def test_normalize_prefers_cid_over_channel_id() -> None:
    """cid wins when several channel keys are present."""
    event = normalize_push_payload(
        {"msgType": "human", "did": "SN1", "cid": 2, "channelId": 9}
    )
    assert event["channel_id"] == 2


def test_normalize_skips_list_channel_keys() -> None:
    """List-typed channel keys are skipped; monitor.channel is the fallback."""
    event = normalize_push_payload(
        {
            "msgType": "iotEvent",
            "did": "SN1",
            "cid": [0, 1],
            "content": {"monitor": {"channel": 3}},
        }
    )
    assert event["channel_id"] == 3


def test_is_iot_non_event() -> None:
    """Drop non-event/property envelopes only when product_id is truthy."""
    assert is_iot_non_event("mhpf7Dsz", "videoMotion") is True
    assert is_iot_non_event("mhpf7Dsz", "iotEvent") is False
    assert is_iot_non_event("mhpf7Dsz", "iotProperty") is False
    assert is_iot_non_event("mhpf7Dsz", "iotAction") is True
    assert is_iot_non_event(None, "videoMotion") is False
    assert is_iot_non_event("", "videoMotion") is False
    assert is_iot_non_event(0, "videoMotion") is False


def test_event_ref_lookup_key() -> None:
    """Digit msg_type or iotEvent content.event become the product-model ref."""
    assert event_ref_lookup_key("33000", {}) == "33000"
    assert event_ref_lookup_key("iotEvent", {"content": {"event": "33000"}}) == "33000"
    assert event_ref_lookup_key("iotEvent", {"content": {"event": "human"}}) is None
    assert event_ref_lookup_key("human", {"content": {"event": "33000"}}) is None
    assert event_ref_lookup_key("iotEvent", {"content": {}}) is None


def test_pic_urls_from_payload_extracts_array() -> None:
    """picUrlArray strings are returned in order."""
    urls = pic_urls_from_payload({"picUrlArray": ["https://a/big", "https://a/small"]})
    assert urls == ["https://a/big", "https://a/small"]


def test_preferred_pic_url_prefers_small_thumb() -> None:
    """Thumbnail pick prefers index 1 when two URLs are present."""
    assert preferred_pic_url(["https://a/big", "https://a/small"]) == "https://a/small"
    assert preferred_pic_url(["https://a/big"]) == "https://a/big"
    assert preferred_pic_url([]) is None


def test_iot_property_values_from_content() -> None:
    """Prefer content.properties; stringify keys."""
    raw = {"content": {"properties": {10001: 1, "15400": 2}}}
    assert iot_property_values(raw) == {"10001": 1, "15400": 2}


def test_iot_property_values_from_top_level() -> None:
    """Fall back to top-level properties when content has none."""
    assert iot_property_values({"properties": {"10001": 0}}) == {"10001": 0}


def test_iot_property_values_empty() -> None:
    """Missing or non-dict properties yield an empty map."""
    assert iot_property_values({}) == {}
    assert iot_property_values({"content": "x"}) == {}
    assert iot_property_values({"content": {"properties": []}}) == {}

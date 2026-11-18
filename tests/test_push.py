"""Tests for pyimouapi.push Open Platform payload helpers."""

from __future__ import annotations

import pytest
from pyimouapi.push import (
    NON_ALARM_MSG_TYPES,
    V2_PROPERTY_REPORT_MSG_TYPE,
    alarm_picture_url,
    event_id_from_push,
    is_alarm_msg_type,
    is_capability_event_payload,
    is_iot_non_event,
    is_unknown_legacy_msg_type,
    is_v2_capability_event_id,
    is_v2_property_report,
    normalize_push_payload,
    parse_callback_flag,
    pic_urls_from_payload,
    preferred_pic_url,
    push_dispatch_permitted,
    push_subscription_kind,
    v2_capability_event_permitted,
    v2_property_report_values,
)
from pyimouapi.push_dispatch_allowlist import PUSH_DISPATCH_MSG_TYPES_LOWER


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


def test_normalize_strips_msg_type() -> None:
    """Normalized msg_type fields use the canonical stripped value."""
    event = normalize_push_payload(
        {"msgType": "  device.property.report  ", "deviceId": "IPC1"}
    )

    assert event["msg_type"] == V2_PROPERTY_REPORT_MSG_TYPE
    assert event["msg_type_name"] == V2_PROPERTY_REPORT_MSG_TYPE
    assert event["raw"]["msgType"] == "  device.property.report  "


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


def test_normalize_includes_ai_copywriting() -> None:
    payload = {
        "msgType": "human",
        "deviceId": "SN1",
        "channelId": "0",
        "aiCopyWriting": "Man in dark jacket",
        "aiTag": ["human", "vehicle"],
    }
    event = normalize_push_payload(payload)
    assert event["ai_copywriting"] == "Man in dark jacket"
    assert event["ai_tags"] == ["human", "vehicle"]
    folded = normalize_push_payload(
        {
            "msgType": "human",
            "content": {
                "aicopywriting": "A box by the door",
                "aitag": "pet\uff0cpackage",
            },
        }
    )
    assert folded["ai_copywriting"] == "A box by the door"
    assert folded["ai_tags"] == ["pet", "package"]


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
    assert is_iot_non_event("mhpf7Dsz", "detection.motion.detected") is False
    assert is_iot_non_event("mhpf7Dsz", "iotEvent") is False
    assert is_iot_non_event("mhpf7Dsz", "iotProperty") is False
    assert is_iot_non_event("mhpf7Dsz", "iotAction") is True
    assert is_iot_non_event(None, "videoMotion") is False
    assert is_iot_non_event("", "videoMotion") is False
    assert is_iot_non_event(0, "videoMotion") is False


def test_pic_urls_from_payload_extracts_array() -> None:
    """picUrlArray strings are returned in order."""
    urls = pic_urls_from_payload({"picUrlArray": ["https://a/big", "https://a/small"]})
    assert urls == ["https://a/big", "https://a/small"]


def test_alarm_picture_url_uses_pic_url_array_first() -> None:
    """Message pictures use picUrlArray[0], including a lowercase key."""
    raw = {
        "thumbUrl": "https://example/thumb.jpg",
        "picUrlArray": ["https://example/big.jpg", "https://example/small.jpg"],
    }
    assert alarm_picture_url(raw) == "https://example/big.jpg"
    assert (
        alarm_picture_url(
            {"picurlarray": ["https://example/first.jpg", "https://example/second.jpg"]}
        )
        == "https://example/first.jpg"
    )
    assert alarm_picture_url({"thumbUrl": "https://example/thumb.jpg"}) == (
        "https://example/thumb.jpg"
    )


def test_preferred_pic_url_prefers_small_thumb() -> None:
    """Thumbnail pick prefers index 1 when two URLs are present."""
    assert preferred_pic_url(["https://a/big", "https://a/small"]) == "https://a/small"
    assert preferred_pic_url(["https://a/big"]) == "https://a/big"
    assert preferred_pic_url([]) is None


def test_parse_callback_flag() -> None:
    """callbackFlag splits on commas and trims whitespace."""
    assert parse_callback_flag("alarm,deviceStatus,capabilityEvent") == frozenset(
        {"alarm", "deviceStatus", "capabilityEvent"}
    )
    assert parse_callback_flag("") == frozenset()
    assert parse_callback_flag(["iot", "alarm"]) == frozenset({"iot", "alarm"})


def test_legacy_alarm_name_is_not_a_capability_event() -> None:
    """Legacy alarm names are not capability event ids."""
    assert is_v2_capability_event_id("videoMotion") is False
    assert is_v2_capability_event_id("detection.motion.detected") is True


def test_v2_capability_event_permitted() -> None:
    """Gate V2 events against a device's event id set."""
    allowed = frozenset({"detection.motion.detected"})
    assert v2_capability_event_permitted(allowed, "detection.motion.detected") is True
    assert v2_capability_event_permitted(allowed, "detection.person.detected") is False
    assert v2_capability_event_permitted(None, "detection.motion.detected") is True


def test_legacy_and_v2_motion_share_normalize_fields() -> None:
    """Webhook compares the same device/channel after Legacy or V2 motion."""
    legacy = {
        "msgType": "videoMotion",
        "did": "IPC1",
        "cid": "0",
        "time": "20230111T111629",
    }
    v2 = {
        "msgType": "detection.motion.detected",
        "deviceId": "IPC1",
        "channelId": 0,
        "time": "20230111T111629",
    }
    leg = normalize_push_payload(legacy)
    v2n = normalize_push_payload(v2)
    assert leg["device_id"] == v2n["device_id"] == "IPC1"
    assert str(leg["channel_id"]) == str(v2n["channel_id"])
    assert leg["time"] == v2n["time"]


def test_capability_event_v2_normalize() -> None:
    """V2 capabilityEvent exposes top-level outputData and deviceId."""
    payload = {
        "msgType": "detection.motion.detected",
        "deviceId": "IPC123",
        "channelId": 0,
        "outputData": {"score": 0.9},
        "time": "20230111T111629",
    }
    assert is_capability_event_payload(payload) is True
    event = normalize_push_payload(payload)
    assert event["msg_type"] == "detection.motion.detected"
    assert event["device_id"] == "IPC123"
    assert event["channel_id"] == 0
    assert event["outputData"] == {"score": 0.9}
    assert event_id_from_push(payload) == "detection.motion.detected"


def test_push_dispatch_accepts_unknown_legacy_alarm_type() -> None:
    assert push_dispatch_permitted("human") is True
    assert push_dispatch_permitted("detection.person.detected") is True
    assert push_dispatch_permitted("iotProperty") is True
    assert push_dispatch_permitted("newAlarmFromCloud") is True
    assert is_unknown_legacy_msg_type("newAlarmFromCloud") is True
    assert push_dispatch_permitted(None) is False


@pytest.mark.parametrize("msg_type", [None, "", " ", "\t"])
def test_push_dispatch_rejects_empty_msg_type(msg_type: str | None) -> None:
    assert push_dispatch_permitted(msg_type) is False
    assert is_unknown_legacy_msg_type(msg_type) is False


def test_push_dispatch_keeps_recognized_non_alarm_operation_policy() -> None:
    assert push_dispatch_permitted("electricity") is True
    assert is_unknown_legacy_msg_type("electricity") is False
    assert push_dispatch_permitted("numberstat") is False
    assert is_unknown_legacy_msg_type("numberstat") is False


@pytest.mark.parametrize(
    "msg_type",
    sorted(
        msg_type for msg_type in NON_ALARM_MSG_TYPES if not msg_type.startswith("e_")
    ),
)
def test_prefixed_known_non_alarm_never_uses_unknown_alarm_fallback(
    msg_type: str,
) -> None:
    prefixed = f"e_{msg_type}"

    assert is_unknown_legacy_msg_type(prefixed) is False
    assert is_alarm_msg_type(prefixed) is False
    assert push_dispatch_permitted(prefixed) is (
        prefixed.lower() in PUSH_DISPATCH_MSG_TYPES_LOWER
    )


@pytest.mark.parametrize("msg_type", ["e_numberstat", " E_NumberStat "])
def test_prefixed_denied_non_alarm_normalizes_case_and_whitespace(
    msg_type: str,
) -> None:
    assert push_dispatch_permitted(msg_type) is False
    assert is_unknown_legacy_msg_type(msg_type) is False
    assert is_alarm_msg_type(msg_type) is False


def test_push_dispatch_rejects_double_e_prefix() -> None:
    assert push_dispatch_permitted("e_e_videomotion") is False
    assert is_unknown_legacy_msg_type("e_e_videomotion") is False
    assert push_dispatch_permitted("e_videoMotion") is True


def test_unknown_prefixed_legacy_alarm_keeps_fallback() -> None:
    assert push_dispatch_permitted("e_newAlarmFromCloud") is True
    assert is_unknown_legacy_msg_type("e_newAlarmFromCloud") is True
    assert is_alarm_msg_type("e_newAlarmFromCloud") is True


@pytest.mark.parametrize(
    ("msg_type", "expected"),
    [
        ("iotProperty", "iot"),
        ("device.property.report", "capability"),
        ("detection.motion.detected", "capability"),
        ("alarmLocal", "alarm"),
        ("online", "device_status"),
        ("storageEmpty", "lifecycle"),
    ],
)
def test_push_subscription_kind_buckets(msg_type: str, expected: str) -> None:
    assert push_subscription_kind(msg_type) == expected


@pytest.mark.parametrize(
    "msg_type",
    [
        "storageempty",
        "storageEmpty",
        "  storageEmpty  ",
        "STORAGEEMPTY",
    ],
)
def test_push_subscription_kind_lifecycle_normalizes_storage_empty(
    msg_type: str,
) -> None:
    assert push_subscription_kind(msg_type) == "lifecycle"


def test_legacy_human_not_capability_event() -> None:
    """Legacy alarm types must not classify as V2 capability events."""
    payload = {"msgType": "human", "did": "IPC123"}
    assert is_capability_event_payload(payload) is False
    assert event_id_from_push(payload) is None


def test_v2_property_report_helpers() -> None:
    """device.property.report is capability subscription, not an alarm event."""
    assert is_v2_property_report(V2_PROPERTY_REPORT_MSG_TYPE) is True
    assert is_v2_capability_event_id(V2_PROPERTY_REPORT_MSG_TYPE) is False
    assert is_alarm_msg_type(V2_PROPERTY_REPORT_MSG_TYPE) is False
    assert push_dispatch_permitted(V2_PROPERTY_REPORT_MSG_TYPE) is True
    assert push_subscription_kind(V2_PROPERTY_REPORT_MSG_TYPE) == "capability"
    assert is_iot_non_event("mhpf7Dsz", V2_PROPERTY_REPORT_MSG_TYPE) is False


def test_v2_property_report_values_top_level() -> None:
    payload = {
        "msgType": V2_PROPERTY_REPORT_MSG_TYPE,
        "deviceId": "IPC1",
        "properties": {"privacy.cover.enabled": {"enabled": 1}},
    }
    assert is_capability_event_payload(payload) is False
    assert v2_property_report_values(payload) == {
        "privacy.cover.enabled": {"enabled": 1}
    }
    event = normalize_push_payload(payload)
    assert event["msg_type"] == V2_PROPERTY_REPORT_MSG_TYPE
    assert event["device_id"] == "IPC1"

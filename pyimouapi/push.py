"""Imou Open Platform event-push payload helpers.

Legacy alarm msg types and V2 capability ``eventId`` values are both accepted
here (dual-track ingestion). Device control uses Open API v2 capabilities only.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from .push_dispatch_allowlist import PUSH_DISPATCH_MSG_TYPES_LOWER

V2_PROPERTY_REPORT_MSG_TYPE = "device.property.report"

# Status / ops types that are not security alarms.
# Official Imou "Device alarm" list also includes privacy-mask and lifecycle
# types; we subtract those here. See:
# https://open.imoulife.com/book/en/push/alarm.html
NON_ALARM_MSG_TYPES = frozenset(
    {
        "online",
        "offline",
        "close",
        "changeDevName",
        "iotProperty",
        "iotAction",
        "numberstat",
        "electricity",
        "low_battery_alarm",
        "openCamera",
        "closeCamera",
        "whiteLightOn",
        "whiteLightOff",
        "sleep",
        "bindDevice",
        "unbindDevice",
        "deviceShare",
        "deviceShareCancel",
        "deviceAuthorize",
        "deviceAuthorizationChanged",
        "transferDeviceFrom",
        "transferDeviceTo",
        "deviceDeletedSharedCancel",
        "UpgradeSuccess",
        "upgradeFail",
        "apUpgradeSuccess",
        "apUpgradeFail",
        "storageRecoverOk",
        "storageRecoverFail",
        "storageEmpty",
        "storageAbnormal",
        "e_upgradeSuccess",
        "e_upgradeFail",
        "e_storageEmpty",
        "e_storageAbnormal",
        "upgrading",
        "upgrade_success",
        "upgrade_failed",
        "upgrade_result",
        "e_matchApSucc",
        "home",
        "leave",
        "no_defend",
        V2_PROPERTY_REPORT_MSG_TYPE,
    }
)

_NON_ALARM_MSG_TYPES_LOWER = frozenset(k.lower() for k in NON_ALARM_MSG_TYPES)


def is_alarm_msg_type(msg_type: str | None) -> bool:
    """Return True if this push should be treated as a security alarm."""
    if msg_type is None:
        return False
    lower = msg_type.strip().lower()
    if lower in _NON_ALARM_MSG_TYPES_LOWER:
        return False
    return not (lower.startswith("e_") and lower[2:] in _NON_ALARM_MSG_TYPES_LOWER)


_IOT_PUSH_ENVELOPES = frozenset({"iotEvent", "iotProperty"})

_IOT_PUSH_ENVELOPES_LOWER = frozenset(k.lower() for k in _IOT_PUSH_ENVELOPES)

_DEVICE_STATUS_MSG_TYPES_LOWER = frozenset({"online", "offline"})

_ARMING_MSG_TYPES_LOWER = frozenset({"home", "leave", "no_defend"})

PushSubscriptionKind = Literal[
    "iot",
    "capability",
    "alarm",
    "device_status",
    "lifecycle",
]


def is_v2_property_report(msg_type: str | None) -> bool:
    """Return True for V2 property change pushes (``device.property.report``)."""
    return msg_type == V2_PROPERTY_REPORT_MSG_TYPE


def is_v2_capability_event_id(msg_type: str | None) -> bool:
    """Return True when msg_type looks like a standard capability eventId."""
    if is_v2_property_report(msg_type):
        return False
    return isinstance(msg_type, str) and "." in msg_type


def v2_capability_event_permitted(
    events: frozenset[str] | None,
    event_id: str,
) -> bool:
    """Return True when the event is allowed for this device's capability list."""
    if events is None:
        return True
    return event_id in events


def is_unknown_legacy_msg_type(msg_type: str | None) -> bool:
    """Return whether a non-empty Legacy msg_type is absent from known catalogs."""
    if not isinstance(msg_type, str) or not msg_type.strip():
        return False
    stripped = msg_type.strip()
    if (
        is_v2_property_report(stripped)
        or is_v2_capability_event_id(stripped)
        or _is_digit_str(stripped)
    ):
        return False
    lower = stripped.lower()
    if (
        lower in PUSH_DISPATCH_MSG_TYPES_LOWER
        or lower in _NON_ALARM_MSG_TYPES_LOWER
        or lower.startswith("e_e_")
    ):
        return False
    if lower.startswith("e_"):
        remainder = lower[2:]
        return (
            remainder not in PUSH_DISPATCH_MSG_TYPES_LOWER
            and remainder not in _NON_ALARM_MSG_TYPES_LOWER
        )
    return True


def push_dispatch_permitted(msg_type: str | None) -> bool:
    """Allow known pushes and unknown Legacy alarms; reject malformed/denied ops."""
    if not isinstance(msg_type, str) or not msg_type.strip():
        return False
    stripped = msg_type.strip()
    lower = stripped.lower()
    if lower in PUSH_DISPATCH_MSG_TYPES_LOWER:
        return True
    if lower.startswith("e_"):
        remainder = lower[2:]
        if remainder.startswith("e_") or remainder in _NON_ALARM_MSG_TYPES_LOWER:
            return False
        return remainder in PUSH_DISPATCH_MSG_TYPES_LOWER or is_unknown_legacy_msg_type(
            stripped
        )
    if is_v2_property_report(stripped) or is_v2_capability_event_id(stripped):
        return True
    if _is_digit_str(stripped):
        return True
    return is_unknown_legacy_msg_type(stripped)


def push_subscription_kind(msg_type: str | None) -> PushSubscriptionKind:
    """Map an allowed push msg_type to a Configure event_push_types bucket."""
    if not isinstance(msg_type, str):
        return "lifecycle"
    stripped = msg_type.strip()
    if is_v2_property_report(stripped) or is_v2_capability_event_id(stripped):
        return "capability"
    lower = stripped.lower()
    if lower in _IOT_PUSH_ENVELOPES_LOWER:
        return "iot"
    if lower in _DEVICE_STATUS_MSG_TYPES_LOWER:
        return "device_status"
    if lower in _ARMING_MSG_TYPES_LOWER or is_alarm_msg_type(stripped):
        return "alarm"
    return "lifecycle"


def is_iot_non_event(product_id: Any, msg_type: str | None) -> bool:
    """Return True when an IoT device sent an envelope this integration ignores."""
    if is_v2_capability_event_id(msg_type) or is_v2_property_report(msg_type):
        return False
    return bool(product_id) and msg_type not in _IOT_PUSH_ENVELOPES


def v2_property_report_values(raw: dict[str, Any]) -> dict[str, Any]:
    """Return propertyId→value from a ``device.property.report`` body."""
    props = raw.get("properties")
    if not isinstance(props, dict):
        return {}
    return {str(key): value for key, value in props.items()}


def _is_digit_str(value: Any) -> bool:
    return isinstance(value, str) and value.isdigit()


def parse_callback_flag(value: str | Iterable[str] | None) -> frozenset[str]:
    """Split Imou ``callbackFlag`` (comma-separated) into a flag set."""
    if value is None or value == "":
        return frozenset()
    parts = value.split(",") if isinstance(value, str) else list(value)
    return frozenset(part.strip() for part in parts if str(part).strip())


def is_capability_event_payload(raw: dict[str, Any]) -> bool:
    """Return True when the body matches V2 capabilityEvent shape."""
    msg_type = raw.get("msgType")
    if is_v2_property_report(msg_type):
        return False
    if not isinstance(msg_type, str) or "." not in msg_type:
        return False
    device_id = raw.get("deviceId") or raw.get("msgDeviceId")
    return bool(device_id)


def event_id_from_push(raw: dict[str, Any]) -> str | None:
    """Return a capability eventId, else None."""
    if is_capability_event_payload(raw):
        msg_type = raw.get("msgType")
        return str(msg_type) if msg_type is not None else None
    return None


def _channel_id_from_payload(payload: dict[str, Any]) -> Any:
    """Return a scalar channel id from the push payload, if present."""
    for key in ("cid", "channelId", "msgChannelId"):
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, list | dict):
            continue
        return value
    channels = payload.get("channels")
    if isinstance(channels, list | dict) or channels in (None, ""):
        return None
    return channels


def _field_ci(source: dict[str, Any], name: str) -> Any:
    """Return the value whose key matches ``name``, ignoring case."""
    for key, value in source.items():
        if str(key).lower() == name:
            return value
    return None


def _push_field(payload: dict[str, Any], content: Any, name: str) -> Any:
    """Read a push field from the envelope, then from content."""
    value = _field_ci(payload, name)
    if value not in (None, "", []):
        return value
    if isinstance(content, dict):
        return _field_ci(content, name)
    return None


def _ai_tags(value: Any) -> list[str]:
    """Return detected-category tags from a list or a comma-separated string."""
    if isinstance(value, str):
        parts = value.replace("\uff0c", ",").split(",")
        return [part.strip() for part in parts if part.strip()]
    if not isinstance(value, list):
        return []
    return [str(tag).strip() for tag in value if str(tag).strip()]


def normalize_push_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize PaaS / IoT push formats into common fields.

    Does not raise. Caller must pass a dict. Does not set device_name.
    """
    device_id = (
        payload.get("did") or payload.get("deviceId") or payload.get("msgDeviceId")
    )
    channel_id = _channel_id_from_payload(payload)
    raw_msg_type = payload.get("msgType")
    msg_type = raw_msg_type.strip() if isinstance(raw_msg_type, str) else raw_msg_type
    content = payload.get("content")
    output_data = None
    if isinstance(content, dict):
        output_data = content.get("outputData")
    if output_data is None and "outputData" in payload:
        output_data = payload.get("outputData")
    if isinstance(content, dict) and channel_id is None:
        monitor = content.get("monitor")
        if isinstance(monitor, dict) and "channel" in monitor:
            channel_id = monitor.get("channel")

    ai_copy = _push_field(payload, content, "aicopywriting")
    ai_copywriting = (
        ai_copy.strip() if isinstance(ai_copy, str) and ai_copy.strip() else None
    )
    ai_tags = _ai_tags(_push_field(payload, content, "aitag"))

    return {
        "msg_type": msg_type,
        "msg_type_name": msg_type,
        "device_id": device_id,
        "channel_id": channel_id,
        "product_id": payload.get("productId") or payload.get("pid"),
        "time": (
            payload.get("time") or payload.get("localTime") or payload.get("utcTime")
        ),
        "name": payload.get("cname") or payload.get("dname"),
        "alarm_id": payload.get("id") or payload.get("alarmId"),
        "token": payload.get("token"),
        "desc": payload.get("desc"),
        "ai_copywriting": ai_copywriting,
        "ai_tags": ai_tags,
        "outputData": output_data,
        "raw": payload,
    }


def _pic_url_strings(value: Any) -> list[str]:
    """Return non-empty URL strings from a list or a single string."""
    if isinstance(value, str) and value:
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def pic_urls_from_payload(raw: dict[str, Any]) -> list[str]:
    """Return picture URL strings from the first populated push field.

    Order: ``thumbUrl`` (usually smallest), then ``picUrlArray``,
    ``picUrlArr``, ``picUrl``. Each field may be a list or a single string.
    """
    for key in ("thumbUrl", "picUrlArray", "picUrlArr", "picUrl"):
        urls = _pic_url_strings(raw.get(key))
        if urls:
            return urls
    return []


def preferred_pic_url(urls: list[str]) -> str | None:
    """Prefer index 1 (small thumb) when present, else index 0."""
    if not urls:
        return None
    if len(urls) > 1 and urls[1]:
        return urls[1]
    return urls[0] or None


def alarm_picture_url(raw: dict[str, Any]) -> str | None:
    """Return the alarm still: the first ``picUrlArray`` entry.

    When that array is missing, fall back to the older thumb and url fields.
    """
    for key, value in raw.items():
        if str(key).lower() != "picurlarray":
            continue
        urls = _pic_url_strings(value)
        if urls:
            return urls[0]
    return preferred_pic_url(pic_urls_from_payload(raw))

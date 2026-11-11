"""Imou Open Platform event-push payload helpers.

Legacy alarm msg types and V2 capability ``eventId`` values are both accepted
here (dual-track ingestion). Device control uses Open API v2 capabilities only.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

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
    }
)


def is_alarm_msg_type(msg_type: str | None) -> bool:
    """Return True if this push should be treated as a security alarm."""
    return msg_type is not None and msg_type not in NON_ALARM_MSG_TYPES


_IOT_PUSH_ENVELOPES = frozenset({"iotEvent", "iotProperty"})


def is_v2_capability_event_id(msg_type: str | None) -> bool:
    """Return True when msg_type looks like a standard capability eventId."""
    return isinstance(msg_type, str) and "." in msg_type


# V2 capability eventId → legacy PaaS msg_type for motion, labels, and automations.
V2_EVENT_LEGACY_MSG_TYPE: dict[str, str] = {
    "detection.motion.detected": "videoMotion",
    "detection.person.detected": "human",
    "detection.pet.detected": "mobileDetect",
    "detection.sound.detected": "abAlarmSound",
}


def legacy_msg_type_from_v2_event(msg_type: str | None) -> str | None:
    """Map a V2 eventId to the legacy msg_type Home Assistant already understands."""
    if not msg_type:
        return msg_type
    return V2_EVENT_LEGACY_MSG_TYPE.get(msg_type, msg_type)


def v2_capability_event_permitted(
    events: frozenset[str] | None,
    event_id: str,
) -> bool:
    """Return True when the event is allowed for this device's capability list."""
    if events is None:
        return True
    return event_id in events


def is_iot_non_event(product_id: Any, msg_type: str | None) -> bool:
    """Return True when an IoT device sent an envelope this integration ignores."""
    if is_v2_capability_event_id(msg_type):
        return False
    return bool(product_id) and msg_type not in _IOT_PUSH_ENVELOPES


def iot_property_values(raw: dict[str, Any]) -> dict[str, Any]:
    """Return ref→value from an iotProperty payload. Never raises."""
    content = raw.get("content")
    if isinstance(content, dict) and isinstance(content.get("properties"), dict):
        source = content["properties"]
    elif isinstance(raw.get("properties"), dict):
        source = raw["properties"]
    else:
        return {}
    return {str(key): value for key, value in source.items()}


def _is_digit_str(value: Any) -> bool:
    return isinstance(value, str) and value.isdigit()


def event_ref_lookup_key(msg_type: str | None, raw: dict[str, Any]) -> str | None:
    """Return the product-model event ref to resolve, or None to skip."""
    if _is_digit_str(msg_type):
        return msg_type
    if msg_type == "iotEvent":
        content = raw.get("content")
        if isinstance(content, dict):
            event_ref = content.get("event")
            if event_ref is None or event_ref == "":
                return None
            key = str(event_ref)
            if key.isdigit():
                return key
    return None


def parse_callback_flag(value: str | Iterable[str] | None) -> frozenset[str]:
    """Split Imou ``callbackFlag`` (comma-separated) into a flag set."""
    if value is None or value == "":
        return frozenset()
    parts = value.split(",") if isinstance(value, str) else list(value)
    return frozenset(part.strip() for part in parts if str(part).strip())


def is_capability_event_payload(raw: dict[str, Any]) -> bool:
    """Return True when the body matches V2 capabilityEvent shape."""
    msg_type = raw.get("msgType")
    if not isinstance(msg_type, str) or "." not in msg_type:
        return False
    device_id = raw.get("deviceId") or raw.get("msgDeviceId")
    return bool(device_id)


def event_id_from_push(raw: dict[str, Any]) -> str | None:
    """Return a capability eventId or legacy digit ref, else None."""
    if is_capability_event_payload(raw):
        msg_type = raw.get("msgType")
        return str(msg_type) if msg_type is not None else None
    msg_type = raw.get("msgType")
    key = msg_type if isinstance(msg_type, str) else None
    return event_ref_lookup_key(key, raw)


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


def normalize_push_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize PaaS / IoT push formats into common fields.

    Does not raise. Caller must pass a dict. Does not set device_name.
    """
    device_id = (
        payload.get("did") or payload.get("deviceId") or payload.get("msgDeviceId")
    )
    channel_id = _channel_id_from_payload(payload)
    msg_type = payload.get("msgType")
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

    ai_copy = payload.get("aiCopyWriting")
    if not ai_copy and isinstance(content, dict):
        ai_copy = content.get("aiCopyWriting")
    ai_copywriting = str(ai_copy).strip() if ai_copy else None
    ai_tags_raw = payload.get("aiTag")
    if ai_tags_raw is None and isinstance(content, dict):
        ai_tags_raw = content.get("aiTag")
    ai_tags: list[str] = []
    if isinstance(ai_tags_raw, list):
        ai_tags = [str(tag).strip() for tag in ai_tags_raw if str(tag).strip()]

    return {
        "msg_type": msg_type,
        "msg_type_name": msg_type,
        "device_id": device_id,
        "channel_id": channel_id,
        "product_id": payload.get("pid"),
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

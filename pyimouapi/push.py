"""Imou Open Platform event-push payload helpers."""

from __future__ import annotations

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


def is_iot_non_event(product_id: Any, msg_type: str | None) -> bool:
    """Return True when an IoT device sent a non-iotEvent envelope."""
    return bool(product_id) and msg_type != "iotEvent"


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
        if channel_id is None:
            monitor = content.get("monitor")
            if isinstance(monitor, dict) and "channel" in monitor:
                channel_id = monitor.get("channel")

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
        "outputData": output_data,
        "raw": payload,
    }


def pic_urls_from_payload(raw: dict[str, Any]) -> list[str]:
    """Return picture URL strings from a push payload, if any."""
    urls: list[str] = []
    for key in ("picUrlArray", "picUrlArr"):
        value = raw.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and item and item not in urls:
                urls.append(item)
    return urls


def preferred_pic_url(urls: list[str]) -> str | None:
    """Prefer index 1 (small thumb) when present, else index 0."""
    if not urls:
        return None
    if len(urls) > 1 and urls[1]:
        return urls[1]
    return urls[0] or None

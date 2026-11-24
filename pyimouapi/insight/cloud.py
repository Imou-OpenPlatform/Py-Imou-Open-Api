"""getDeviceCloud parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

INSIGHT_STRATEGY_TYPE = "6"


@dataclass(frozen=True, slots=True)
class DeviceCloudService:
    """Normalized cloud storage subscription for one channel."""

    has_default: bool
    strategy_id: str | None
    name: str | None
    strategy_type: str | None
    strategy_status: int | None
    begin_time: str | None
    end_time: str | None

    @property
    def ai_insight_active(self) -> bool:
        """True when an insight (strategyType 6) plan is in use."""
        return self.strategy_type == INSIGHT_STRATEGY_TYPE and self.strategy_status == 1

    @property
    def cloud_storage_label(self) -> str:
        """Same active / inactive states as the AI Insight sensor.

        Imou ``strategyStatus`` 1 is in use. An expired plan and a missing
        plan are both inactive.
        """
        if self.strategy_status == 2:
            return "inactive"
        if self.strategy_status == 1 or self.has_default:
            return "active"
        return "inactive"


_SUBSCRIPTION_ACTIVE = frozenset({"using", "on", "active"})
_SUBSCRIPTION_INACTIVE = frozenset({"notexist", "not_exist", "off", "none", "expired"})


def subscription_status_label(value: str | None) -> str:
    """Map a device-list status onto active, inactive, or unavailable."""
    raw = (value or "").strip().lower()
    if raw in _SUBSCRIPTION_ACTIVE:
        return "active"
    if raw in _SUBSCRIPTION_INACTIVE:
        return "inactive"
    return "unavailable"


def cloud_storage_label_from_cs_status(value: str | None) -> str:
    """Map a device-list ``csStatus`` onto the AI Insight status set."""
    return subscription_status_label(value)


def ai_insight_label_from_status(value: str | None) -> str:
    """Map a device-list ``aiInsightStatus`` onto active, inactive, or unavailable."""
    return subscription_status_label(value)


def ai_insight_label_from_strategy_status(status: int | None) -> str:
    """Map queryDeviceAiInsight ``strategyStatus`` onto the AI Insight sensor."""
    if status == 1:
        return "active"
    if status == 2:
        return "paused"
    return "inactive"


def parse_ai_insight_strategy_status(data: Any) -> int | None:
    """Read ``strategyStatus`` from queryDeviceAiInsight ``data``."""
    if not isinstance(data, dict):
        return None
    status_raw = data.get("strategyStatus")
    if status_raw is None or str(status_raw).strip() == "":
        return None
    try:
        return int(status_raw)
    except (TypeError, ValueError):
        return None


def parse_device_cloud_data(data: Any) -> DeviceCloudService:
    """Parse getDeviceCloud ``data`` without raising."""
    if not isinstance(data, dict):
        return DeviceCloudService(False, None, None, None, None, None, None)
    has_default = bool(data.get("hasDefault"))
    strategy_id = data.get("strategyId")
    sid = str(strategy_id).strip() if strategy_id not in (None, "") else None
    name_raw = data.get("name")
    name = str(name_raw).strip() if name_raw else None
    stype_raw = data.get("strategyType")
    strategy_type = str(stype_raw).strip() if stype_raw not in (None, "") else None
    status_raw = data.get("strategyStatus")
    strategy_status = None
    if status_raw is not None and str(status_raw).strip() != "":
        try:
            strategy_status = int(status_raw)
        except (TypeError, ValueError):
            strategy_status = None
    begin = data.get("beginTime")
    end = data.get("endTime")
    begin_time = str(begin).strip() if begin else None
    end_time = str(end).strip() if end else None
    return DeviceCloudService(
        has_default,
        sid,
        name,
        strategy_type,
        strategy_status,
        begin_time,
        end_time,
    )


def ai_insight_cloud_label_from_service(snap: DeviceCloudService) -> str:
    """Map getDeviceCloud data onto the AI Insight cloud storage sensor states."""
    if snap.strategy_type == INSIGHT_STRATEGY_TYPE:
        if snap.strategy_status == 1:
            return "active"
        if snap.strategy_status == 2:
            return "paused"
    return "inactive"

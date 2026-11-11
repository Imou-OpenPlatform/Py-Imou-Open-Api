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
        return (
            self.strategy_type == INSIGHT_STRATEGY_TYPE
            and self.strategy_status == 1
            and bool(self.has_default)
        )

    @property
    def cloud_storage_label(self) -> str:
        """User-facing bucket for the sensor enum."""
        if not self.has_default:
            return "none"
        stype = (self.strategy_type or "").strip()
        if stype == INSIGHT_STRATEGY_TYPE:
            return "insight"
        if stype in {"1", "2", "3", "4", "5"}:
            return "event"
        if stype in {"7", "8"} or stype.isdigit():
            return "continuous"
        return "unknown"


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

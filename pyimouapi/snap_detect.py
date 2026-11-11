"""Parse deviceSnapDetect Open API responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SnapDetectTarget:
    """One detected target from deviceSnapDetect."""

    target_type: str
    confidence: str | int | float | None
    region: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DeviceSnapDetectResult:
    """Normalized deviceSnapDetect payload."""

    url: str | None
    detect_result: bool
    targets: tuple[SnapDetectTarget, ...]


def parse_device_snap_detect_data(data: Any) -> DeviceSnapDetectResult:
    """Parse API ``data`` from deviceSnapDetect without raising."""
    if not isinstance(data, dict):
        return DeviceSnapDetectResult(None, False, ())
    url = data.get("url")
    url_str = str(url).strip() if url else None
    detect_raw = data.get("detectResult")
    detect_result = False
    if isinstance(detect_raw, bool):
        detect_result = detect_raw
    elif isinstance(detect_raw, str):
        detect_result = detect_raw.strip().lower() in {"1", "true", "yes"}
    elif detect_raw not in (None, "", 0):
        detect_result = bool(detect_raw)
    targets_raw = data.get("targets")
    targets: list[SnapDetectTarget] = []
    if isinstance(targets_raw, list):
        for item in targets_raw:
            if not isinstance(item, dict):
                continue
            target_type = str(item.get("targetType") or "").strip()
            if not target_type:
                continue
            region = item.get("targetRegion")
            if not isinstance(region, dict):
                region = {}
            targets.append(
                SnapDetectTarget(
                    target_type=target_type,
                    confidence=item.get("confidence"),
                    region=region,
                )
            )
    if targets and not detect_result:
        detect_result = True
    return DeviceSnapDetectResult(
        url_str or None,
        detect_result,
        tuple(targets),
    )

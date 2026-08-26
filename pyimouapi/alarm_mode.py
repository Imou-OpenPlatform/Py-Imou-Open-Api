"""Friendly keys for IoT alarm mode (ref 15200)."""

from __future__ import annotations

ALARM_MODES: tuple[str, ...] = ("home", "away", "disarm")

_RAW_TO_FRIENDLY = {"0": "home", "1": "away", "2": "disarm"}
_FRIENDLY_TO_RAW = {v: k for k, v in _RAW_TO_FRIENDLY.items()}


def to_friendly(raw: object) -> str:
    """Map vendor raw (int or str) to home / away / disarm."""
    key = "" if raw is None else str(raw).strip()
    return _RAW_TO_FRIENDLY.get(key, key)


def to_raw(mode: str) -> str:
    """Map home / away / disarm to the IoT integer string."""
    key = mode.strip().lower()
    if key not in _FRIENDLY_TO_RAW:
        raise ValueError(f"unknown alarm mode: {mode!r}")
    return _FRIENDLY_TO_RAW[key]

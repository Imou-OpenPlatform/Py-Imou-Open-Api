"""Shared on/off coercion for thing-model and v2 property values."""

from __future__ import annotations

from typing import Any


def property_is_on(raw: Any) -> bool | None:
    """Return True/False for an on/off property, or None when it cannot be read."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw == 1
    if isinstance(raw, str):
        text = raw.strip()
        if text == "1":
            return True
        if text == "0":
            return False
    return None

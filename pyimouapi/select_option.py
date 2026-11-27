"""Select option key normalization for Home Assistant integrations."""

from __future__ import annotations

import logging
from typing import Any

from pyimouapi.const import (
    PARAM_COLLECTION_POINT,
    PARAM_DEVICE_VOLUME,
    PARAM_NIGHT_VISION_MODE,
)

PARAM_WIDE_DYNAMIC = "wide_dynamic"

_LOGGER = logging.getLogger(__name__)

MAPPED_SELECT_TYPES = frozenset(
    {PARAM_DEVICE_VOLUME, PARAM_NIGHT_VISION_MODE, PARAM_WIDE_DYNAMIC}
)

# raw string -> friendly
_VOLUME_RAW_TO_FRIENDLY = {
    "99": "mute",
    "-1": "mute",
    "0": "low",
    "1": "medium",
    "2": "high",
}
_VOLUME_FRIENDLY_TO_RAW = {
    "mute": "99",
    "low": "0",
    "medium": "1",
    "high": "2",
}
# Older cameras use this set. A 1-5 level must not run through it, or 1 and 2
# become Medium and High while 3, 4 and 5 stay numbers.
_VOLUME_NAMED_RAWS = frozenset(_VOLUME_RAW_TO_FRIENDLY)


def volume_enum_uses_names(options: tuple[Any, ...] | list[Any]) -> bool:
    """True when every enum value is the mute/low/medium/high scale."""
    values = {_as_raw_str(getattr(item, "value", item)) for item in options}
    return bool(values) and values <= _VOLUME_NAMED_RAWS


_NIGHT_VISION_RAW_TO_FRIENDLY = {
    "0": "intelligent",
    "1": "fullcolor",
    "2": "infrared",
    "3": "off",
    "4": "custom",
    "5": "starlight",
}
_NIGHT_VISION_FRIENDLY_TO_RAW = {
    "intelligent": "0",
    "fullcolor": "1",
    "infrared": "2",
    "off": "3",
    "custom": "4",
    "starlight": "5",
    "lowlight": "lowlight",
    "smartlowlight": "smartlowlight",
}
# PaaS already-friendly keys also accepted as raw (identity after lower)
for _k in (
    "intelligent",
    "fullcolor",
    "infrared",
    "off",
    "custom",
    "starlight",
    "lowlight",
    "smartlowlight",
):
    _NIGHT_VISION_RAW_TO_FRIENDLY.setdefault(_k, _k)

_WDR_RAW_TO_FRIENDLY = {
    "0": "off",
    "1": "on",
    "2": "adaptive",
}
_WDR_FRIENDLY_TO_RAW = {
    "off": "0",
    "on": "1",
    "adaptive": "2",
}
for _k in ("off", "on", "adaptive"):
    _WDR_RAW_TO_FRIENDLY.setdefault(_k, _k)


def enum_desc_to_option_key(desc: str, raw_value: Any) -> str:
    """Turn a capability enum label into a stable select option key."""
    label = (desc or "").strip()
    if label:
        return label.lower().replace(" ", "_").replace("-", "_")
    return _as_raw_str(raw_value)


def _as_raw_str(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def to_friendly(select_type: str, raw: Any) -> str:
    """Map vendor/API raw option to a stable friendly key."""
    if select_type == PARAM_COLLECTION_POINT or select_type not in MAPPED_SELECT_TYPES:
        return _as_raw_str(raw)

    key = _as_raw_str(raw)
    if select_type == PARAM_DEVICE_VOLUME:
        table = _VOLUME_RAW_TO_FRIENDLY
    elif select_type == PARAM_WIDE_DYNAMIC:
        table = _WDR_RAW_TO_FRIENDLY
    else:
        key_l = key.lower()
        mapped = _NIGHT_VISION_RAW_TO_FRIENDLY.get(key_l)
        if mapped is not None:
            return mapped
        _LOGGER.debug("unknown night_vision raw option %r", raw)
        return key_l

    if key in table:
        return table[key]
    _LOGGER.debug("unknown %s raw option %r", select_type, raw)
    return key


def to_raw(select_type: str, friendly: str) -> str:
    """Map friendly key to vendor/API raw string for IoT writes.

    For night vision keys such as ``lowlight`` and ``smartlowlight``, returns the
    same lowercase string.
    Raises ValueError for unknown keys on mapped select types.
    """
    if select_type == PARAM_COLLECTION_POINT or select_type not in MAPPED_SELECT_TYPES:
        return friendly

    key = friendly.strip().lower()
    if select_type == PARAM_DEVICE_VOLUME:
        table = _VOLUME_FRIENDLY_TO_RAW
    elif select_type == PARAM_WIDE_DYNAMIC:
        table = _WDR_FRIENDLY_TO_RAW
    else:
        table = _NIGHT_VISION_FRIENDLY_TO_RAW

    if key not in table:
        raise ValueError(f"unknown {select_type} option: {friendly!r}")
    return table[key]


def normalize_options(select_type: str, options: list[str]) -> list[str]:
    """Return options list with each entry passed through to_friendly."""
    return [to_friendly(select_type, item) for item in options]

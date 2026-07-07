"""Sensor state normalization for Home Assistant integrations."""

from __future__ import annotations

import logging
from typing import Any

from pyimouapi.const import (
    PARAM_STATE,
    PARAM_STATE_VARIANT,
    PARAM_STATUS,
    PARAM_STORAGE_USED,
    STATE_VARIANT_ENUM,
    STATE_VARIANT_NUMERIC,
)

_LOGGER = logging.getLogger(__name__)

NUMERIC_SENSOR_TYPES = frozenset(
    {
        "battery",
        "temperature_current",
        "humidity_current",
        "power",
        "voltage",
        "current",
        "use_electricity",
        "use_time",
        "switch_cnt",
    }
)

INTEGER_NUMERIC_SENSOR_TYPES = frozenset(
    {
        "battery",
        "use_time",
        "switch_cnt",
    }
)

ENUM_SENSOR_TYPES = frozenset({PARAM_STATUS})

STORAGE_ERROR_CODES = frozenset({"e1", "e2"})


def normalize_sensor_state(sensor_type: str, raw: Any) -> tuple[Any, str]:
    """Return normalized (state, state_variant) for a sensor update."""
    if sensor_type == PARAM_STORAGE_USED:
        if isinstance(raw, str) and raw in STORAGE_ERROR_CODES:
            return raw, STATE_VARIANT_ENUM
        return _coerce_number(
            raw, integer=True, sensor_type=sensor_type
        ), STATE_VARIANT_NUMERIC

    if sensor_type in ENUM_SENSOR_TYPES:
        return str(raw), STATE_VARIANT_ENUM

    if sensor_type in NUMERIC_SENSOR_TYPES:
        integer = sensor_type in INTEGER_NUMERIC_SENSOR_TYPES
        return _coerce_number(
            raw, integer=integer, sensor_type=sensor_type
        ), STATE_VARIANT_NUMERIC

    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return raw, STATE_VARIANT_NUMERIC
    return raw, STATE_VARIANT_ENUM


def _coerce_number(raw: Any, *, integer: bool, sensor_type: str) -> Any:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, float):
        return int(raw) if integer else raw
    if isinstance(raw, str):
        try:
            number = float(raw)
            return int(number) if integer else number
        except ValueError:
            _LOGGER.warning(
                "Could not coerce sensor %s value %r to number", sensor_type, raw
            )
            return raw
    return raw


def apply_sensor_state(
    sensors: dict[str, dict[str, Any]], sensor_type: str, raw: Any
) -> None:
    """Write PARAM_STATE and PARAM_STATE_VARIANT on a sensor entry."""
    state, variant = normalize_sensor_state(sensor_type, raw)
    bucket = sensors.setdefault(sensor_type, {})
    bucket[PARAM_STATE] = state
    bucket[PARAM_STATE_VARIANT] = variant

"""Tests for sensor state normalization."""

import pytest
from pyimouapi.const import (
    PARAM_STATE,
    PARAM_STATE_VARIANT,
    STATE_VARIANT_ENUM,
    STATE_VARIANT_NUMERIC,
)
from pyimouapi.sensor import apply_sensor_state, normalize_sensor_state


@pytest.mark.parametrize(
    ("sensor_type", "raw", "expected_state", "expected_variant"),
    [
        ("battery", "85", 85, STATE_VARIANT_NUMERIC),
        ("battery", 85, 85, STATE_VARIANT_NUMERIC),
        ("temperature_current", "23.5", 23.5, STATE_VARIANT_NUMERIC),
        ("use_time", "120", 120, STATE_VARIANT_NUMERIC),
        ("switch_cnt", "3", 3, STATE_VARIANT_NUMERIC),
        ("use_electricity", "1.25", 1.25, STATE_VARIANT_NUMERIC),
        ("storage_used", "75", 75, STATE_VARIANT_NUMERIC),
        ("storage_used", "no_card", "no_card", STATE_VARIANT_ENUM),
        ("storage_used", "mount_failed", "mount_failed", STATE_VARIANT_ENUM),
        ("status", "online", "online", STATE_VARIANT_ENUM),
        ("status", "offline", "offline", STATE_VARIANT_ENUM),
    ],
)
def test_normalize_sensor_state(sensor_type, raw, expected_state, expected_variant):
    """Normalize sensor values to typed state and variant metadata."""
    state, variant = normalize_sensor_state(sensor_type, raw)
    assert state == expected_state
    assert variant == expected_variant


def test_apply_sensor_state_writes_variant():
    """apply_sensor_state sets PARAM_STATE and PARAM_STATE_VARIANT."""
    sensors: dict[str, dict] = {}
    apply_sensor_state(sensors, "battery", "90")
    assert sensors["battery"][PARAM_STATE] == 90
    assert sensors["battery"][PARAM_STATE_VARIANT] == STATE_VARIANT_NUMERIC

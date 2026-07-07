"""Tests for sensor state normalization."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_BATTERY,
    PARAM_STATE,
    PARAM_STATE_VARIANT,
    PARAM_STORAGE_USED,
    STATE_VARIANT_ENUM,
    STATE_VARIANT_NUMERIC,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
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
        ("storage_used", "e1", "e1", STATE_VARIANT_ENUM),
        ("storage_used", "e2", "e2", STATE_VARIANT_ENUM),
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


@pytest.mark.asyncio
async def test_update_device_battery_stores_int():
    """Battery updates store normalized integer state."""
    device = ImouHaDevice("d1", "cam", "Imou", "m", "1.0")
    device.sensors[PARAM_BATTERY] = {}
    delegate = MagicMock()
    delegate.async_get_device_power_info = AsyncMock(
        return_value={"electricitys": [{"litElec": "88"}]}
    )
    manager = ImouHaDeviceManager(delegate)
    await manager._async_update_device_battery(device)
    assert device.sensors[PARAM_BATTERY][PARAM_STATE] == 88
    assert device.sensors[PARAM_BATTERY][PARAM_STATE_VARIANT] == STATE_VARIANT_NUMERIC


@pytest.mark.asyncio
async def test_update_device_storage_stores_int_percentage():
    """Storage percentage is stored as int with numeric variant."""
    device = ImouHaDevice("d1", "cam", "Imou", "m", "1.0")
    device.sensors[PARAM_STORAGE_USED] = {}
    delegate = MagicMock()
    delegate.async_get_device_storage = AsyncMock(
        return_value={"usedBytes": 50, "totalBytes": 100}
    )
    manager = ImouHaDeviceManager(delegate)
    await manager._async_update_device_storage(device)
    assert device.sensors[PARAM_STORAGE_USED][PARAM_STATE] == 50
    assert (
        device.sensors[PARAM_STORAGE_USED][PARAM_STATE_VARIANT] == STATE_VARIANT_NUMERIC
    )

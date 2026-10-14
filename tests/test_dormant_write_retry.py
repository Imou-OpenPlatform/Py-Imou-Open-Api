"""Tests for dormant control write retry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.const import PARAM_BATTERY, PARAM_REF, PARAM_STATE, PARAM_STATUS
from pyimouapi.dormant_retry import async_dormant_write_retry
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.sensor import apply_sensor_state


def _sleeping_battery_device() -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Battery Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_product_id("prod1")
    apply_sensor_state(device.sensors, PARAM_STATUS, "sleep")
    apply_sensor_state(device.sensors, PARAM_BATTERY, "80")
    device.switches["close_camera"] = {
        PARAM_REF: "13100",
        PARAM_STATE: False,
    }
    return device


@pytest.mark.asyncio
async def test_sleeping_device_retries_close_camera_after_dv1026() -> None:
    device = _sleeping_battery_device()
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock(
        side_effect=[
            RequestFailedException("DV1026:The device does not support the call"),
            None,
            None,
        ]
    )
    manager = ImouHaDeviceManager(delegate)

    with (
        patch(
            "pyimouapi.ha_device.async_dormant_write_retry",
            wraps=async_dormant_write_retry,
        ) as retry,
        patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()),
    ):
        await manager.async_switch_operation(device, "close_camera", True)

    assert retry.await_count == 1
    assert delegate.async_set_iot_device_properties.await_count == 3
    assert device.switches["close_camera"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_online_device_does_not_retry() -> None:
    device = _sleeping_battery_device()
    apply_sensor_state(device.sensors, PARAM_STATUS, "online")
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock(
        side_effect=RequestFailedException("DV1026:unsupported")
    )
    manager = ImouHaDeviceManager(delegate)

    with (
        patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()) as sleep,
        pytest.raises(RequestFailedException),
    ):
        await manager.async_switch_operation(device, "close_camera", True)

    sleep.assert_not_awaited()
    assert delegate.async_set_iot_device_properties.await_count == 1


@pytest.mark.asyncio
async def test_sleeping_device_no_retry_on_unrelated_error() -> None:
    device = _sleeping_battery_device()
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock(
        side_effect=RequestFailedException("OP9999:other")
    )
    manager = ImouHaDeviceManager(delegate)

    with (
        patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()) as sleep,
        pytest.raises(RequestFailedException),
    ):
        await manager.async_switch_operation(device, "close_camera", True)

    sleep.assert_not_awaited()
    assert delegate.async_set_iot_device_properties.await_count == 1

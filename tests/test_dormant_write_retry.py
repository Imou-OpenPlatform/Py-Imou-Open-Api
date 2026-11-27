"""Tests for dormant control write retry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.const import PARAM_STATE, PARAM_STATUS, PARAM_V2_TARGET_ID
from pyimouapi.dormant_retry import async_dormant_write_retry
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.sensor import apply_sensor_state


def _sleeping_device() -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_product_id("prod1")
    apply_sensor_state(device.sensors, PARAM_STATUS, "sleep")
    device.switches["close_camera"] = {
        PARAM_V2_TARGET_ID: "detection.privacy.enabled",
        PARAM_STATE: False,
    }
    return device


@pytest.mark.asyncio
async def test_sleeping_device_retries_close_camera_after_dv1026() -> None:
    device = _sleeping_device()
    manager = ImouHaDeviceManager(MagicMock())
    writer = AsyncMock(
        side_effect=[
            RequestFailedException(
                "The device does not support the call", api_code="DV1026"
            ),
            None,
        ]
    )

    with (
        patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()),
        patch("pyimouapi.ha_device.async_property_set", writer),
    ):
        await manager.async_switch_operation(device, "close_camera", True)

    assert writer.await_count == 2
    assert device.switches["close_camera"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_online_device_does_not_retry() -> None:
    device = _sleeping_device()
    apply_sensor_state(device.sensors, PARAM_STATUS, "online")
    manager = ImouHaDeviceManager(MagicMock())
    writer = AsyncMock(
        side_effect=RequestFailedException("unsupported", api_code="DV1026")
    )

    with (
        patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()) as sleep,
        patch("pyimouapi.ha_device.async_property_set", writer),
        pytest.raises(RequestFailedException),
    ):
        await manager.async_switch_operation(device, "close_camera", True)

    sleep.assert_not_awaited()
    assert writer.await_count == 1


@pytest.mark.asyncio
async def test_sleeping_device_no_retry_on_unrelated_error() -> None:
    device = _sleeping_device()
    manager = ImouHaDeviceManager(MagicMock())
    writer = AsyncMock(side_effect=RequestFailedException("other", api_code="OP9999"))

    with (
        patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()) as sleep,
        patch("pyimouapi.ha_device.async_property_set", writer),
        pytest.raises(RequestFailedException),
    ):
        await manager.async_switch_operation(device, "close_camera", True)

    sleep.assert_not_awaited()
    assert writer.await_count == 1


@pytest.mark.asyncio
async def test_custom_wait_seconds() -> None:
    device = _sleeping_device()
    calls: list[int] = []

    async def _fail_then_ok() -> None:
        if len(calls) == 0:
            calls.append(1)
            raise RequestFailedException("sleeping", api_code="DV1030")
        calls.append(2)

    with patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()) as sleep:
        await async_dormant_write_retry(device, _fail_then_ok, wait_seconds=25)

    sleep.assert_awaited_once_with(25)
    assert calls == [1, 2]


@pytest.mark.asyncio
async def test_manager_uses_configured_wait_seconds() -> None:
    device = _sleeping_device()
    manager = ImouHaDeviceManager(MagicMock(), dormant_write_retry_wait_seconds=42)
    writer = AsyncMock(
        side_effect=[
            RequestFailedException("sleep", api_code="DV1030"),
            None,
        ]
    )

    with (
        patch("pyimouapi.dormant_retry.asyncio.sleep", new=AsyncMock()) as sleep,
        patch("pyimouapi.ha_device.async_property_set", writer),
    ):
        await manager.async_switch_operation(device, "close_camera", True)

    sleep.assert_awaited_once_with(42)

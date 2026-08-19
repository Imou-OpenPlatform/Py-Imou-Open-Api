"""Tests for optimistic local state after writes (no post-write cloud read)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_CURRENT_OPTION,
    PARAM_DEVICE_VOLUME,
    PARAM_OPTIONS,
    PARAM_REF,
    PARAM_STATE,
    PARAM_VALUE_TYPE,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _ha_device(*, product_id: str | None = "prod1") -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    if product_id is not None:
        device.set_product_id(product_id)
    return device


@pytest.mark.asyncio
async def test_switch_operation_by_ref_updates_local_state_without_read() -> None:
    """IoT switch writes update local state without getIotDeviceProperties."""
    device = _ha_device()
    device.switches["motion_detect"] = {PARAM_REF: "12300", PARAM_STATE: False}
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    delegate.async_get_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_switch_operation(device, "motion_detect", True)

    assert device.switches["motion_detect"][PARAM_STATE] is True
    delegate.async_get_iot_device_properties.assert_not_called()


@pytest.mark.asyncio
async def test_select_option_by_ref_updates_local_state_without_read() -> None:
    """IoT alarm mode writes update panel state without a coordinator refresh read."""
    device = _ha_device()
    ImouHaDeviceManager.configure_alarm_control_panel_by_ref(
        ["15200"], True, [], device
    )
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    delegate.async_get_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_set_alarm_mode(device, "away")

    assert device.alarm_control_panel[PARAM_STATE] == "away"
    props = delegate.async_set_iot_device_properties.await_args.args[3]
    assert props == {"15200": 1}
    delegate.async_get_iot_device_properties.assert_not_called()


@pytest.mark.asyncio
async def test_select_volume_mute_writes_minus_one() -> None:
    device = _ha_device()
    device.selects[PARAM_DEVICE_VOLUME] = {
        PARAM_REF: "15400",
        PARAM_CURRENT_OPTION: "low",
        PARAM_OPTIONS: ["mute", "low", "medium", "high"],
        PARAM_VALUE_TYPE: "int",
    }
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_select_option(device, PARAM_DEVICE_VOLUME, "mute")

    assert device.selects[PARAM_DEVICE_VOLUME][PARAM_CURRENT_OPTION] == "mute"
    props = delegate.async_set_iot_device_properties.await_args.args[3]
    assert props == {"15400": -1}


@pytest.mark.asyncio
async def test_set_text_value_by_ref_updates_local_state_without_read() -> None:
    """IoT text writes update local state without getIotDeviceProperties."""
    device = _ha_device()
    device.texts["overcharge_switch"] = {
        PARAM_REF: "128900",
        PARAM_STATE: "5",
        PARAM_VALUE_TYPE: "int",
    }
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    delegate.async_get_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_set_text_value(device, "overcharge_switch", "100")

    assert device.texts["overcharge_switch"][PARAM_STATE] == "100"
    delegate.async_get_iot_device_properties.assert_not_called()


@pytest.mark.asyncio
async def test_set_count_down_text_updates_local_state_without_read() -> None:
    """Countdown text writes update local state without sleep/re-query."""
    device = _ha_device()
    device.switches["switch"] = {PARAM_REF: "10000", PARAM_STATE: False}
    device.texts["count_down_switch"] = {
        PARAM_REF: "28800",
        PARAM_STATE: "0",
    }
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    delegate.async_get_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    manager._async_update_device_switch_status_by_ref = AsyncMock()

    await manager.async_set_text_value(device, "count_down_switch", "10")

    assert device.texts["count_down_switch"][PARAM_STATE] == "10"
    manager._async_update_device_switch_status_by_ref.assert_awaited_once()
    delegate.async_iot_device_control.assert_awaited_once()
    delegate.async_get_iot_device_properties.assert_not_called()

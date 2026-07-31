"""Tests for optimistic local state after writes (no post-write cloud read)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_CURRENT_OPTION,
    PARAM_MODE,
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
    """IoT select writes update current_option without a coordinator refresh read."""
    device = _ha_device()
    device.selects[PARAM_MODE] = {
        PARAM_REF: "15200",
        PARAM_CURRENT_OPTION: "0",
        PARAM_OPTIONS: ["0", "1", "2"],
        PARAM_VALUE_TYPE: "int",
    }
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_select_option(device, PARAM_MODE, "1")

    assert device.selects[PARAM_MODE][PARAM_CURRENT_OPTION] == "1"
    delegate.async_get_iot_device_properties.assert_not_called()

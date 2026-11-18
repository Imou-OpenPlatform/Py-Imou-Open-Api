"""Alarm control panel writes go through device.property.set."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.const import (
    PARAM_STATE,
    PARAM_SUPPORTED,
    PARAM_V2_TARGET_ID,
    PARAM_VALUE_TYPE,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _device() -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_product_id("prod1")
    return device


def _panel(device: ImouHaDevice) -> None:
    device.alarm_control_panel = {
        PARAM_V2_TARGET_ID: "alarm.mode",
        PARAM_STATE: "home",
        PARAM_SUPPORTED: ["home", "away", "disarm"],
        PARAM_VALUE_TYPE: "int",
    }


@pytest.mark.asyncio
async def test_set_alarm_mode_writes_the_capability_and_updates_state() -> None:
    device = _device()
    _panel(device)
    manager = ImouHaDeviceManager(MagicMock())
    writer = AsyncMock()

    with patch("pyimouapi.ha_device.async_property_set", writer):
        await manager.async_set_alarm_mode(device, "away")

    assert device.alarm_control_panel[PARAM_STATE] == "away"
    assert writer.await_args.kwargs["properties"] == {"alarm.mode": 1}


@pytest.mark.asyncio
async def test_set_alarm_mode_unknown_raises() -> None:
    device = _device()
    _panel(device)
    manager = ImouHaDeviceManager(MagicMock())
    with pytest.raises(ValueError, match="unknown"):
        await manager.async_set_alarm_mode(device, "vacation")

"""Alarm control panel on ImouHaDevice (IoT ref 15200)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import PARAM_REF, PARAM_STATE, PARAM_SUPPORTED, PARAM_VALUE_TYPE
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _device() -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_product_id("prod1")
    return device


def test_configure_sets_panel_when_ref_present() -> None:
    device = _device()
    ImouHaDeviceManager.configure_alarm_control_panel_by_ref(
        ["15200"], True, [], device
    )
    panel = device.alarm_control_panel
    assert panel is not None
    assert panel[PARAM_REF] == "15200"
    assert panel[PARAM_STATE] == "home"
    assert panel[PARAM_SUPPORTED] == ["home", "away", "disarm"]
    assert panel[PARAM_VALUE_TYPE] == "int"


def test_configure_leaves_none_without_ref() -> None:
    device = _device()
    ImouHaDeviceManager.configure_alarm_control_panel_by_ref(
        ["15400"], True, [], device
    )
    assert device.alarm_control_panel is None


@pytest.mark.asyncio
async def test_set_alarm_mode_writes_ref_and_updates_state() -> None:
    device = _device()
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
async def test_set_alarm_mode_unknown_raises() -> None:
    device = _device()
    ImouHaDeviceManager.configure_alarm_control_panel_by_ref(
        ["15200"], True, [], device
    )
    manager = ImouHaDeviceManager(MagicMock())
    with pytest.raises(ValueError, match="unknown"):
        await manager.async_set_alarm_mode(device, "vacation")

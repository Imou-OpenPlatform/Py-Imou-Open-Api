"""Tests for applying detail properties to HA device entities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_CHANNELS,
    PARAM_CURRENT_OPTION,
    PARAM_ONLINE,
    PARAM_PROPERTIES,
    PARAM_REF,
    PARAM_STATE,
    PARAM_STATUS,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


def _online_device() -> ImouHaDevice:
    device = ImouHaDevice("dev1", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("pid1")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    return device


@pytest.mark.asyncio
async def test_update_from_detail_applies_switch_and_select():
    device = _online_device()
    device.switches["relay"] = {PARAM_REF: "10001", PARAM_STATE: False}
    device.selects["volume"] = {PARAM_REF: "15400", PARAM_CURRENT_OPTION: "0"}

    detail = {
        PARAM_PROPERTIES: {"10001": 1, "15400": -1},
        PARAM_CHANNELS: [],
    }

    delegate = MagicMock()
    manager = ImouHaDeviceManager(delegate)

    await manager._async_update_properties_from_detail(device, detail)

    assert device.switches["relay"][PARAM_STATE] is True
    assert device.selects["volume"][PARAM_CURRENT_OPTION] == "99"


@pytest.mark.asyncio
async def test_update_device_status_calls_detail_info_once():
    device = _online_device()
    device.switches["relay"] = {PARAM_REF: "10001", PARAM_STATE: False}

    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={PARAM_ONLINE: "1", "channels": []}
    )
    delegate.async_get_iot_device_detail_info = AsyncMock(
        return_value={
            PARAM_PROPERTIES: {"10001": 0},
            PARAM_CHANNELS: [],
        }
    )

    manager = ImouHaDeviceManager(delegate)
    await manager.async_update_device_status(device)

    delegate.async_get_iot_device_detail_info.assert_awaited_once()
    delegate.async_get_iot_device_properties = AsyncMock()
    delegate.async_get_iot_device_properties.assert_not_called()
    assert device.switches["relay"][PARAM_STATE] is False


@pytest.mark.asyncio
async def test_update_device_status_skips_detail_when_offline():
    device = _online_device()
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value
    device.switches["relay"] = {PARAM_REF: "10001", PARAM_STATE: False}

    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={PARAM_ONLINE: "0", "channels": []}
    )
    delegate.async_get_iot_device_detail_info = AsyncMock()

    manager = ImouHaDeviceManager(delegate)
    await manager.async_update_device_status(device)

    delegate.async_get_iot_device_detail_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_switch_operation_by_ref_uses_single_property_query(monkeypatch):
    device = _online_device()
    device.switches["relay"] = {PARAM_REF: "10001", PARAM_STATE: False}

    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    delegate.async_get_iot_device_properties = AsyncMock(
        return_value={PARAM_PROPERTIES: {"10001": 1}}
    )
    delegate.async_get_iot_device_detail_info = AsyncMock()

    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    manager = ImouHaDeviceManager(delegate)
    await manager._async_switch_operation_by_ref(device, "relay", True, "10001")

    delegate.async_get_iot_device_detail_info.assert_not_called()
    delegate.async_get_iot_device_properties.assert_awaited_once()
    assert device.switches["relay"][PARAM_STATE] is True

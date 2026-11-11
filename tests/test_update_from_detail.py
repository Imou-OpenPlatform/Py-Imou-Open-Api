"""Tests for applying detail properties to HA device entities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability
from pyimouapi.const import (
    PARAM_CHANNELS,
    PARAM_CURRENT_OPTION,
    PARAM_DEVICE_VOLUME,
    PARAM_ONLINE,
    PARAM_PROPERTIES,
    PARAM_REF,
    PARAM_STATE,
    PARAM_STATUS,
    PARAM_V2_TARGET_ID,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


def _online_device() -> ImouHaDevice:
    device = ImouHaDevice("dev1", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("pid1")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    return device


def _v2_relay_device() -> ImouHaDevice:
    device = _online_device()
    target = "control.outlet.enabled"
    device.set_capability_set(
        CapabilitySet(
            properties={
                target: PropertyCapability(
                    property_id=target,
                    access_mode="rw",
                    data_type="int",
                )
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.switches["relay"] = {
        PARAM_V2_TARGET_ID: target,
        PARAM_STATE: False,
    }
    return device


@pytest.mark.asyncio
async def test_update_from_detail_applies_alarm_control_panel():
    device = _online_device()
    ImouHaDeviceManager.configure_alarm_control_panel_by_ref(
        ["15200"], True, [], device
    )
    assert device.alarm_control_panel[PARAM_STATE] == "home"

    detail = {
        PARAM_PROPERTIES: {"15200": 2},
        PARAM_CHANNELS: [],
    }

    manager = ImouHaDeviceManager(MagicMock())
    await manager._async_update_properties_from_detail(device, detail)

    assert device.alarm_control_panel[PARAM_STATE] == "disarm"


@pytest.mark.asyncio
async def test_update_from_detail_applies_switch_and_select():
    device = _online_device()
    device.switches["relay"] = {PARAM_REF: "10001", PARAM_STATE: False}
    device.selects[PARAM_DEVICE_VOLUME] = {
        PARAM_REF: "15400",
        PARAM_CURRENT_OPTION: "low",
    }

    detail = {
        PARAM_PROPERTIES: {"10001": 1, "15400": -1},
        PARAM_CHANNELS: [],
    }

    delegate = MagicMock()
    manager = ImouHaDeviceManager(delegate)

    await manager._async_update_properties_from_detail(device, detail)

    assert device.switches["relay"][PARAM_STATE] is True
    assert device.selects[PARAM_DEVICE_VOLUME][PARAM_CURRENT_OPTION] == "mute"


@pytest.mark.asyncio
async def test_update_device_status_calls_detail_info_once():
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={PARAM_ONLINE: "1", "channels": []}
    )
    delegate.async_get_iot_device_detail_info = AsyncMock()

    manager = ImouHaDeviceManager(delegate)
    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value={target: 0}),
    ):
        await manager.async_update_device_status(device)

    delegate.async_get_iot_device_detail_info.assert_not_awaited()
    assert device.switches["relay"][PARAM_STATE] is False


@pytest.mark.asyncio
async def test_update_devices_status_skips_detail_for_listed_ids() -> None:
    """skip_iot_property_ids suppresses v2 property reads for that device."""
    device = _v2_relay_device()

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={PARAM_ONLINE: "1", "channels": []}
    )

    manager = ImouHaDeviceManager(delegate)
    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(),
    ) as prop_get:
        fetched = await manager.async_update_devices_status(
            [device], skip_iot_property_ids={device.device_id}
        )

    assert fetched == set()
    prop_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_devices_status_returns_fetched_physical_id() -> None:
    """A successful v2 property read is reported so HA can skip next interval."""
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={PARAM_ONLINE: "1", "channels": []}
    )

    manager = ImouHaDeviceManager(delegate)
    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value={target: 1}),
    ):
        fetched = await manager.async_update_devices_status([device])

    assert device.device_id in fetched
    assert device.switches["relay"][PARAM_STATE] is True


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
async def test_switch_operation_by_ref_updates_local_state_without_read():
    """Switch ref writes set local state without a post-write property read."""
    device = _online_device()
    device.switches["relay"] = {PARAM_REF: "10001", PARAM_STATE: False}

    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    delegate.async_get_iot_device_properties = AsyncMock(
        return_value={PARAM_PROPERTIES: {"10001": 1}}
    )
    delegate.async_get_iot_device_detail_info = AsyncMock()

    manager = ImouHaDeviceManager(delegate)
    await manager._async_switch_operation_by_ref(device, "relay", True, "10001")

    delegate.async_get_iot_device_detail_info.assert_not_called()
    delegate.async_get_iot_device_properties.assert_not_called()
    assert device.switches["relay"][PARAM_STATE] is True


def test_apply_iot_property_values_updates_known_switch() -> None:
    """Known v2 property ids update local switch state; unknown keys are ignored."""
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]
    manager = ImouHaDeviceManager(MagicMock())

    changed = manager.apply_iot_property_values(
        device, {target: 1, "unknown.property": 0}
    )

    assert changed is True
    assert device.switches["relay"][PARAM_STATE] is True


def test_apply_iot_property_values_unknown_only() -> None:
    """A payload with no matching entity refs is a no-op."""
    device = _online_device()
    device.switches["relay"] = {PARAM_REF: "10001", PARAM_STATE: False}
    manager = ImouHaDeviceManager(MagicMock())

    assert manager.apply_iot_property_values(device, {"99999": 1}) is False
    assert device.switches["relay"][PARAM_STATE] is False

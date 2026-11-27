"""Tests for applying detail properties to HA device entities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability
from pyimouapi.const import (
    PARAM_STATE,
    PARAM_STATUS,
    PARAM_V2_OUTPUT_FIELD,
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
async def test_update_device_status_calls_detail_info_once():
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[{"deviceId": "dev1", "deviceStatus": "online", "channelList": []}]
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
    delegate.async_list_device_details = AsyncMock(
        return_value=[{"deviceId": "dev1", "deviceStatus": "online", "channelList": []}]
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
async def test_skip_iot_properties_still_polls_service_sensors() -> None:
    """Property push skip leaves service-backed sensors on the poll path."""
    device = _v2_relay_device()
    device.sensors["power"] = {
        PARAM_V2_TARGET_ID: "power.outlet.read",
        PARAM_V2_OUTPUT_FIELD: "power",
        PARAM_STATE: None,
    }

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[{"deviceId": "dev1", "deviceStatus": "online", "channelList": []}]
    )
    manager = ImouHaDeviceManager(delegate)

    with (
        patch(
            "pyimouapi.ha_device.async_property_get",
            AsyncMock(),
        ) as prop_get,
        patch(
            "pyimouapi.ha_device.async_service_invoke",
            AsyncMock(return_value={"outputData": {"power": 12.5}}),
        ) as service_invoke,
    ):
        fetched = await manager.async_update_devices_status(
            [device], skip_iot_property_ids={device.device_id}
        )

    assert fetched == set()
    prop_get.assert_not_awaited()
    service_invoke.assert_awaited()
    assert device.sensors["power"][PARAM_STATE] == 12.5


@pytest.mark.asyncio
async def test_listed_skip_still_reads_a_device_without_product_id() -> None:
    """A device list row without productId keeps its entity poll."""
    device = _v2_relay_device()
    device._product_id = None

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[{"deviceId": "dev1", "deviceStatus": "online", "channelList": []}]
    )
    manager = ImouHaDeviceManager(delegate)
    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value={"control.outlet.enabled": 0}),
    ) as prop_get:
        await manager.async_update_devices_status(
            [device], skip_iot_property_ids={device.device_id}
        )

    prop_get.assert_awaited()


@pytest.mark.asyncio
async def test_update_devices_status_returns_fetched_physical_id() -> None:
    """A successful v2 property read is reported so HA can skip next interval."""
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[{"deviceId": "dev1", "deviceStatus": "online", "channelList": []}]
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
async def test_failed_v2_property_snapshot_is_retried() -> None:
    """A failed first property read must not suppress the next interval."""
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]
    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[{"deviceId": "dev1", "deviceStatus": "online", "channelList": []}]
    )
    manager = ImouHaDeviceManager(delegate)

    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(side_effect=[RuntimeError("property down"), {target: 1}]),
    ) as property_get:
        first = await manager.async_update_devices_status([device])
        second = await manager.async_update_devices_status([device])

    assert first == set()
    assert second == {device.device_id}
    assert property_get.await_count == 2
    assert device.switches["relay"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_partial_v2_snapshot_is_not_reported_complete() -> None:
    """A property success cannot hide a failed service-backed state read."""
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]
    device.sensors["power"] = {
        PARAM_V2_TARGET_ID: "power.outlet.read",
        PARAM_V2_OUTPUT_FIELD: "power",
    }
    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[{"deviceId": "dev1", "deviceStatus": "online", "channelList": []}]
    )
    manager = ImouHaDeviceManager(delegate)

    with (
        patch(
            "pyimouapi.ha_device.async_property_get",
            AsyncMock(return_value={target: 1}),
        ),
        patch(
            "pyimouapi.ha_device.async_service_invoke",
            AsyncMock(side_effect=RuntimeError("service down")),
        ),
    ):
        fetched = await manager.async_update_devices_status([device])

    assert fetched == set()
    assert device.switches["relay"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_update_device_status_skips_detail_when_offline():
    device = _online_device()
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value
    device.switches["relay"] = {
        PARAM_V2_TARGET_ID: "control.outlet.enabled",
        PARAM_STATE: False,
    }

    delegate = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[
            {"deviceId": "dev1", "deviceStatus": "offline", "channelList": []}
        ]
    )

    manager = ImouHaDeviceManager(delegate)
    await manager.async_update_device_status(device)


def test_apply_property_values_updates_known_switch() -> None:
    """Known v2 property ids update local switch state; unknown keys are ignored."""
    device = _v2_relay_device()
    target = device.switches["relay"][PARAM_V2_TARGET_ID]
    manager = ImouHaDeviceManager(MagicMock())

    changed = manager.apply_property_values(device, {target: 1, "unknown.property": 0})

    assert changed is True
    assert device.switches["relay"][PARAM_STATE] is True


def test_apply_property_values_unknown_only() -> None:
    """A payload with no matching v2 property ids is a no-op."""
    device = _v2_relay_device()
    manager = ImouHaDeviceManager(MagicMock())

    assert manager.apply_property_values(device, {"unknown.property": 1}) is False
    assert device.switches["relay"][PARAM_STATE] is False

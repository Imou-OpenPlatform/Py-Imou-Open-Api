"""ImouHaDeviceManager discovery uses capability.list, not IoT ref tables."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.capability.catalog import CapabilitySet
from pyimouapi.const import PARAM_MOTION_DETECT, PARAM_V2_TARGET_ID
from pyimouapi.device import ImouChannel, ImouDevice
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDeviceManager


def _iot_channel_device() -> ImouDevice:
    device = ImouDevice("PLUG1", "Plug", "1", "Imou", "SP")
    device.set_product_id("pid")
    device.set_device_ability_refs("11900,28800")
    device.set_channels([ImouChannel("0", "", "1", "11900")])
    return device


@pytest.mark.asyncio
async def test_iot_device_skips_ref_fallback_when_capability_list_works() -> None:
    from pyimouapi.capability.catalog import PropertyCapability

    cap = CapabilitySet(
        properties={
            "control.outlet.enabled": PropertyCapability(
                property_id="control.outlet.enabled",
                access_mode="rw",
                data_type="int",
                default_data=0,
            ),
        },
        services=frozenset(),
        events=frozenset(),
        product_id="pid",
    )
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[_iot_channel_device()])
    manager = ImouHaDeviceManager(delegate)
    with (
        patch(
            "pyimouapi.ha_device.async_capability_list",
            AsyncMock(return_value=cap),
        ),
        patch.object(
            manager,
            "_async_configure_device_by_ref",
            AsyncMock(),
        ) as ref_configure,
    ):
        devices = await manager.async_get_devices(fetch_ability_refs=False)
    assert len(devices) == 1
    assert devices[0].capability_set is cap
    ref_configure.assert_not_awaited()


@pytest.mark.asyncio
async def test_iot_device_does_not_ref_fallback_when_capability_list_fails() -> None:
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[_iot_channel_device()])
    manager = ImouHaDeviceManager(delegate)
    with (
        patch(
            "pyimouapi.ha_device.async_capability_list",
            AsyncMock(side_effect=ImouException("list down")),
        ),
        patch.object(
            manager,
            "_async_configure_device_by_ref",
            AsyncMock(),
        ) as ref_configure,
        patch(
            "pyimouapi.ha_device.configure_imou_ha_device_from_capability",
        ) as configure,
    ):
        devices = await manager.async_get_devices(fetch_ability_refs=False)
    assert len(devices) == 1
    assert devices[0].capability_set is None
    ref_configure.assert_not_awaited()
    configure.assert_not_called()


@pytest.mark.asyncio
async def test_paas_channel_registers_entities_from_capability_only() -> None:
    from pyimouapi.capability.catalog import PropertyCapability

    cap = CapabilitySet(
        properties={
            "detection.motion.enabled": PropertyCapability(
                property_id="detection.motion.enabled",
                access_mode="rw",
                data_type="int",
                default_data=0,
            ),
        },
        services=frozenset(),
        events=frozenset(),
    )
    device = ImouDevice("CAM1", "Cam", "1", "Imou", "IPC")
    device.set_channel_number(1)
    device.set_device_ability("MotionDetect")
    device.set_channels([ImouChannel("0", "Main", "1", "MotionDetect")])
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[device])
    manager = ImouHaDeviceManager(delegate)
    with (
        patch(
            "pyimouapi.ha_device.async_capability_list",
            AsyncMock(return_value=cap),
        ),
        patch.object(manager, "configure_device_by_ability") as ability_configure,
    ):
        devices = await manager.async_get_devices(fetch_ability_refs=False)
    ability_configure.assert_not_called()
    assert PARAM_MOTION_DETECT in devices[0].switches
    assert (
        devices[0].switches[PARAM_MOTION_DETECT][PARAM_V2_TARGET_ID]
        == "detection.motion.enabled"
    )


@pytest.mark.asyncio
async def test_paas_skips_ability_fallback_when_capability_list_missing() -> None:
    device = ImouDevice("CAM1", "Cam", "1", "Imou", "IPC")
    device.set_channel_number(1)
    device.set_device_ability("MotionDetect")
    device.set_channels([ImouChannel("0", "Main", "1", "MotionDetect")])
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[device])
    manager = ImouHaDeviceManager(delegate)
    with (
        patch(
            "pyimouapi.ha_device.async_capability_list",
            AsyncMock(side_effect=ImouException("unavailable")),
        ),
        patch.object(manager, "configure_device_by_ability") as ability_configure,
    ):
        devices = await manager.async_get_devices()
    ability_configure.assert_not_called()
    assert devices[0].capability_set is None
    assert devices[0].switches == {}

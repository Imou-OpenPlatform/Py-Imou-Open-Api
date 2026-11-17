"""ImouHaDeviceManager discovery uses capability.list, not IoT ref tables."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.capability.catalog import CapabilitySet
from pyimouapi.const import PARAM_MOTION_DETECT, PARAM_V2_TARGET_ID
from pyimouapi.device import ImouChannel, ImouDevice, ImouDeviceManager
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDeviceManager


def _iot_channel_device() -> ImouDevice:
    device = ImouDevice("PLUG1", "Plug", "1", "Imou", "SP")
    device.set_product_id("pid")
    device.set_device_ability_refs("11900,28800")
    device.set_channels([ImouChannel("0", "", "1", "11900")])
    return device


@pytest.mark.asyncio
async def test_device_listing_does_not_fetch_iot_detail_by_default() -> None:
    delegate = MagicMock()
    delegate.async_request_api = AsyncMock(
        side_effect=[
            {
                "deviceList": [
                    {
                        "deviceId": "PLUG1",
                        "deviceName": "Plug",
                        "deviceStatus": "1",
                        "brand": "Imou",
                        "deviceModel": "SP",
                        "productId": "pid",
                    }
                ]
            },
            {"item": [{"productId": "pid", "deviceType": "Plug"}]},
        ]
    )
    manager = ImouDeviceManager(delegate)
    manager._async_update_device_ability_refs = AsyncMock()

    devices = await manager.async_get_devices()

    manager._async_update_device_ability_refs.assert_not_awaited()
    assert devices[0].product_device_type == "Plug"


@pytest.mark.asyncio
async def test_device_listing_can_explicitly_fetch_legacy_ability_refs() -> None:
    delegate = MagicMock()
    delegate.async_request_api = AsyncMock(
        side_effect=[
            {
                "deviceList": [
                    {
                        "deviceId": "PLUG1",
                        "deviceName": "Plug",
                        "deviceStatus": "1",
                        "brand": "Imou",
                        "deviceModel": "SP",
                        "productId": "pid",
                    }
                ]
            },
            {"item": [{"productId": "pid", "deviceType": "Plug"}]},
        ]
    )
    manager = ImouDeviceManager(delegate)
    manager._async_update_device_ability_refs = AsyncMock()

    await manager.async_get_devices(fetch_ability_refs=True)

    manager._async_update_device_ability_refs.assert_awaited_once()


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


@pytest.mark.asyncio
async def test_capability_list_is_not_repeated_for_a_known_channel() -> None:
    """Discovery after the first list reuses the stored capability set."""
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
    device.set_channels([ImouChannel("0", "Main", "1", "MotionDetect")])
    device.channels[0].set_ai_insight_status("using")
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[device])
    manager = ImouHaDeviceManager(delegate)
    listed = AsyncMock(return_value=cap)
    with patch("pyimouapi.ha_device.async_capability_list", listed):
        first = await manager.async_get_devices()
        second = await manager.async_get_devices()
    listed.assert_awaited_once()
    assert first[0].ai_insight_label == "active"
    assert second[0].ai_insight_label == "active"
    assert second[0].capability_set is cap


@pytest.mark.asyncio
async def test_empty_capability_list_is_cached_and_registers_nothing() -> None:
    empty = CapabilitySet(properties={}, services=frozenset(), events=frozenset())
    device = ImouDevice("CAM1", "Cam", "1", "Imou", "IPC")
    device.set_product_id("PID")
    device.set_channels([ImouChannel("0", "Main", "1", "")])
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[device])
    manager = ImouHaDeviceManager(delegate)
    listed = AsyncMock(return_value=empty)
    with patch("pyimouapi.ha_device.async_capability_list", listed):
        first = await manager.async_get_devices()
        second = await manager.async_get_devices()
    listed.assert_awaited_once()
    assert first[0].capability_set is None
    assert second[0].switches == {}


@pytest.mark.asyncio
async def test_failed_capability_list_is_retried() -> None:
    from pyimouapi.exceptions import RequestFailedException

    device = ImouDevice("CAM1", "Cam", "1", "Imou", "IPC")
    device.set_channels([ImouChannel("0", "Main", "1", "")])
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[device])
    manager = ImouHaDeviceManager(delegate)
    listed = AsyncMock(side_effect=RequestFailedException("temporary"))
    with patch("pyimouapi.ha_device.async_capability_list", listed):
        await manager.async_get_devices()
        await manager.async_get_devices()
    assert listed.await_count == 2


@pytest.mark.asyncio
async def test_unselected_device_does_not_request_capability_list() -> None:
    selected = ImouDevice("KEEP", "Keep", "1", "Imou", "IPC")
    selected.set_channels([ImouChannel("0", "Main", "1", "")])
    other = ImouDevice("SKIP", "Skip", "1", "Imou", "IPC")
    other.set_channels([ImouChannel("0", "Main", "1", "")])
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(return_value=[selected, other])
    manager = ImouHaDeviceManager(delegate)
    listed = AsyncMock(
        return_value=CapabilitySet(
            properties={},
            services=frozenset(),
            events=frozenset(),
        )
    )
    with patch("pyimouapi.ha_device.async_capability_list", listed):
        devices = await manager.async_get_devices(configure_device_ids={"KEEP"})
    assert {item.device_id for item in devices} == {"KEEP", "SKIP"}
    assert listed.await_count == 1
    assert listed.await_args.kwargs["device_id"] == "KEEP"

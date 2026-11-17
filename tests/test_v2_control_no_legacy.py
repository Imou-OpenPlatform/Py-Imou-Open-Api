from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.const import PARAM_STATE, PARAM_V2_TARGET_ID
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _manager() -> tuple[ImouHaDeviceManager, MagicMock]:
    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_get_device_storage = AsyncMock()
    delegate.async_get_device_power_info = AsyncMock()
    delegate.async_get_device_night_vision_mode = AsyncMock()
    delegate.async_set_device_night_vision_mode = AsyncMock()
    delegate.async_control_device_ptz = AsyncMock()
    delegate.async_restart_device = AsyncMock()
    return ImouHaDeviceManager(delegate), delegate


@pytest.mark.asyncio
async def test_storage_and_battery_poll_does_not_call_legacy_apis() -> None:
    manager, delegate = _manager()
    device = ImouHaDevice("SN1", "Cam", "Imou", "IPC", "1.0")
    device.sensors["storage_used"] = {PARAM_STATE: 0}
    device.sensors["battery"] = {PARAM_STATE: 0}
    await manager._async_update_device_sensor_status(device)
    delegate.async_get_device_storage.assert_not_called()
    delegate.async_get_device_power_info.assert_not_called()
    assert device.sensors["storage_used"][PARAM_STATE] == 0


@pytest.mark.asyncio
async def test_night_vision_without_capability_is_not_written_to_legacy_api() -> None:
    manager, delegate = _manager()
    device = ImouHaDevice("SN1", "Cam", "Imou", "IPC", "1.0")
    device.selects["night_vision_mode"] = {"current_option": "", "options": []}
    with pytest.raises(RequestFailedException):
        await manager.async_select_option(device, "night_vision_mode", "intelligent")
    delegate.async_set_device_night_vision_mode.assert_not_called()


@pytest.mark.asyncio
async def test_ptz_without_service_is_rejected() -> None:
    manager, delegate = _manager()
    device = ImouHaDevice("SN1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.buttons["ptz_up"] = {}
    with pytest.raises(RequestFailedException, match="云台"):
        await manager.async_press_button(device, "ptz_up", 500)
    delegate.async_control_device_ptz.assert_not_called()


@pytest.mark.asyncio
async def test_reboot_posts_named_v2_endpoint() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock(return_value={})
    from pyimouapi.device import ImouDeviceManager

    devices = ImouDeviceManager(client)
    await devices.async_restart_device("SN1", "PID1")
    client.async_request_api.assert_awaited_once_with(
        "/openapi/v2/device.reboot.execute",
        {"deviceId": "SN1", "productId": "PID1"},
    )


@pytest.mark.asyncio
async def test_reboot_button_does_not_use_service_invoke() -> None:
    manager, delegate = _manager()
    delegate.async_restart_device = AsyncMock()
    device = ImouHaDevice("SN1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("PID1")
    device.buttons["restart_device"] = {PARAM_V2_TARGET_ID: "device.reboot.execute"}
    with patch("pyimouapi.ha_device.async_service_invoke", AsyncMock()) as invoke:
        await manager.async_press_button(device, "restart_device", 0)
    invoke.assert_not_called()
    delegate.async_restart_device.assert_awaited_once_with("SN1", "PID1")


@pytest.mark.asyncio
async def test_missing_storage_property_keeps_the_previous_percent() -> None:
    from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability

    manager, delegate = _manager()
    device = ImouHaDevice("SN1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("PID1")
    device.set_channel_id("0")
    device.set_capability_set(
        CapabilitySet(
            properties={
                "storage.local.capacity": PropertyCapability(
                    property_id="storage.local.capacity",
                    access_mode="r",
                    data_type="int",
                )
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.sensors["storage_used"] = {
        PARAM_V2_TARGET_ID: "storage.local.capacity",
        PARAM_STATE: 40,
    }
    delegate.async_get_device_online_status = AsyncMock(
        return_value={"online": 1, "channels": [{"channelId": "0", "online": 1}]}
    )
    with patch("pyimouapi.ha_device.async_property_get", AsyncMock(return_value={})):
        await manager.async_update_devices_status([device])
    assert device.sensors["storage_used"][PARAM_STATE] == 40

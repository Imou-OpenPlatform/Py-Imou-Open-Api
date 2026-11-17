from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_CHANNELS,
    PARAM_DEVICE_ID,
    PARAM_PRODUCT_ID,
    PARAM_STATUS,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


def test_get_device_status_accepts_int_and_numeric_string() -> None:
    assert ImouHaDeviceManager.get_device_status(1) == DeviceStatus.ONLINE.value
    assert ImouHaDeviceManager.get_device_status("0") == DeviceStatus.OFFLINE.value
    assert ImouHaDeviceManager.get_device_status(3) == DeviceStatus.UPGRADING.value
    assert ImouHaDeviceManager.get_device_status("4") == DeviceStatus.SLEEP.value
    assert ImouHaDeviceManager.get_device_status(9) == DeviceStatus.OFFLINE.value


@pytest.mark.asyncio
async def test_status_get_uses_channel_online_field() -> None:
    device = ImouHaDevice("SN1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("PID1")
    device.set_channel_id("0")
    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={
            "online": 1,
            PARAM_CHANNELS: [{"channelId": "0", "online": 4}],
        }
    )
    manager = ImouHaDeviceManager(delegate)

    await manager._async_update_status_shared([device])

    delegate.async_get_device_online_status.assert_awaited_once_with("SN1", "PID1")
    assert device.sensors[PARAM_STATUS]["state"] == DeviceStatus.SLEEP.value


@pytest.mark.asyncio
async def test_online_status_request_posts_v2_status_get() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock(return_value={"online": 1, "channels": []})
    from pyimouapi.device import ImouDeviceManager

    manager = ImouDeviceManager(client)
    await manager.async_get_device_online_status("SN1", "PID1")
    client.async_request_api.assert_awaited_once_with(
        "/openapi/v2/device.status.get",
        {PARAM_DEVICE_ID: "SN1", PARAM_PRODUCT_ID: "PID1"},
    )

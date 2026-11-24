from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import PARAM_DEVICE_ID, PARAM_DEVICE_LIST, PARAM_STATUS
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


def test_get_device_status_accepts_int_and_words() -> None:
    assert ImouHaDeviceManager.get_device_status(1) == DeviceStatus.ONLINE.value
    assert ImouHaDeviceManager.get_device_status("online") == DeviceStatus.ONLINE.value
    assert ImouHaDeviceManager.get_device_status("0") == DeviceStatus.OFFLINE.value
    assert (
        ImouHaDeviceManager.get_device_status("offline") == DeviceStatus.OFFLINE.value
    )
    assert ImouHaDeviceManager.get_device_status(3) == DeviceStatus.UPGRADING.value
    assert ImouHaDeviceManager.get_device_status("upgrading") == (
        DeviceStatus.UPGRADING.value
    )
    assert ImouHaDeviceManager.get_device_status("4") == DeviceStatus.SLEEP.value
    assert ImouHaDeviceManager.get_device_status("sleep") == DeviceStatus.SLEEP.value
    assert ImouHaDeviceManager.get_device_status(9) == DeviceStatus.OFFLINE.value


@pytest.mark.asyncio
async def test_detail_list_sets_status_cloud_and_insight() -> None:
    device = ImouHaDevice("SN1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("PID1")
    device.set_channel_id("0")
    delegate = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[
            {
                "deviceId": "SN1",
                "deviceStatus": "online",
                "channelList": [
                    {
                        "channelId": "0",
                        "channelStatus": "sleep",
                        "csStatus": "notExist",
                        "aiInsightStatus": "using",
                    }
                ],
            }
        ]
    )
    manager = ImouHaDeviceManager(delegate)

    await manager._async_refresh_detail_status([device])

    delegate.async_list_device_details.assert_awaited_once_with(["SN1"])
    assert device.sensors[PARAM_STATUS]["state"] == DeviceStatus.SLEEP.value
    assert device.cloud_storage_label == "inactive"
    assert device.ai_insight_label == "active"


@pytest.mark.asyncio
async def test_detail_list_request_posts_serials() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock(return_value={"deviceList": []})
    from pyimouapi.device import ImouDeviceManager

    manager = ImouDeviceManager(client)
    await manager.async_list_device_details(["SN1", "SN1", "SN2"])
    client.async_request_api.assert_awaited_once_with(
        "/openapi/v2/device.detail.list",
        {
            PARAM_DEVICE_LIST: [
                {PARAM_DEVICE_ID: "SN1"},
                {PARAM_DEVICE_ID: "SN2"},
            ]
        },
    )

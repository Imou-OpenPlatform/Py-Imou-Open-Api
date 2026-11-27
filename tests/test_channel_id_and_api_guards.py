"""Guards for channelId type mismatch and empty API payloads."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_CHANNEL_ID,
    PARAM_STATE,
    PARAM_STATUS,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


@pytest.mark.asyncio
async def test_online_status_matches_int_channel_id():
    """API may return channelId as int while HA device stores str."""
    device = ImouHaDevice("dev1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value

    delegate = MagicMock()
    delegate.async_list_device_details = AsyncMock(
        return_value=[
            {
                "deviceId": "dev1",
                "deviceStatus": "online",
                "channelList": [{PARAM_CHANNEL_ID: 0, "channelStatus": "online"}],
            }
        ]
    )
    manager = ImouHaDeviceManager(delegate)
    await manager._async_refresh_detail_status([device])

    assert device.sensors[PARAM_STATUS][PARAM_STATE] == DeviceStatus.ONLINE.value

"""Guards for channelId type mismatch and empty API payloads."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_ABILITY_REFS,
    PARAM_CHANNEL_ID,
    PARAM_CHANNELS,
    PARAM_DEVICE_LIST,
    PARAM_ONLINE,
    PARAM_REF,
    PARAM_STATE,
    PARAM_STATUS,
    PARAM_VALUE_TYPE,
)
from pyimouapi.device import ImouChannel, ImouDevice, ImouDeviceManager
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


@pytest.mark.asyncio
async def test_online_status_matches_int_channel_id():
    """API may return channelId as int while HA device stores str."""
    device = ImouHaDevice("dev1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value

    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={
            PARAM_ONLINE: "1",
            PARAM_CHANNELS: [
                {PARAM_CHANNEL_ID: 0, PARAM_ONLINE: "1"},
            ],
        }
    )
    manager = ImouHaDeviceManager(delegate)
    await manager._async_update_status_shared([device])

    assert device.sensors[PARAM_STATUS][PARAM_STATE] == DeviceStatus.ONLINE.value


@pytest.mark.asyncio
async def test_ability_refs_match_int_channel_id():
    """Channel abilityRefs lookup must tolerate int/str channelId."""
    channel = ImouChannel("0", "ch0", "1", "ability")
    device = ImouDevice("dev1", "Cam", "1", "Imou", "IPC")
    device.set_channels([channel])
    device.set_product_id("pid1")

    manager = ImouDeviceManager(MagicMock())
    manager.async_get_iot_device_detail_info = AsyncMock(
        return_value={
            PARAM_ABILITY_REFS: "devAbility",
            PARAM_CHANNELS: [
                {PARAM_CHANNEL_ID: 0, PARAM_ABILITY_REFS: "chAbility"},
            ],
        }
    )
    await manager._async_update_device_ability_refs(device)

    assert channel.channel_ability_refs == "chAbility"


@pytest.mark.asyncio
async def test_get_iot_device_properties_empty_list():
    """Empty deviceList must not raise IndexError."""
    api = MagicMock()
    api.async_request_api = AsyncMock(return_value={PARAM_DEVICE_LIST: []})
    manager = ImouDeviceManager(api)

    result = await manager.async_get_iot_device_properties(
        "dev1", "0", "pid", ["10001"]
    )
    assert result == {}


@pytest.mark.asyncio
async def test_set_text_value_coerces_str_type():
    """value_type=str must stringify the payload."""
    device = ImouHaDevice("dev1", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("pid1")
    device.texts["name"] = {
        PARAM_REF: "20001",
        PARAM_VALUE_TYPE: "str",
        PARAM_STATE: "",
    }

    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_set_text_value(device, "name", "hello")

    delegate.async_set_iot_device_properties.assert_awaited_with(
        "dev1", None, "pid1", {"20001": "hello"}
    )

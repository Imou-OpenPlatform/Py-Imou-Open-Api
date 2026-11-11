"""V2 property.get / property.set switch and select paths."""

from unittest.mock import AsyncMock, patch

import pytest
from pyimouapi.const import PARAM_STATE, PARAM_V2_TARGET_ID
from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient


@pytest.fixture
def ha_manager() -> ImouHaDeviceManager:
    client = ImouOpenApiClient("app", "secret", "api.example.com")
    return ImouHaDeviceManager(ImouDeviceManager(client))


def _switch_device() -> ImouHaDevice:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("pid")
    device.set_channel_id("0")
    device.switches["motion_detect"] = {
        PARAM_V2_TARGET_ID: "detection.motion.enabled",
        PARAM_STATE: False,
    }
    return device


@pytest.mark.asyncio
async def test_switch_operation_uses_property_set(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = _switch_device()
    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager.async_switch_operation(device, "motion_detect", True)
    mock_set.assert_awaited_once()
    kwargs = mock_set.await_args.kwargs
    assert kwargs["properties"] == {"detection.motion.enabled": 1}
    assert device.switches["motion_detect"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_update_v2_property_entities_reads_batch(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = _switch_device()
    with patch(
        "pyimouapi.ha_device.async_property_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {"detection.motion.enabled": 1}
        await ha_manager._async_update_v2_property_entities(device)
    mock_get.assert_awaited_once()
    assert device.switches["motion_detect"][PARAM_STATE] is True

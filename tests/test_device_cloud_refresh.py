"""getDeviceCloud refresh during status polls."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


@pytest.mark.asyncio
async def test_cloud_refresh_skips_when_cs_inactive() -> None:
    delegate = MagicMock()
    delegate.async_get_device_cloud = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_cs_status("notExist")
    await manager._async_refresh_ai_insight_cloud_plans([device])
    delegate.async_get_device_cloud.assert_not_called()
    assert device.ai_insight_cloud_label == "inactive"


@pytest.mark.asyncio
async def test_cloud_refresh_sets_active_on_type_six() -> None:
    delegate = MagicMock()
    delegate.async_get_device_cloud = AsyncMock(
        return_value={"strategyType": "6", "strategyStatus": 1}
    )
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_cs_status("using")
    await manager._async_refresh_ai_insight_cloud_plans([device])
    delegate.async_get_device_cloud.assert_awaited_once_with("SN", "0")
    assert device.ai_insight_cloud_active


@pytest.mark.asyncio
async def test_st1002_marks_inactive() -> None:
    delegate = MagicMock()
    delegate.async_get_device_cloud = AsyncMock(
        side_effect=ImouException("no plan", api_code="ST1002")
    )
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_cs_status("on")
    await manager._async_refresh_ai_insight_cloud_plans([device])
    assert device.ai_insight_cloud_label == "inactive"


@pytest.mark.asyncio
async def test_transient_error_keeps_previous_label() -> None:
    delegate = MagicMock()
    delegate.async_get_device_cloud = AsyncMock(
        side_effect=ImouException("offline", api_code="DV1007")
    )
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_cs_status("using")
    device.set_ai_insight_cloud_label("active")
    await manager._async_refresh_ai_insight_cloud_plans([device])
    assert device.ai_insight_cloud_active


def test_insight_features_active() -> None:
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_ai_insight_status("off")
    device.set_ai_insight_cloud_label("active")
    assert device.insight_features_active
    device.set_ai_insight_cloud_label("paused")
    assert device.insight_features_active
    assert not device.ai_insight_cloud_active
    device.set_ai_insight_cloud_label("inactive")
    device.set_ai_insight_status("on")
    assert device.insight_features_active
    device.set_ai_insight_status("off")
    assert not device.insight_features_active

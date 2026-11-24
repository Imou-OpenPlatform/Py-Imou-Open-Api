"""queryDeviceAiInsight refresh during status polls."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


@pytest.mark.asyncio
async def test_insight_refresh_skips_when_list_inactive() -> None:
    delegate = MagicMock()
    delegate.async_query_device_ai_insight = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_ai_insight_status("notExist")
    await manager._async_refresh_ai_insight_plans([device])
    delegate.async_query_device_ai_insight.assert_not_called()
    assert device.ai_insight_label == "inactive"


@pytest.mark.asyncio
async def test_insight_refresh_sets_paused() -> None:
    delegate = MagicMock()
    delegate.async_query_device_ai_insight = AsyncMock(
        return_value={"strategyStatus": 2, "name": "AI Insight"}
    )
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_ai_insight_status("using")
    await manager._async_refresh_ai_insight_plans([device])
    delegate.async_query_device_ai_insight.assert_awaited_once_with("SN", "0")
    assert device.ai_insight_label == "paused"
    assert device.ai_insight_usable
    assert not device.ai_insight_active


@pytest.mark.asyncio
async def test_ai1006_marks_inactive() -> None:
    delegate = MagicMock()
    delegate.async_query_device_ai_insight = AsyncMock(
        side_effect=ImouException("no plan", api_code="AI1006")
    )
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_ai_insight_status("on")
    await manager._async_refresh_ai_insight_plans([device])
    assert device.ai_insight_label == "inactive"


@pytest.mark.asyncio
async def test_transient_error_keeps_list_label() -> None:
    delegate = MagicMock()
    delegate.async_query_device_ai_insight = AsyncMock(
        side_effect=ImouException("offline", api_code="DV1007")
    )
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_ai_insight_status("using")
    await manager._async_refresh_ai_insight_plans([device])
    assert device.ai_insight_active


def test_insight_features_active_includes_paused_plan() -> None:
    device = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_ai_insight_status("off")
    device.set_ai_insight_label("paused")
    assert device.insight_features_active
    device.set_ai_insight_label("inactive")
    assert not device.insight_features_active

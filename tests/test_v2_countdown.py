"""V2 outlet countdown read/write via device.service.invoke."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_OUTPUT_DATA,
    PARAM_STATE,
    PARAM_V2_TARGET_ID,
    PARAM_V2_WRITE_TARGET_ID,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


@pytest.mark.asyncio
async def test_countdown_v2_read_minutes() -> None:
    device = ImouHaDevice("PLUG1", "Plug", "Imou", "SP", "1.0")
    device.set_product_id("pid")
    device.texts["count_down_switch"] = {
        PARAM_V2_TARGET_ID: "control.outlet.countdownGet",
        PARAM_V2_WRITE_TARGET_ID: "control.outlet.countdownSet",
        PARAM_STATE: "0",
    }
    client = MagicMock()
    client.async_request_api = AsyncMock(
        return_value={PARAM_OUTPUT_DATA: {"minutes": 15}}
    )
    delegate = MagicMock()
    delegate.api_client = client
    manager = ImouHaDeviceManager(delegate)
    await manager._async_update_countdown_v2(
        device, "count_down_switch", device.texts["count_down_switch"]
    )
    assert device.texts["count_down_switch"][PARAM_STATE] == "15"


@pytest.mark.asyncio
async def test_countdown_v2_write_invokes_set_service() -> None:
    device = ImouHaDevice("PLUG1", "Plug", "Imou", "SP", "1.0")
    device.set_product_id("pid")
    device.switches["switch"] = {
        PARAM_V2_TARGET_ID: "control.outlet.enabled",
        PARAM_STATE: True,
    }
    device.texts["count_down_switch"] = {
        PARAM_V2_TARGET_ID: "control.outlet.countdownGet",
        PARAM_V2_WRITE_TARGET_ID: "control.outlet.countdownSet",
        PARAM_STATE: "0",
    }
    client = MagicMock()
    client.async_request_api = AsyncMock(
        side_effect=[
            {PARAM_OUTPUT_DATA: {"value": 1}},
            {},
        ]
    )
    delegate = MagicMock()
    delegate.api_client = client
    manager = ImouHaDeviceManager(delegate)
    await manager._async_set_count_down_switch_time_v2(
        device, "20", device.texts["count_down_switch"]
    )
    assert device.texts["count_down_switch"][PARAM_STATE] == "20"
    assert client.async_request_api.await_count == 2

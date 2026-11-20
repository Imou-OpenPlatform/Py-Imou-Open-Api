"""Step failures DV2116 and DV1026 switch that channel to relative."""

from unittest.mock import AsyncMock, patch

import pytest
from pyimouapi.const import PARAM_STATE, PARAM_STATUS, PARAM_V2_TARGET_ID
from pyimouapi.device import ImouDeviceManager
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient


def _manager() -> ImouHaDeviceManager:
    client = ImouOpenApiClient("app", "secret", "api.example.com")
    manager = ImouHaDeviceManager(ImouDeviceManager(client))
    manager.set_dormant_write_retry_wait_seconds(0)
    return manager


def _camera() -> ImouHaDevice:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_capability_ids({"ptz.aim.step", "ptz.aim.relative"})
    device.buttons["ptz_up"] = {PARAM_V2_TARGET_ID: "ptz.aim.step"}
    device.buttons["ptz_left"] = {PARAM_V2_TARGET_ID: "ptz.aim.step"}
    return device


@pytest.mark.asyncio
async def test_dv2116_retries_relative_and_later_press_skips_step() -> None:
    manager = _manager()
    device = _camera()
    with patch(
        "pyimouapi.ha_device.async_service_invoke", new_callable=AsyncMock
    ) as invoke:
        invoke.side_effect = [
            RequestFailedException("rejected", api_code="DV2116"),
            None,
            None,
        ]
        await manager.async_press_button(device, "ptz_up", 400)
        await manager.async_press_button(device, "ptz_left", 400)

    assert [call.kwargs["service_id"] for call in invoke.await_args_list] == [
        "ptz.aim.step",
        "ptz.aim.relative",
        "ptz.aim.relative",
    ]
    assert invoke.await_args_list[1].kwargs["input_data"]["vertical"] == "0.5"
    assert invoke.await_args_list[2].kwargs["input_data"]["horizontal"] == "-0.5"


@pytest.mark.asyncio
async def test_dv1026_without_relative_retries_step_when_asleep() -> None:
    manager = _manager()
    device = _camera()
    device.set_capability_ids({"ptz.aim.step"})
    device.sensors[PARAM_STATUS][PARAM_STATE] = "sleep"
    with patch(
        "pyimouapi.ha_device.async_service_invoke", new_callable=AsyncMock
    ) as invoke:
        invoke.side_effect = [
            RequestFailedException("asleep", api_code="DV1026"),
            None,
        ]
        await manager.async_press_button(device, "ptz_up", 400)

    assert [call.kwargs["service_id"] for call in invoke.await_args_list] == [
        "ptz.aim.step",
        "ptz.aim.step",
    ]


@pytest.mark.asyncio
async def test_relative_failure_is_not_retried_as_step() -> None:
    manager = _manager()
    device = _camera()
    with patch(
        "pyimouapi.ha_device.async_service_invoke", new_callable=AsyncMock
    ) as invoke:
        invoke.side_effect = RequestFailedException("no", api_code="DV2116")
        with pytest.raises(RequestFailedException):
            await manager.async_press_button(device, "ptz_up", 400)

    assert [call.kwargs["service_id"] for call in invoke.await_args_list] == [
        "ptz.aim.step",
        "ptz.aim.relative",
    ]


@pytest.mark.asyncio
async def test_other_channel_stays_on_step() -> None:
    manager = _manager()
    moved = _camera()
    other = _camera()
    other.set_channel_id("1")
    with patch(
        "pyimouapi.ha_device.async_service_invoke", new_callable=AsyncMock
    ) as invoke:
        invoke.side_effect = [
            RequestFailedException("rejected", api_code="DV2116"),
            None,
            None,
        ]
        await manager.async_press_button(moved, "ptz_up", 400)
        await manager.async_press_button(other, "ptz_up", 400)

    assert [call.kwargs["service_id"] for call in invoke.await_args_list] == [
        "ptz.aim.step",
        "ptz.aim.relative",
        "ptz.aim.step",
    ]

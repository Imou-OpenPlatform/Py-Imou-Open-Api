"""A failing status read is reported, and cancellation is not swallowed."""

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from pyimouapi.const import PARAM_STATE, PARAM_STATUS
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


def build_camera() -> ImouHaDevice:
    device = ImouHaDevice("dev0", "Camera", "Imou", "IPC-A1", "1.0")
    device.set_channel_id("0")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    return device


@pytest.mark.asyncio
async def test_a_failing_read_is_reported_instead_of_vanishing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Status failures used to be gathered and dropped without a word."""
    manager = ImouHaDeviceManager(MagicMock())
    device = build_camera()

    async def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("selects boom")

    manager._async_update_device_select_status = boom
    manager._async_refresh_detail_status = _noop

    with caplog.at_level(logging.WARNING):
        await manager.async_update_device_status(device)

    assert "selects boom" in caplog.text


async def _noop(*args: Any, **kwargs: Any) -> None:
    """Skip the online check so the entity reads are reached."""
    return None


@pytest.mark.asyncio
async def test_cancelling_a_poll_is_not_swallowed() -> None:
    """Gathering must let cancellation through rather than log it as a failure."""
    manager = ImouHaDeviceManager(MagicMock())
    device = build_camera()

    async def cancelled() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await manager._async_gather_reads([cancelled()], device, "selects")

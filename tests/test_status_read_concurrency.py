"""Tests that one device's status reads are issued as a batch.

A camera carries a handful of ability-backed switches plus battery and storage
sensors. Reading them one after another is what decides how long a poll takes,
so these pin that they overlap.
"""

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from pyimouapi.const import (
    PARAM_BATTERY,
    PARAM_FUNCTION_TYPE,
    PARAM_ON,
    PARAM_STATE,
    PARAM_STATUS,
    PARAM_STORAGE_USED,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


class StatusRecorder:
    """Stands in for async_get_device_status and tracks concurrency."""

    def __init__(self) -> None:
        """Initialize the recorder."""
        self.abilities: list[str] = []
        self._in_flight = 0
        self.max_in_flight = 0

    async def __call__(
        self, device_id: str, channel_id: str | None, ability_type: str
    ) -> dict[str, Any]:
        """Record the call and yield once so overlap becomes observable."""
        self.abilities.append(ability_type)
        self._in_flight += 1
        self.max_in_flight = max(self._in_flight, self.max_in_flight)
        await asyncio.sleep(0)
        self._in_flight -= 1
        return {PARAM_STATUS: PARAM_ON}


def build_camera() -> ImouHaDevice:
    """Return an online camera with several ability-backed switches."""
    device = ImouHaDevice("dev0", "Camera", "Imou", "IPC-A1", "1.0")
    device.set_channel_id("0")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    for name, ability in (
        ("motion_detect", "AlarmMD"),
        ("header_detect", "SMDH"),
        ("light", "Linkagewhitelight"),
        ("audio_encode_control", "AudioEncodeControl"),
        ("ab_alarm_sound", "AlarmSound"),
    ):
        device.switches[name] = {PARAM_FUNCTION_TYPE: ability, PARAM_STATE: False}
    return device


@pytest.mark.asyncio
async def test_switch_reads_across_a_device_overlap() -> None:
    """Every ability-backed switch on a device is read in one concurrent batch."""
    manager = ImouHaDeviceManager(MagicMock())
    recorder = StatusRecorder()
    manager.delegate.async_get_device_status = recorder
    device = build_camera()

    await manager._async_update_device_switch_status(device)

    assert len(recorder.abilities) == 5
    assert recorder.max_in_flight == 5
    assert all(device.switches[name][PARAM_STATE] for name in device.switches)


@pytest.mark.asyncio
async def test_a_switch_backed_by_several_abilities_still_reads_them_together() -> None:
    """Fanning out over abilities keeps working inside the wider batch."""
    manager = ImouHaDeviceManager(MagicMock())
    recorder = StatusRecorder()
    manager.delegate.async_get_device_status = recorder
    device = build_camera()
    device.switches["motion_detect"][PARAM_FUNCTION_TYPE] = ["AlarmMD", "SMDH"]

    await manager._async_update_device_switch_status(device)

    assert len(recorder.abilities) == 6
    assert recorder.max_in_flight == 6


@pytest.mark.asyncio
async def test_battery_and_storage_are_read_together() -> None:
    """The two sensor reads a camera has must not queue behind each other."""
    manager = ImouHaDeviceManager(MagicMock())
    device = build_camera()
    device.sensors[PARAM_STORAGE_USED] = {PARAM_STATE: None}
    device.sensors[PARAM_BATTERY] = {PARAM_STATE: None}
    in_flight = 0
    max_in_flight = 0

    async def read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(in_flight, max_in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return {}

    manager.delegate.async_get_device_storage = read
    manager.delegate.async_get_device_power_info = read

    await manager._async_update_device_sensor_status(device)

    assert max_in_flight == 2


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
    manager._async_update_device_switch_status = boom
    manager._async_update_device_sensor_status = boom
    manager._async_update_services_entities = boom
    manager._async_update_status_shared = _noop

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
        await manager._async_gather_reads([cancelled()], device, "switches")

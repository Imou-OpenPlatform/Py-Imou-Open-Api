"""Tests for how ability-backed switch states are combined."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pyimouapi.const import PARAM_FUNCTION_TYPE, PARAM_STATE
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def build_device(
    function_type: Any, switch_type: str = "motion_detect"
) -> ImouHaDevice:
    """Return a device with one ability-backed switch, reported as on."""
    device = ImouHaDevice("dev0", "Cam", "Imou", "Cam", "1.0")
    device.switches[switch_type] = {
        PARAM_FUNCTION_TYPE: function_type,
        PARAM_STATE: True,
    }
    return device


@pytest.mark.asyncio
async def test_a_failed_read_does_not_report_the_switch_as_on() -> None:
    """A read that raises must not be mistaken for an "on" reading.

    Gathered exceptions come back as objects, and every object is truthy, so
    combining them without a check would show a switch the user never enabled.
    """
    manager = ImouHaDeviceManager(MagicMock())
    device = build_device(["motionDetect", "smartTrack"])

    async def boom(_device: ImouHaDevice, _ability: str) -> bool:
        raise RuntimeError("upstream is down")

    manager._async_get_device_switch_status_by_ability = boom

    await manager._async_update_device_switch_status(device)

    assert device.switches["motion_detect"][PARAM_STATE] is False


@pytest.mark.asyncio
async def test_any_enabled_ability_turns_the_switch_on() -> None:
    """A switch backed by several abilities is on when any of them is."""
    manager = ImouHaDeviceManager(MagicMock())
    device = build_device(["motionDetect", "smartTrack"])

    async def only_second_is_on(_device: ImouHaDevice, ability: str) -> bool:
        return ability == "smartTrack"

    manager._async_get_device_switch_status_by_ability = only_second_is_on

    await manager._async_update_device_switch_status(device)

    assert device.switches["motion_detect"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_every_write_failing_surfaces_the_first_error() -> None:
    """When no ability accepted the write, the caller must hear about it."""
    manager = ImouHaDeviceManager(MagicMock())
    device = build_device(["closeCamera"], switch_type="close_camera")

    async def boom(_device: ImouHaDevice, _ability: str, _enable: bool) -> None:
        raise RuntimeError("write rejected")

    manager._async_set_device_switch_status_by_ability = boom

    with pytest.raises(RuntimeError, match="write rejected"):
        await manager.async_switch_operation(device, "close_camera", False)


@pytest.mark.asyncio
async def test_a_switch_with_no_abilities_says_so() -> None:
    """An empty ability list means no request went out, so nothing flipped.

    Two earlier readings of this were both wrong. all() is true for an empty
    sequence, so asking for the first failure raised IndexError at whoever
    pressed the switch; guarding that then fell through to recording the switch
    as flipped, a state the device was never told about.
    """
    manager = ImouHaDeviceManager(MagicMock())
    device = build_device([], switch_type="close_camera")

    with pytest.raises(RequestFailedException, match="close_camera"):
        await manager.async_switch_operation(device, "close_camera", False)

    # Still reading as it was, because the device was never asked to change.
    assert device.switches["close_camera"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_a_single_ability_is_read_as_one_call() -> None:
    """A plain string function type is treated as a one-element list."""
    manager = ImouHaDeviceManager(MagicMock())
    device = build_device("motionDetect")
    seen: list[str] = []

    async def record(_device: ImouHaDevice, ability: str) -> bool:
        seen.append(ability)
        return False

    manager._async_get_device_switch_status_by_ability = record

    await manager._async_update_device_switch_status(device)

    assert seen == ["motionDetect"]
    assert device.switches["motion_detect"][PARAM_STATE] is False

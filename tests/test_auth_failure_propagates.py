"""Tests that refused credentials reach the caller.

Reads that fail are logged and skipped so one unhappy entity cannot stop a
poll. Credentials being refused is not one entity's problem: every later call
fails the same way, and swallowing it leaves the caller showing stale values
while believing everything is fine.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import PARAM_FUNCTION_TYPE, PARAM_STATE, PARAM_STATUS
from pyimouapi.exceptions import InvalidAppIdOrSecretException, RequestFailedException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


def build_camera() -> ImouHaDevice:
    """Return an online camera with one ability-backed switch."""
    device = ImouHaDevice("dev0", "Cam", "Imou", "IPC-A1", "1.0")
    device.set_channel_id("0")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    device.switches["motion_detect"] = {
        PARAM_FUNCTION_TYPE: "AlarmMD",
        PARAM_STATE: False,
    }
    return device


@pytest.mark.asyncio
async def test_revoked_credentials_reach_the_caller() -> None:
    """A status poll must report refused credentials rather than log them."""
    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        side_effect=InvalidAppIdOrSecretException("revoked")
    )
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(InvalidAppIdOrSecretException, match="revoked"):
        await manager.async_update_device_status(build_camera())


@pytest.mark.asyncio
async def test_refused_credentials_survive_the_gather() -> None:
    """The batched reads must not turn a refusal into a logged line."""
    delegate = MagicMock()
    delegate.async_get_device_status = AsyncMock(
        side_effect=InvalidAppIdOrSecretException("revoked")
    )
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(InvalidAppIdOrSecretException):
        await manager._async_update_device_switch_status(build_camera())


@pytest.mark.asyncio
async def test_an_ordinary_read_failure_is_still_skipped() -> None:
    """Only credentials are special; a flaky read must not stop the poll."""
    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        side_effect=RequestFailedException("device busy")
    )
    manager = ImouHaDeviceManager(delegate)

    await manager.async_update_device_status(build_camera())


@pytest.mark.asyncio
async def test_a_switch_read_refusal_is_not_reported_as_off() -> None:
    """The per-ability handler must not turn a refusal into a False reading."""
    delegate = MagicMock()
    delegate.async_get_device_status = AsyncMock(
        side_effect=InvalidAppIdOrSecretException("revoked")
    )
    manager = ImouHaDeviceManager(delegate)
    device = build_camera()

    with pytest.raises(InvalidAppIdOrSecretException):
        await manager._async_get_device_switch_status_by_ability(device, "AlarmMD")


@pytest.mark.asyncio
async def test_listing_devices_still_reports_refused_credentials() -> None:
    """The slower listing path keeps surfacing a refusal as it always did."""
    delegate = MagicMock()
    delegate.async_get_devices = AsyncMock(
        side_effect=InvalidAppIdOrSecretException("revoked")
    )
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(InvalidAppIdOrSecretException):
        await manager.async_get_devices()


@pytest.mark.asyncio
async def test_a_service_read_refusal_reaches_the_caller() -> None:
    """Service-backed entities go through the same gather and behave the same."""
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock(
        side_effect=InvalidAppIdOrSecretException("revoked")
    )
    manager = ImouHaDeviceManager(delegate)
    device = ImouHaDevice("dev0", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("prod-1")
    device.sensors["power"] = {
        "ref": "28600",
        "ref_type": "services",
        PARAM_STATE: None,
    }

    with pytest.raises(InvalidAppIdOrSecretException):
        await manager._async_update_services_entities(device)


def test_every_swallowing_handler_lets_credentials_through() -> None:
    """Guard the rule itself, so a new read handler does not reintroduce this.

    Each broad handler exists to skip a failed read, and each one has to let a
    refusal past first. A new one added without that clause is the bug this
    module was written for.
    """
    import inspect
    import re

    import pyimouapi.ha_device as module

    source = inspect.getsource(module).split("\n")
    broad: list[int] = [
        n
        for n, line in enumerate(source)
        if re.match(r"^\s*except Exception as \w+:$", line)
    ]
    assert broad, "expected the module to still skip failed reads"
    unguarded = [
        n + 1
        for n in broad
        if "InvalidAppIdOrSecretException" not in source[n - 2]
        or source[n - 1].strip() != "raise"
    ]
    assert not unguarded, (
        f"lines {unguarded} swallow every exception, so a refused credential "
        "is logged as a failed read and the caller never learns to reauthenticate"
    )

"""Tests that a written text value is reflected locally.

Callers write the value and then render the device's own copy without waiting
for a poll, so a write that does not update that copy shows the old value. The
countdown timer writes back from inside its own helper rather than alongside
the other text entities, which is easy to lose track of in a refactor.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import PARAM_REF, PARAM_STATE, PARAM_VALUE_TYPE
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def build_device() -> ImouHaDevice:
    """Return a device with a countdown timer and an ordinary threshold."""
    device = ImouHaDevice("dev0", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("prod-1")
    device.texts["count_down_switch"] = {PARAM_REF: "28800", PARAM_STATE: "5"}
    device.texts["alarm_threshold"] = {
        PARAM_REF: "28900",
        PARAM_VALUE_TYPE: "int",
        PARAM_STATE: "10",
    }
    device.switches["switch"] = {PARAM_REF: "28601", PARAM_STATE: False}
    return device


def build_manager() -> tuple[ImouHaDeviceManager, MagicMock]:
    """Return a manager whose delegate accepts every call."""
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock(return_value=None)
    delegate.async_get_iot_device_properties = AsyncMock(
        return_value={"properties": {"28601": 0}}
    )
    delegate.async_iot_device_control = AsyncMock(return_value=None)
    return ImouHaDeviceManager(delegate), delegate


@pytest.mark.asyncio
async def test_a_countdown_write_updates_the_local_value() -> None:
    """Its write-back lives in a separate helper, so pin it from the outside."""
    manager, _ = build_manager()
    device = build_device()

    await manager.async_set_text_value(device, "count_down_switch", "30")

    assert device.texts["count_down_switch"][PARAM_STATE] == "30"


@pytest.mark.asyncio
async def test_an_ordinary_text_write_still_updates_the_local_value() -> None:
    """The behaviour the other text entities already had must not change."""
    manager, _ = build_manager()
    device = build_device()

    await manager.async_set_text_value(device, "alarm_threshold", "42")

    assert device.texts["alarm_threshold"][PARAM_STATE] == "42"


@pytest.mark.asyncio
async def test_a_failed_countdown_write_leaves_the_old_value() -> None:
    """Nothing reached the device, so the entity must keep showing the old value."""
    manager, delegate = build_manager()
    delegate.async_iot_device_control = AsyncMock(side_effect=OSError("nope"))
    device = build_device()

    with pytest.raises(OSError, match="nope"):
        await manager.async_set_text_value(device, "count_down_switch", "30")

    assert device.texts["count_down_switch"][PARAM_STATE] == "5"


@pytest.mark.asyncio
async def test_the_countdown_is_sent_to_the_device_in_seconds() -> None:
    """The value is shown in minutes but the device is told seconds."""
    manager, delegate = build_manager()
    device = build_device()

    await manager.async_set_text_value(device, "count_down_switch", "30")

    sent = delegate.async_iot_device_control.await_args.args[3]
    assert sent["28602"] == 30 * 60

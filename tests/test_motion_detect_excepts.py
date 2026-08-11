"""Tests for motion_detect IoT ref excepts (abilityRefs lie)."""

from __future__ import annotations

from pyimouapi.const import PARAM_MOTION_DETECT, PARAM_REF
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

EXCEPT_PID = "FKX9UYL4"
REF_14800 = "14800"
REF_108800 = "108800"


def _ha_device(*, product_id: str) -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    device.set_product_id(product_id)
    return device


def test_motion_detect_skips_14800_for_excepted_product_id() -> None:
    """FKX9UYL4 advertises 14800+108800 but must bind 108800."""
    device = _ha_device(product_id=EXCEPT_PID)
    ImouHaDeviceManager.configure_switch_by_ref(
        channel_ability_refs=[REF_14800, REF_108800],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert PARAM_MOTION_DETECT in device.switches
    assert device.switches[PARAM_MOTION_DETECT][PARAM_REF] == REF_108800


def test_motion_detect_still_binds_14800_for_other_product_ids() -> None:
    device = _ha_device(product_id="OTHERPID1")
    ImouHaDeviceManager.configure_switch_by_ref(
        channel_ability_refs=[REF_14800, REF_108800],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.switches[PARAM_MOTION_DETECT][PARAM_REF] == REF_14800


def test_motion_detect_excepted_pid_with_only_14800_has_no_switch() -> None:
    device = _ha_device(product_id=EXCEPT_PID)
    ImouHaDeviceManager.configure_switch_by_ref(
        channel_ability_refs=[REF_14800],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert PARAM_MOTION_DETECT not in device.switches

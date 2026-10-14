"""PaaS PIR detection switch from AlarmPIR ability generations."""

from pyimouapi.const import PARAM_FUNCTION_TYPE, PARAM_STATE
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

ALARM_PIR_ABILITIES = ("AlarmPIRV2", "AlarmPIRV3")
LEGACY_ALARM_PIR_ABILITIES = ("AlarmPIR", "AlarmPIRV4")


def _device() -> ImouHaDevice:
    device = ImouHaDevice("dev-1", "Cam", "Imou", "IPC-K42", "1.0")
    device.set_product_id("product-not-in-any-excepts")
    return device


def test_each_alarm_pir_ability_registers_alarm_pir_switch() -> None:
    """Every PIR ability generation writes the same alarmPIR switch."""
    for ability in ALARM_PIR_ABILITIES:
        device = _device()
        ImouHaDeviceManager.configure_switch_by_ability([ability], False, [], device)
        assert device.switches["alarm_pir"][PARAM_FUNCTION_TYPE] == "alarmPIR"
        assert device.switches["alarm_pir"][PARAM_STATE] is False


def test_legacy_alarm_pir_abilities_do_not_register_switch() -> None:
    """Older PIR ability names are ignored until mapped explicitly."""
    for ability in LEGACY_ALARM_PIR_ABILITIES:
        device = _device()
        ImouHaDeviceManager.configure_switch_by_ability([ability], False, [], device)
        assert "alarm_pir" not in device.switches


def test_device_without_alarm_pir_ability_has_no_switch() -> None:
    """Picture-change ability must not invent a PIR switch."""
    device = _device()
    ImouHaDeviceManager.configure_switch_by_ability(["AlarmMD"], False, [], device)
    assert "alarm_pir" not in device.switches

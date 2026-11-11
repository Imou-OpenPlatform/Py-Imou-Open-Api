"""V2 capability list ∩ map entity registration."""

from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability
from pyimouapi.capability.setup import configure_imou_ha_device_from_capability
from pyimouapi.const import (
    PARAM_COLLECTION_POINT,
    PARAM_RESTART_DEVICE,
    PARAM_STATE,
    PARAM_V2_LIST_SERVICE_ID,
    PARAM_V2_TARGET_ID,
    PARAM_V2_WRITE_TARGET_ID,
)
from pyimouapi.ha_device import ImouHaDevice


def _motion_cap() -> CapabilitySet:
    return CapabilitySet(
        properties={
            "detection.motion.enabled": PropertyCapability(
                property_id="detection.motion.enabled",
                access_mode="rw",
                data_type="int",
                range_min=0,
                range_max=1,
                default_data=0,
            ),
            "image.wdr.mode": PropertyCapability(
                property_id="image.wdr.mode",
                access_mode="rw",
                data_type="enum",
                enum_options=(),
            ),
        },
        services=frozenset({"ptz.aim.step"}),
        events=frozenset({"detection.motion.detected"}),
        device_id="IPC1",
        channel_id="0",
    )


def test_v2_gate_registers_motion_switch() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("pid")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    configure_imou_ha_device_from_capability(device, _motion_cap())
    assert "motion_detect" in device.switches
    assert device.switches["motion_detect"][PARAM_V2_TARGET_ID] == (
        "detection.motion.enabled"
    )
    assert device.switches["motion_detect"][PARAM_STATE] is False


def test_v2_gate_registers_wide_dynamic_select() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = CapabilitySet(
        properties={
            "image.wdr.mode": PropertyCapability(
                property_id="image.wdr.mode",
                access_mode="rw",
                data_type="enum",
                enum_options=(),
                default_data=0,
            ),
        },
        services=frozenset(),
        events=frozenset(),
    )
    configure_imou_ha_device_from_capability(device, cap)
    assert "wide_dynamic" in device.selects
    assert device.selects["wide_dynamic"][PARAM_V2_TARGET_ID] == "image.wdr.mode"


def test_v2_gate_registers_outlet_countdown() -> None:
    device = ImouHaDevice("PLUG1", "Plug", "Imou", "SP", "1.0")
    device.set_product_id("pid")
    cap = CapabilitySet(
        properties={},
        services=frozenset(
            {"control.outlet.countdownGet", "control.outlet.countdownSet"}
        ),
        events=frozenset(),
    )
    configure_imou_ha_device_from_capability(device, cap)
    assert "count_down_switch" in device.texts
    meta = device.texts["count_down_switch"]
    assert meta[PARAM_V2_TARGET_ID] == "control.outlet.countdownGet"
    assert meta[PARAM_V2_WRITE_TARGET_ID] == "control.outlet.countdownSet"


def test_v2_gate_registers_collection_point_when_list_present() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = CapabilitySet(
        properties={},
        services=frozenset({"ptz.preset.goto", "ptz.preset.list"}),
        events=frozenset(),
    )
    configure_imou_ha_device_from_capability(device, cap)
    assert PARAM_COLLECTION_POINT in device.selects
    assert device.selects[PARAM_COLLECTION_POINT][PARAM_V2_TARGET_ID] == (
        "ptz.preset.goto"
    )
    assert device.selects[PARAM_COLLECTION_POINT][PARAM_V2_LIST_SERVICE_ID] == (
        "ptz.preset.list"
    )


def test_v2_gate_registers_restart_when_named_api_row() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = CapabilitySet(properties={}, services=frozenset(), events=frozenset())
    configure_imou_ha_device_from_capability(device, cap)
    assert PARAM_RESTART_DEVICE in device.buttons
    assert device.buttons[PARAM_RESTART_DEVICE][PARAM_V2_TARGET_ID] == (
        "device.reboot.execute"
    )


def test_v2_gate_skips_missing_targets() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    empty = CapabilitySet(properties={}, services=frozenset(), events=frozenset())
    configure_imou_ha_device_from_capability(device, empty)
    assert "motion_detect" not in device.switches

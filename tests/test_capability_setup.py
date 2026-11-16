"""V2 capability list ∩ map entity registration."""

import pytest
from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability
from pyimouapi.capability.setup import configure_imou_ha_device_from_capability
from pyimouapi.const import (
    PARAM_BATTERY,
    PARAM_COLLECTION_POINT,
    PARAM_RESTART_DEVICE,
    PARAM_STATE,
    PARAM_V2_FALLBACK_TARGET_ID,
    PARAM_V2_LIST_SERVICE_ID,
    PARAM_V2_SOURCE_TARGET_IDS,
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


def test_v2_wide_dynamic_enum_uses_friendly_option_keys() -> None:
    from pyimouapi.capability.catalog import EnumOption, PropertyCapability
    from pyimouapi.const import (
        PARAM_CURRENT_OPTION,
        PARAM_OPTIONS,
        PARAM_V2_RAW_BY_OPTION,
    )

    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = CapabilitySet(
        properties={
            "image.wdr.mode": PropertyCapability(
                property_id="image.wdr.mode",
                access_mode="rw",
                data_type="enum",
                enum_options=(
                    EnumOption(0, "Off"),
                    EnumOption(1, "On"),
                    EnumOption(2, "Adaptive"),
                ),
                default_data=2,
            ),
        },
        services=frozenset(),
        events=frozenset(),
    )
    configure_imou_ha_device_from_capability(device, cap)
    wdr = device.selects["wide_dynamic"]
    assert wdr[PARAM_OPTIONS] == ["off", "on", "adaptive"]
    assert wdr[PARAM_CURRENT_OPTION] == "adaptive"
    assert wdr[PARAM_V2_RAW_BY_OPTION]["adaptive"] == 2


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


def test_v2_gate_registers_overcharge_as_switch_only() -> None:
    device = ImouHaDevice("PLUG1", "Plug", "Imou", "SP", "1.0")
    device.set_product_id("pid")
    cap = CapabilitySet(
        properties={
            "control.outlet.overchargeProtection": PropertyCapability(
                property_id="control.outlet.overchargeProtection",
                access_mode="rw",
                data_type="int",
            ),
        },
        services=frozenset(),
        events=frozenset(),
    )

    configure_imou_ha_device_from_capability(device, cap)

    assert "overcharge_switch" in device.switches
    assert "overcharge_switch" not in device.texts


@pytest.mark.parametrize(
    "source_ids",
    [
        ("power.battery.level",),
        ("power.battery.info",),
        ("power.battery.level", "power.battery.info"),
    ],
)
def test_v2_battery_records_available_sources_on_one_entity(
    source_ids: tuple[str, ...],
) -> None:
    device = ImouHaDevice("BAT1", "Battery", "Imou", "Sensor", "1.0")
    device.set_product_id("pid")
    cap = CapabilitySet(
        properties={
            target: PropertyCapability(
                property_id=target,
                access_mode="r",
                data_type="int" if target.endswith(".level") else "array",
            )
            for target in source_ids
        },
        services=frozenset(),
        events=frozenset(),
    )

    configure_imou_ha_device_from_capability(device, cap)

    assert [key for key in device.sensors if key == PARAM_BATTERY] == [PARAM_BATTERY]
    assert device.sensors[PARAM_BATTERY][PARAM_V2_SOURCE_TARGET_IDS] == list(source_ids)


def test_v2_switch_count_records_property_fallback() -> None:
    device = ImouHaDevice("PLUG1", "Plug", "Imou", "SP", "1.0")
    device.set_product_id("pid")
    cap = CapabilitySet(
        properties={
            "control.outlet.switchCount": PropertyCapability(
                property_id="control.outlet.switchCount",
                access_mode="r",
                data_type="int",
            )
        },
        services=frozenset({"power.outlet.read"}),
        events=frozenset(),
    )

    configure_imou_ha_device_from_capability(device, cap)

    assert device.sensors["switch_cnt"][PARAM_V2_FALLBACK_TARGET_ID] == (
        "control.outlet.switchCount"
    )


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

"""V2 capability list ∩ map entity registration."""

import pytest
from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability
from pyimouapi.capability.setup import configure_imou_ha_device_from_capability
from pyimouapi.const import (
    PARAM_BATTERY,
    PARAM_COLLECTION_POINT,
    PARAM_RESTART_DEVICE,
    PARAM_STATE,
    PARAM_V2_LIST_SERVICE_ID,
    PARAM_V2_OUTPUT_FIELD,
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


def _copy_ids_from_capability(device: ImouHaDevice, cap: CapabilitySet) -> None:
    device.set_capability_ids(set(cap.properties) | set(cap.services) | set(cap.events))


def test_v2_gate_registers_intrusion_switches() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    properties = {
        property_id: PropertyCapability(
            property_id=property_id,
            access_mode="rw",
            data_type="int",
            range_min=0,
            range_max=1,
            default_data=0,
        )
        for property_id in (
            "detection.intrusion.enabled",
            "detection.intrusion.personFilter",
            "detection.intrusion.petFilter",
        )
    }
    cap = CapabilitySet(properties=properties, services=frozenset(), events=frozenset())
    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)
    assert set(device.switches) == {
        "motion_detect",
        "header_detect",
        "pet_detect",
    }
    assert device.switches["motion_detect"][PARAM_V2_TARGET_ID] == (
        "detection.intrusion.enabled"
    )
    assert device.switches["header_detect"][PARAM_V2_TARGET_ID] == (
        "detection.intrusion.personFilter"
    )
    assert device.switches["pet_detect"][PARAM_V2_TARGET_ID] == (
        "detection.intrusion.petFilter"
    )


def test_dedicated_detection_property_wins_over_intrusion() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    properties = {
        property_id: PropertyCapability(
            property_id=property_id,
            access_mode="rw",
            data_type="int",
            range_min=0,
            range_max=1,
            default_data=0,
        )
        for property_id in (
            "detection.motion.enabled",
            "detection.intrusion.enabled",
        )
    }
    cap = CapabilitySet(properties=properties, services=frozenset(), events=frozenset())
    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)
    assert device.switches["motion_detect"][PARAM_V2_TARGET_ID] == (
        "detection.motion.enabled"
    )


def test_v2_gate_registers_motion_switch() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("pid")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = _motion_cap()
    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)
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
    _copy_ids_from_capability(device, cap)
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
    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)
    wdr = device.selects["wide_dynamic"]
    assert wdr[PARAM_OPTIONS] == ["off", "on", "adaptive"]
    assert wdr[PARAM_CURRENT_OPTION] == "adaptive"
    assert wdr[PARAM_V2_RAW_BY_OPTION]["adaptive"] == 2


def test_v2_numeric_volume_keeps_level_numbers() -> None:
    """A 1-5 level must not turn 1 and 2 into Medium and High."""
    from pyimouapi.capability.catalog import EnumOption
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
            "audio.volume.level": PropertyCapability(
                property_id="audio.volume.level",
                access_mode="rw",
                data_type="enum",
                enum_options=tuple(
                    EnumOption(str(level), str(level)) for level in range(1, 6)
                ),
                default_data="3",
            ),
        },
        services=frozenset(),
        events=frozenset(),
    )
    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)
    volume = device.selects["device_volume"]
    assert volume[PARAM_OPTIONS] == ["1", "2", "3", "4", "5"]
    assert volume[PARAM_CURRENT_OPTION] == "3"
    assert volume[PARAM_V2_RAW_BY_OPTION]["3"] == "3"


def test_v2_named_volume_keeps_mute_low_medium_high() -> None:
    from pyimouapi.capability.catalog import EnumOption
    from pyimouapi.const import PARAM_OPTIONS

    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = CapabilitySet(
        properties={
            "audio.volume.level": PropertyCapability(
                property_id="audio.volume.level",
                access_mode="rw",
                data_type="enum",
                enum_options=(
                    EnumOption("99", "Mute"),
                    EnumOption("0", "Low"),
                    EnumOption("1", "Medium"),
                    EnumOption("2", "High"),
                ),
                default_data="1",
            ),
        },
        services=frozenset(),
        events=frozenset(),
    )
    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)
    assert device.selects["device_volume"][PARAM_OPTIONS] == [
        "mute",
        "low",
        "medium",
        "high",
    ]


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
    _copy_ids_from_capability(device, cap)
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

    _copy_ids_from_capability(device, cap)
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

    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)

    assert [key for key in device.sensors if key == PARAM_BATTERY] == [PARAM_BATTERY]
    assert device.sensors[PARAM_BATTERY][PARAM_V2_SOURCE_TARGET_IDS] == list(source_ids)


def test_v2_switch_count_reads_outlet_service_switch_cnt() -> None:
    device = ImouHaDevice("PLUG1", "Plug", "Imou", "SP", "1.0")
    device.set_product_id("pid")
    cap = CapabilitySet(
        properties={},
        services=frozenset({"power.outlet.read"}),
        events=frozenset(),
    )

    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)

    sensor = device.sensors["switch_cnt"]
    assert sensor[PARAM_V2_TARGET_ID] == "power.outlet.read"
    assert sensor[PARAM_V2_OUTPUT_FIELD] == "switchCnt"


def test_v2_alarm_pir_uses_detection_pir_enabled() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = CapabilitySet(
        properties={
            "detection.pir.enabled": PropertyCapability(
                property_id="detection.pir.enabled",
                access_mode="rw",
                data_type="int",
                range_min=0,
                range_max=1,
                default_data=0,
            )
        },
        services=frozenset(),
        events=frozenset(),
    )

    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)

    assert device.switches["alarm_pir"][PARAM_V2_TARGET_ID] == "detection.pir.enabled"


def test_v2_gate_registers_collection_point_when_list_present() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    cap = CapabilitySet(
        properties={},
        services=frozenset({"ptz.preset.goto", "ptz.preset.list"}),
        events=frozenset(),
    )
    _copy_ids_from_capability(device, cap)
    configure_imou_ha_device_from_capability(device, cap)
    assert PARAM_COLLECTION_POINT in device.selects
    assert device.selects[PARAM_COLLECTION_POINT][PARAM_V2_TARGET_ID] == (
        "ptz.preset.goto"
    )
    assert device.selects[PARAM_COLLECTION_POINT][PARAM_V2_LIST_SERVICE_ID] == (
        "ptz.preset.list"
    )


def test_restart_registers_only_when_reboot_id_is_present() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    device.set_capability_ids({"device.reboot.execute"})
    configure_imou_ha_device_from_capability(
        device,
        CapabilitySet(properties={}, services=frozenset(), events=frozenset()),
    )
    assert PARAM_RESTART_DEVICE in device.buttons
    assert device.buttons[PARAM_RESTART_DEVICE][PARAM_V2_TARGET_ID] == (
        "device.reboot.execute"
    )

    bare = ImouHaDevice("IPC2", "Cam", "Imou", "IPC", "1.0")
    bare.set_channel_id("0")
    bare.set_is_ipc(True)
    bare.set_capability_ids(frozenset())
    configure_imou_ha_device_from_capability(
        bare,
        CapabilitySet(properties={}, services=frozenset(), events=frozenset()),
    )
    assert PARAM_RESTART_DEVICE not in bare.buttons


def test_page_id_registers_without_capability_detail() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    device.set_capability_ids({"detection.motion.enabled"})
    configure_imou_ha_device_from_capability(
        device,
        CapabilitySet(properties={}, services=frozenset(), events=frozenset()),
    )
    assert device.switches["motion_detect"][PARAM_V2_TARGET_ID] == (
        "detection.motion.enabled"
    )
    assert device.switches["motion_detect"][PARAM_STATE] is False


def test_capability_detail_does_not_add_entities() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    device.set_capability_ids(frozenset())
    configure_imou_ha_device_from_capability(device, _motion_cap())
    assert "motion_detect" not in device.switches
    assert PARAM_RESTART_DEVICE not in device.buttons


def test_v2_gate_skips_missing_targets() -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(True)
    empty = CapabilitySet(properties={}, services=frozenset(), events=frozenset())
    configure_imou_ha_device_from_capability(device, empty)
    assert "motion_detect" not in device.switches

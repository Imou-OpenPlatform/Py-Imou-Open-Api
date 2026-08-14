"""Discovery of pet / flip / WDR / smart-track switches from the entity tables."""

from pyimouapi.const import (
    PARAM_FUNCTION_TYPE,
    PARAM_REF,
    PARAM_STATE,
    SWITCH_TYPE_ABILITY,
    SWITCH_TYPE_REF,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

IOT_REFS = {
    "pet_detect": "18300",
    "frame_reverse": "13500",
    "wide_dynamic": "19400",
    "smart_track": "13300",
    "play_sound": "14000",
}

PAAS_ABILITIES = {
    "frame_reverse": ("FrameReverse", "frameReverse"),
    "wide_dynamic": ("WideDynamic", "wideDynamic"),
    "smart_track": ("SmartTrack", "smartTrack"),
    "play_sound": ("PlaySound", "playSound"),
}


def _device() -> ImouHaDevice:
    device = ImouHaDevice("dev-1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("product-not-in-any-excepts")
    return device


def test_iot_refs_register_the_feature_switches() -> None:
    device = _device()
    ImouHaDeviceManager.configure_switch_by_ref(
        list(IOT_REFS.values()),
        False,
        [],
        device,
    )
    for switch_type, ref in IOT_REFS.items():
        assert device.switches[switch_type][PARAM_REF] == ref
        assert device.switches[switch_type][PARAM_STATE] is False


def test_paas_abilities_register_feature_switches_without_pet_detect() -> None:
    device = _device()
    ImouHaDeviceManager.configure_switch_by_ability(
        [ability for ability, _ in PAAS_ABILITIES.values()],
        False,
        [],
        device,
    )
    assert "pet_detect" not in device.switches
    assert "pet_detect" not in SWITCH_TYPE_ABILITY
    for switch_type, (ability, function_type) in PAAS_ABILITIES.items():
        assert device.switches[switch_type][PARAM_FUNCTION_TYPE] == function_type
        assert device.switches[switch_type][PARAM_STATE] is False
        assert any(
            entry["ability"] == ability for entry in SWITCH_TYPE_ABILITY[switch_type]
        )


def test_feature_switch_iot_refs_have_no_excepts() -> None:
    for switch_type, ref in IOT_REFS.items():
        [entry] = SWITCH_TYPE_REF[switch_type]
        assert entry == {"ref": ref, "default": False}

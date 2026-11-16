"""Bulb registration follows product identity and the supported property subset."""

from __future__ import annotations

from pyimouapi.bulb_light import BULB_V2_PROPERTY_IDS
from pyimouapi.capability.binding import (
    TargetBinding,
    binding_supported,
    bulb_gate_satisfied,
)
from pyimouapi.capability.catalog import CapabilitySet
from pyimouapi.capability.setup import configure_imou_ha_device_from_capability
from pyimouapi.ha_device import ImouHaDevice


def _bulb_binding() -> TargetBinding:
    return TargetBinding(
        ha_key="bulb",
        kind="composite",
        ha_platform="light",
        scope="device",
        gate_property="light.white.mode",
        properties=(
            "control.outlet.enabled",
            "light.white.mode",
            "light.white.level",
            "light.white.colorTemperature",
            "light.white.hue",
            "light.white.saturation",
            "light.white.colorLevel",
            "light.white.scene",
        ),
    )


def test_lamp_with_partial_color_properties_registers_bulb() -> None:
    properties = {"control.outlet.enabled", "light.white.mode", "light.white.level"}
    assert bulb_gate_satisfied("Lamp", properties) is True


def test_lamp_product_type_is_case_insensitive() -> None:
    assert bulb_gate_satisfied("lAmP", {"control.outlet.enabled"}) is True


def test_ipc_with_light_properties_is_not_a_bulb() -> None:
    assert bulb_gate_satisfied("IPC", set(BULB_V2_PROPERTY_IDS)) is False


def test_lamp_without_power_property_is_not_controllable() -> None:
    assert bulb_gate_satisfied("Lamp", {"light.white.mode"}) is False


def test_binding_supports_partial_lamp_property_subset() -> None:
    binding = _bulb_binding()
    props = {"control.outlet.enabled", "light.white.mode"}
    assert binding_supported(binding, props, set(), set(), device_type="Lamp")


def test_configure_registers_bulb_for_lamp_with_partial_properties() -> None:
    cap = CapabilitySet(
        properties=dict.fromkeys(("control.outlet.enabled", "light.white.mode")),  # type: ignore[arg-type]
        services=frozenset(),
        events=frozenset(),
    )
    device = ImouHaDevice("LAMP1", "Lamp", "Imou", "M", "1")
    device.set_product_device_type("Lamp")
    configure_imou_ha_device_from_capability(device, cap, bindings=(_bulb_binding(),))
    assert device.bulb_light is not None
    assert device.bulb_v2 is True


def test_configure_skips_bulb_for_ipc_with_all_light_properties() -> None:
    cap = CapabilitySet(
        properties=dict.fromkeys(BULB_V2_PROPERTY_IDS),  # type: ignore[arg-type]
        services=frozenset(),
        events=frozenset(),
    )
    device = ImouHaDevice("CAM1", "Cam", "Imou", "M", "1")
    device.set_product_device_type("IPC")
    configure_imou_ha_device_from_capability(device, cap, bindings=(_bulb_binding(),))
    assert device.bulb_light is None

"""Bulb composite registration must not follow a lone gate property on cameras."""

from __future__ import annotations

from pyimouapi.capability.binding import TargetBinding, binding_supported
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


def test_bulb_not_supported_when_only_gate_in_list() -> None:
    binding = _bulb_binding()
    props = {"light.white.mode"}
    assert not binding_supported(binding, props, set(), set())


def test_bulb_supported_when_all_composite_properties_listed() -> None:
    binding = _bulb_binding()
    props = set(binding.properties)
    assert binding_supported(binding, props, set(), set())


def test_configure_skips_bulb_for_ipc_with_partial_light_props() -> None:
    cap = CapabilitySet(
        properties=dict.fromkeys(("light.white.mode", "detection.motion.enabled")),  # type: ignore[arg-type]
        services=frozenset(),
        events=frozenset(),
    )
    device = ImouHaDevice("CAM1", "Cam", "Imou", "M", "1")
    device.set_is_ipc(True)
    device.set_channel_id("0")
    configure_imou_ha_device_from_capability(device, cap, bindings=(_bulb_binding(),))
    assert device.bulb_light is None

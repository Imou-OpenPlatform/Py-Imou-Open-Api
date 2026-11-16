"""V2 color bulb property batch read/write."""

from unittest.mock import AsyncMock, patch

import pytest
from pyimouapi.bulb_light import (
    REF_BRIGHTNESS,
    REF_SWITCH,
    apply_bulb_v2_properties,
    bulb_v2_property_ids_for_device,
    empty_bulb_state,
    properties_for_turn_off,
    ref_payload_to_v2,
)
from pyimouapi.capability.catalog import CapabilitySet
from pyimouapi.device import ImouDevice, ImouDeviceManager
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient


def test_ref_payload_to_v2_maps_switch() -> None:
    payload = ref_payload_to_v2({REF_SWITCH: 1})
    assert payload == {"control.outlet.enabled": 1}


def test_apply_bulb_v2_properties_reads_switch() -> None:
    state = empty_bulb_state()
    apply_bulb_v2_properties(
        state, {"control.outlet.enabled": 1, "light.white.mode": 0}
    )
    assert state["on"] is True


def test_bulb_property_read_subset_only_contains_supported_properties() -> None:
    supported = {"control.outlet.enabled", "light.white.level"}
    assert bulb_v2_property_ids_for_device(supported) == (
        "control.outlet.enabled",
        "light.white.level",
    )


@pytest.fixture
def ha_manager() -> ImouHaDeviceManager:
    client = ImouOpenApiClient("app", "secret", "api.example.com")
    return ImouHaDeviceManager(ImouDeviceManager(client))


@pytest.mark.asyncio
async def test_set_bulb_light_v2_property_set(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = ImouHaDevice("B1", "Bulb", "Imou", "L1", "1.0")
    device.set_product_id("pid")
    device.set_capability_set(
        CapabilitySet(
            properties=dict.fromkeys(("control.outlet.enabled",)),  # type: ignore[arg-type]
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.bulb_light = empty_bulb_state()
    device.set_bulb_v2(True)
    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager.async_set_bulb_light(device, properties_for_turn_off())
    mock_set.assert_awaited_once()
    assert mock_set.await_args.kwargs["properties"]["control.outlet.enabled"] == 0
    assert device.bulb_light["on"] is False


@pytest.mark.asyncio
async def test_set_bulb_light_v2_omits_unsupported_optional_properties(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = ImouHaDevice("B1", "Bulb", "Imou", "L1", "1.0")
    device.set_product_id("pid")
    device.set_capability_set(
        CapabilitySet(
            properties=dict.fromkeys(("control.outlet.enabled",)),  # type: ignore[arg-type]
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.bulb_light = empty_bulb_state()
    device.set_bulb_v2(True)
    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager.async_set_bulb_light(
            device, {REF_SWITCH: 1, REF_BRIGHTNESS: 75}
        )
    assert mock_set.await_args.kwargs["properties"] == {"control.outlet.enabled": 1}
    assert device.bulb_light["brightness"] == 50


def test_build_device_copies_product_device_type() -> None:
    source = ImouDevice("B1", "Bulb", "Online", "Imou", "L1")
    source.set_product_device_type("Lamp")
    device = ImouHaDeviceManager.build_device(source)
    assert device.product_device_type == "Lamp"

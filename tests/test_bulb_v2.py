"""V2 color bulb property batch read/write."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.bulb_light import (
    apply_bulb_v2_properties,
    bulb_v2_property_ids_for_device,
    empty_bulb_state,
    properties_for_turn_off,
)
from pyimouapi.capability.catalog import CapabilitySet
from pyimouapi.device import ImouDevice, ImouDeviceManager
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient


def test_apply_bulb_v2_properties_reads_switch() -> None:
    state = empty_bulb_state()
    changed = apply_bulb_v2_properties(
        state, {"control.outlet.enabled": 1, "light.white.mode": 0}
    )
    assert changed is True
    assert state["on"] is True


def test_apply_property_values_rejects_malformed_v2_bulb_values() -> None:
    manager = ImouHaDeviceManager(ImouDeviceManager(MagicMock()))
    device = ImouHaDevice("B1", "Bulb", "Imou", "L1", "1.0")
    device.set_capability_set(
        CapabilitySet(
            properties=dict.fromkeys(
                (
                    "control.outlet.enabled",
                    "light.white.level",
                    "light.white.hue",
                )
            ),  # type: ignore[arg-type]
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.bulb_light = empty_bulb_state()
    device.set_bulb_v2(True)
    before = dict(device.bulb_light)

    changed = manager.apply_property_values(
        device,
        {
            "control.outlet.enabled": {},
            "light.white.level": [],
            "light.white.hue": "invalid",
        },
    )

    assert changed is False
    assert device.bulb_light == before


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
            device,
            {"control.outlet.enabled": 1, "light.white.level": 75},
        )
    assert mock_set.await_args.kwargs["properties"] == {"control.outlet.enabled": 1}
    assert device.bulb_light["brightness"] == 50


def test_build_device_copies_product_device_type() -> None:
    source = ImouDevice("B1", "Bulb", "Online", "Imou", "L1")
    source.set_product_device_type("Lamp")
    device = ImouHaDeviceManager.build_device(source)
    assert device.product_device_type == "Lamp"


def test_replace_capabilities_syncs_complete_v2_snapshot() -> None:
    current = ImouHaDevice("B1", "Bulb", "Imou", "L1", "1.0")
    fresh = ImouHaDevice("B1", "Bulb", "Imou", "L1", "1.0")
    capability = CapabilitySet(
        properties=dict.fromkeys(("control.outlet.enabled",)),  # type: ignore[arg-type]
        services=frozenset(),
        events=frozenset(),
    )
    fresh.set_product_device_type("Lamp")
    fresh.set_capability_ids({"control.outlet.enabled"})
    fresh.set_capability_set(capability)
    fresh.bulb_light = empty_bulb_state()
    fresh.set_bulb_v2(True)

    assert current.capability_snapshot == (None, None, None)

    current.replace_capabilities(fresh)

    assert current.capability_snapshot == (
        "Lamp",
        frozenset({"control.outlet.enabled"}),
        capability,
    )
    assert current.bulb_light == fresh.bulb_light
    assert current.bulb_v2 is True


@pytest.mark.asyncio
async def test_bulb_light_works_with_page_capability_ids_without_detail(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = ImouHaDevice("B1", "Bulb", "Imou", "L1", "1.0")
    device.set_product_id("pid")
    device.set_capability_ids({"control.outlet.enabled", "light.white.level"})
    device.bulb_light = empty_bulb_state()
    device.set_bulb_v2(True)

    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager.async_set_bulb_light(
            device, {"control.outlet.enabled": 1, "light.white.level": 80}
        )
    assert mock_set.await_count == 2
    assert device.bulb_light["on"] is True
    assert device.bulb_light["brightness"] == 80

    with patch(
        "pyimouapi.ha_device.async_property_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {"control.outlet.enabled": 0, "light.white.level": 35}
        assert await ha_manager._async_update_v2_bulb_state(device) is True
    assert device.bulb_light["on"] is False
    assert device.bulb_light["brightness"] == 35

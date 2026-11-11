"""V2 color bulb property batch read/write."""

from unittest.mock import AsyncMock, patch

import pytest
from pyimouapi.bulb_light import (
    REF_SWITCH,
    apply_bulb_v2_properties,
    empty_bulb_state,
    properties_for_turn_off,
    ref_payload_to_v2,
)
from pyimouapi.device import ImouDeviceManager
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
    device.bulb_light = empty_bulb_state()
    device.set_bulb_v2(True)
    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager.async_set_bulb_light(device, properties_for_turn_off())
    mock_set.assert_awaited_once()
    assert mock_set.await_args.kwargs["properties"]["control.outlet.enabled"] == 0
    assert device.bulb_light["on"] is False

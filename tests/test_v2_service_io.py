"""V2 service.invoke for buttons and outlet read sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from pyimouapi.capability.v2_invoke import v2_service_input_data
from pyimouapi.const import PARAM_STATE, PARAM_V2_OUTPUT_FIELD, PARAM_V2_TARGET_ID
from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient


def test_v2_ptz_step_operator_mapping() -> None:
    data = v2_service_input_data("ptz.aim.step", "ptz_up", 500)
    assert data == {"operator": "3", "zoom": "1"}


@pytest.fixture
def ha_manager() -> ImouHaDeviceManager:
    client = ImouOpenApiClient("app", "secret", "api.example.com")
    return ImouHaDeviceManager(ImouDeviceManager(client))


@pytest.mark.asyncio
async def test_press_button_invokes_v2_service(ha_manager: ImouHaDeviceManager) -> None:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("pid")
    device.set_channel_id("0")
    device.buttons["ptz_up"] = {PARAM_V2_TARGET_ID: "ptz.aim.step"}
    with patch(
        "pyimouapi.ha_device.async_service_invoke", new_callable=AsyncMock
    ) as mock_invoke:
        await ha_manager.async_press_button(device, "ptz_up", 400)
    mock_invoke.assert_awaited_once()
    assert mock_invoke.await_args.kwargs["service_id"] == "ptz.aim.step"
    assert mock_invoke.await_args.kwargs["input_data"]["operator"] == "3"


@pytest.mark.asyncio
async def test_service_sensor_poll_splits_output_fields(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = ImouHaDevice("PLUG1", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("pid")
    device.sensors["power"] = {
        PARAM_V2_TARGET_ID: "power.outlet.read",
        PARAM_V2_OUTPUT_FIELD: "power",
    }
    device.sensors["voltage"] = {
        PARAM_V2_TARGET_ID: "power.outlet.read",
        PARAM_V2_OUTPUT_FIELD: "voltage",
    }
    with patch(
        "pyimouapi.ha_device.async_service_invoke", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = {
            "outputData": {"power": 1200, "voltage": 230},
        }
        await ha_manager._async_update_v2_service_entities(device)
    assert mock_invoke.await_count == 1
    assert device.sensors["power"][PARAM_STATE] == 1200
    assert device.sensors["voltage"][PARAM_STATE] == 230

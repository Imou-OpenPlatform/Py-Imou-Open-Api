"""Tests for siren start/stop button support."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.const import (
    IOT_SIREN_START_INPUT_REF,
    IOT_SIREN_START_REF,
    IOT_SIREN_STOP_REF,
    PARAM_INPUT_REF,
    PARAM_REF,
    PARAM_SIREN_START,
    PARAM_SIREN_STOP,
)
from pyimouapi.device import ImouDeviceManager
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.siren import build_siren_start_iot_content, client_local_time_iso


def _ha_device(*, product_id: str = "prod1", is_ipc: bool = False) -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Front Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_is_ipc(is_ipc)
    device.set_product_id(product_id)
    return device


def test_client_local_time_iso() -> None:
    with patch("pyimouapi.siren.datetime") as mock_dt:
        aware = datetime(2026, 7, 31, 15, 8, tzinfo=UTC)
        now_mock = MagicMock()
        now_mock.astimezone.return_value = aware
        mock_dt.now.return_value = now_mock
        assert client_local_time_iso() == "20260731T150800"


def test_build_siren_start_iot_content() -> None:
    with patch(
        "pyimouapi.siren.client_local_time_iso",
        return_value="20260731T150800",
    ):
        assert build_siren_start_iot_content(IOT_SIREN_START_INPUT_REF) == {
            IOT_SIREN_START_INPUT_REF: "20260731T150800",
        }


def test_configure_siren_buttons_by_ability() -> None:
    """Siren ability registers start/stop without ref."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ability(
        channel_abilities=["Siren"],
        is_ipc=True,
        device_abilities=[],
        imou_ha_device=device,
    )
    assert PARAM_SIREN_START in device.buttons
    assert PARAM_SIREN_STOP in device.buttons
    assert device.buttons[PARAM_SIREN_START] == {}
    assert device.buttons[PARAM_SIREN_STOP] == {}


def test_configure_siren_start_by_ref_includes_input_ref() -> None:
    """IoT SirenStart stores ref and input_ref."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ref(
        channel_ability_refs=[IOT_SIREN_START_REF],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_START] == {
        PARAM_REF: IOT_SIREN_START_REF,
        PARAM_INPUT_REF: IOT_SIREN_START_INPUT_REF,
    }


def test_configure_siren_stop_by_ref() -> None:
    """IoT SirenStop stores ref only."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ref(
        channel_ability_refs=[IOT_SIREN_STOP_REF],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_STOP] == {PARAM_REF: IOT_SIREN_STOP_REF}


def test_ability_blocks_siren_ref_when_already_registered() -> None:
    """PaaS ability takes priority; IoT ref is not added."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ability(
        channel_abilities=["Siren"],
        is_ipc=True,
        device_abilities=[],
        imou_ha_device=device,
    )
    ImouHaDeviceManager.configure_button_by_ref(
        channel_ability_refs=[IOT_SIREN_START_REF, IOT_SIREN_STOP_REF],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_START] == {}
    assert device.buttons[PARAM_SIREN_STOP] == {}


@pytest.mark.asyncio
async def test_async_siren_start_calls_api() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_siren_start("DEV001", [0])

    client.async_request_api.assert_awaited_once_with(
        "/openapi/sirenStart",
        {"deviceId": "DEV001", "channels": [0]},
    )


@pytest.mark.asyncio
async def test_async_siren_start_ipc_omits_channels() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_siren_start("DEV001")

    client.async_request_api.assert_awaited_once_with(
        "/openapi/sirenStart",
        {"deviceId": "DEV001"},
    )


@pytest.mark.asyncio
async def test_async_siren_stop_calls_api() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_siren_stop("DEV001", [0])

    client.async_request_api.assert_awaited_once_with(
        "/openapi/sirenStop",
        {"deviceId": "DEV001", "channels": [0]},
    )


@pytest.mark.asyncio
async def test_press_siren_start_iot_sends_client_local_time() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_START] = {
        PARAM_REF: IOT_SIREN_START_REF,
        PARAM_INPUT_REF: IOT_SIREN_START_INPUT_REF,
    }
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    with patch("pyimouapi.siren.datetime") as mock_dt:
        aware = datetime(2026, 7, 31, 15, 8, tzinfo=UTC)
        now_mock = MagicMock()
        now_mock.astimezone.return_value = aware
        mock_dt.now.return_value = now_mock
        await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001",
        "prod1",
        IOT_SIREN_START_REF,
        {IOT_SIREN_START_INPUT_REF: "20260731T150800"},
    )


@pytest.mark.asyncio
async def test_press_siren_stop_iot_empty_content() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_STOP] = {PARAM_REF: IOT_SIREN_STOP_REF}
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_STOP, 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001", "prod1", IOT_SIREN_STOP_REF, {}
    )


@pytest.mark.asyncio
async def test_press_mute_iot_still_empty_content() -> None:
    device = _ha_device()
    device.buttons["mute"] = {PARAM_REF: "21600"}
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, "mute", 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001", "prod1", "21600", {}
    )


@pytest.mark.asyncio
async def test_press_siren_start_paas() -> None:
    device = _ha_device(is_ipc=True)
    device.buttons[PARAM_SIREN_START] = {}
    delegate = MagicMock()
    delegate.async_siren_start = AsyncMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_siren_start.assert_awaited_once_with("DEV001", None)
    delegate.async_iot_device_control.assert_not_called()


@pytest.mark.asyncio
async def test_press_siren_start_paas_multi_channel() -> None:
    device = _ha_device(is_ipc=False)
    device.buttons[PARAM_SIREN_START] = {}
    delegate = MagicMock()
    delegate.async_siren_start = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_siren_start.assert_awaited_once_with("DEV001", [0])


@pytest.mark.asyncio
async def test_press_siren_stop_paas() -> None:
    device = _ha_device(is_ipc=True)
    device.buttons[PARAM_SIREN_STOP] = {}
    delegate = MagicMock()
    delegate.async_siren_stop = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_STOP, 500)

    delegate.async_siren_stop.assert_awaited_once_with("DEV001", None)


@pytest.mark.asyncio
async def test_press_siren_paas_requires_channel() -> None:
    device = _ha_device(is_ipc=False)
    device.set_channel_id(None)
    device.buttons[PARAM_SIREN_START] = {}
    manager = ImouHaDeviceManager(MagicMock())

    with pytest.raises(RequestFailedException):
        await manager.async_press_button(device, PARAM_SIREN_START, 500)


@pytest.mark.asyncio
async def test_press_siren_paas_single_channel_without_channel_id() -> None:
    device = _ha_device(is_ipc=True)
    device.set_channel_id(None)
    device.buttons[PARAM_SIREN_START] = {}
    delegate = MagicMock()
    delegate.async_siren_start = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_siren_start.assert_awaited_once_with("DEV001", None)

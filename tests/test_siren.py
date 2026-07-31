"""Tests for siren start/stop button support."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.const import (
    PARAM_INPUT_REF,
    PARAM_REF,
    PARAM_SIREN_START,
    PARAM_SIREN_STOP,
)
from pyimouapi.device import ImouDeviceManager
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _ha_device(*, product_id: str = "prod1") -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Front Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_product_id(product_id)
    return device


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
        channel_ability_refs=["25500"],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_START] == {
        PARAM_REF: "25500",
        PARAM_INPUT_REF: "25501",
    }


def test_configure_siren_stop_by_ref() -> None:
    """IoT SirenStop stores ref only."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ref(
        channel_ability_refs=["22200"],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_STOP] == {PARAM_REF: "22200"}


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
        channel_ability_refs=["25500", "22200"],
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

    await manager.async_siren_start("DEV001", "0")

    client.async_request_api.assert_awaited_once_with(
        "/openapi/sirenStart",
        {"deviceId": "DEV001", "channelId": "0"},
    )


@pytest.mark.asyncio
async def test_async_siren_stop_calls_api() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_siren_stop("DEV001", "0")

    client.async_request_api.assert_awaited_once_with(
        "/openapi/sirenStop",
        {"deviceId": "DEV001", "channelId": "0"},
    )


@pytest.mark.asyncio
async def test_press_siren_start_iot_sends_client_local_time() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_START] = {
        PARAM_REF: "25500",
        PARAM_INPUT_REF: "25501",
    }
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    with patch("pyimouapi.ha_device.datetime") as mock_dt:
        aware = datetime(2026, 7, 31, 15, 8, tzinfo=UTC)
        now_mock = MagicMock()
        now_mock.astimezone.return_value = aware
        mock_dt.now.return_value = now_mock
        await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001",
        "prod1",
        "25500",
        {"25501": "2026-07-31T15:08:00+00:00"},
    )


@pytest.mark.asyncio
async def test_press_siren_stop_iot_empty_content() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_STOP] = {PARAM_REF: "22200"}
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_STOP, 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001", "prod1", "22200", {}
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
    device = _ha_device()
    device.buttons[PARAM_SIREN_START] = {}
    delegate = MagicMock()
    delegate.async_siren_start = AsyncMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_siren_start.assert_awaited_once_with("DEV001", "0")
    delegate.async_iot_device_control.assert_not_called()


@pytest.mark.asyncio
async def test_press_siren_stop_paas() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_STOP] = {}
    delegate = MagicMock()
    delegate.async_siren_stop = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_STOP, 500)

    delegate.async_siren_stop.assert_awaited_once_with("DEV001", "0")


@pytest.mark.asyncio
async def test_press_siren_paas_requires_channel() -> None:
    device = _ha_device()
    device.set_channel_id(None)
    device.buttons[PARAM_SIREN_START] = {}
    manager = ImouHaDeviceManager(MagicMock())

    with pytest.raises(RequestFailedException):
        await manager.async_press_button(device, PARAM_SIREN_START, 500)

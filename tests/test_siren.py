"""Tests for siren start/stop button support."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_INPUT_REF,
    PARAM_REF,
    PARAM_SIREN_START,
    PARAM_SIREN_STOP,
)
from pyimouapi.device import ImouDeviceManager
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

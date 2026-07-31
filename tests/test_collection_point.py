"""Tests for collection point support."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.collection_point import (
    build_collection_point_options,
    parse_iot_collection_names,
    parse_paas_collection_names,
    unique_preserve_order,
)
from pyimouapi.const import (
    PARAM_COLLECTION_POINT,
    PARAM_COLLECTION_POINT_PROMPT,
    PARAM_CURRENT_OPTION,
    PARAM_OPTIONS,
    PARAM_REF,
    PARAM_REF_TYPE,
    PARAM_SERVICES,
    PARAM_TURN_INPUT_REF,
    PARAM_TURN_REF,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _ha_device(*, product_id: str | None = None) -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Front Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    if product_id is not None:
        device.set_product_id(product_id)
    return device


def test_parse_paas_collection_names() -> None:
    """Parse names from getCollection response."""
    data = {"collections": [{"name": "door"}, {"name": "gate"}]}
    assert parse_paas_collection_names(data) == ["door", "gate"]


def test_parse_iot_collection_names_ref_map() -> None:
    """Parse names from IoT outputData ref map."""
    output = {"21501": [{"21551": "door"}, {"21551": "gate", "21552": "30"}]}
    assert parse_iot_collection_names(output) == ["door", "gate"]


def test_unique_preserve_order_keeps_first_occurrence() -> None:
    """Dedupe names without reordering."""
    assert unique_preserve_order(["gate", "door", "gate", "door"]) == [
        "gate",
        "door",
    ]


def test_build_collection_point_options_preserves_api_order() -> None:
    """Options keep API order instead of sorting alphabetically."""
    assert build_collection_point_options(["gate", "door", "gate"]) == [
        PARAM_COLLECTION_POINT_PROMPT,
        "gate",
        "door",
    ]


@pytest.mark.asyncio
async def test_update_device_collection_points_paas_preserves_order() -> None:
    """Refresh options preserve getCollection list order."""
    device = _ha_device()
    device.selects[PARAM_COLLECTION_POINT] = {
        PARAM_OPTIONS: [PARAM_COLLECTION_POINT_PROMPT],
        PARAM_CURRENT_OPTION: PARAM_COLLECTION_POINT_PROMPT,
    }
    delegate = MagicMock()
    delegate.async_get_device_collection = AsyncMock(
        return_value={
            "collections": [
                {"name": "gate"},
                {"name": "door"},
                {"name": "gate"},
            ]
        }
    )
    manager = ImouHaDeviceManager(delegate)

    await manager._async_update_device_collection_points(device)

    assert device.selects[PARAM_COLLECTION_POINT][PARAM_OPTIONS] == [
        PARAM_COLLECTION_POINT_PROMPT,
        "gate",
        "door",
    ]


@pytest.mark.asyncio
async def test_update_device_collection_points_paas() -> None:
    """Refresh options from PaaS getCollection."""
    device = _ha_device()
    device.selects[PARAM_COLLECTION_POINT] = {
        PARAM_OPTIONS: [PARAM_COLLECTION_POINT_PROMPT],
        PARAM_CURRENT_OPTION: PARAM_COLLECTION_POINT_PROMPT,
    }
    delegate = MagicMock()
    delegate.async_get_device_collection = AsyncMock(
        return_value={"collections": [{"name": "door"}]}
    )
    manager = ImouHaDeviceManager(delegate)

    await manager._async_update_device_collection_points(device)

    assert device.selects[PARAM_COLLECTION_POINT][PARAM_OPTIONS] == [
        PARAM_COLLECTION_POINT_PROMPT,
        "door",
    ]
    assert device.selects[PARAM_COLLECTION_POINT][PARAM_CURRENT_OPTION] == (
        PARAM_COLLECTION_POINT_PROMPT
    )


@pytest.mark.asyncio
async def test_update_device_collection_points_iot() -> None:
    """Refresh options from IoT GetCollection service."""
    device = _ha_device(product_id="prod1")
    device.selects[PARAM_COLLECTION_POINT] = {
        PARAM_REF: "21500",
        PARAM_TURN_REF: "22000",
        PARAM_TURN_INPUT_REF: "22001",
        PARAM_REF_TYPE: PARAM_SERVICES,
        PARAM_OPTIONS: [PARAM_COLLECTION_POINT_PROMPT],
        PARAM_CURRENT_OPTION: PARAM_COLLECTION_POINT_PROMPT,
    }
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock(
        return_value={"content": {"outputData": {"21501": [{"21551": "gate"}]}}}
    )
    manager = ImouHaDeviceManager(delegate)

    await manager._async_update_device_collection_points(device)

    assert device.selects[PARAM_COLLECTION_POINT][PARAM_OPTIONS] == [
        PARAM_COLLECTION_POINT_PROMPT,
        "gate",
    ]


@pytest.mark.asyncio
async def test_select_collection_point_prompt_is_noop() -> None:
    """Selecting placeholder does not call turn API."""
    device = _ha_device()
    device.selects[PARAM_COLLECTION_POINT] = {
        PARAM_OPTIONS: [PARAM_COLLECTION_POINT_PROMPT, "door"],
        PARAM_CURRENT_OPTION: PARAM_COLLECTION_POINT_PROMPT,
    }
    delegate = MagicMock()
    manager = ImouHaDeviceManager(delegate)

    await manager._async_select_collection_point_option(
        device, PARAM_COLLECTION_POINT_PROMPT
    )

    delegate.async_turn_device_collection.assert_not_called()
    delegate.async_iot_device_control.assert_not_called()


@pytest.mark.asyncio
async def test_select_collection_point_turn_paas() -> None:
    """Turn collection uses PaaS API and resets placeholder."""
    device = _ha_device()
    device.selects[PARAM_COLLECTION_POINT] = {
        PARAM_OPTIONS: [PARAM_COLLECTION_POINT_PROMPT, "door"],
        PARAM_CURRENT_OPTION: PARAM_COLLECTION_POINT_PROMPT,
    }
    delegate = MagicMock()
    delegate.async_turn_device_collection = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager._async_select_collection_point_option(device, "door")

    delegate.async_turn_device_collection.assert_awaited_once_with(
        "DEV001", "0", "door"
    )
    assert device.selects[PARAM_COLLECTION_POINT][PARAM_CURRENT_OPTION] == (
        PARAM_COLLECTION_POINT_PROMPT
    )


@pytest.mark.asyncio
async def test_select_collection_point_turn_iot() -> None:
    """Turn collection uses IoT TurnCollection service."""
    device = _ha_device(product_id="prod1")
    device.selects[PARAM_COLLECTION_POINT] = {
        PARAM_REF: "21500",
        PARAM_TURN_REF: "22000",
        PARAM_TURN_INPUT_REF: "22001",
        PARAM_OPTIONS: [PARAM_COLLECTION_POINT_PROMPT, "door"],
        PARAM_CURRENT_OPTION: PARAM_COLLECTION_POINT_PROMPT,
    }
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager._async_select_collection_point_option(device, "door")

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001", "prod1", "22000", {"22001": "door"}
    )

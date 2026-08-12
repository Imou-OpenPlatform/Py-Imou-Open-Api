"""Tests for concurrent refresh of iot service-backed sensors and texts."""

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from pyimouapi.const import (
    PARAM_CONTENT,
    PARAM_OUTPUT_DATA,
    PARAM_REF,
    PARAM_REF_TYPE,
    PARAM_SERVICES,
    PARAM_STATE,
    PARAM_STATUS,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


class ControlRecorder:
    """Stands in for async_iot_device_control and tracks concurrency."""

    def __init__(self) -> None:
        """Initialize the recorder."""
        self.refs: list[str] = []
        self._in_flight = 0
        self.max_in_flight = 0

    async def __call__(
        self, device_id: str, product_id: str, ref: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        """Record the call and yield once so overlap becomes observable."""
        self.refs.append(ref)
        self._in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self._in_flight)
        await asyncio.sleep(0)
        self._in_flight -= 1
        return {PARAM_CONTENT: {PARAM_OUTPUT_DATA: 42}}


def service_entry(ref: str) -> dict[str, Any]:
    """Build an entity entry that reads its state through an iot service."""
    return {PARAM_REF: ref, PARAM_REF_TYPE: PARAM_SERVICES, PARAM_STATE: None}


def build_device() -> ImouHaDevice:
    """Return an online iot device with service-backed sensors and texts."""
    device = ImouHaDevice("dev0", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("prod-1")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    device.sensors["power"] = service_entry("28600")
    device.sensors["voltage"] = service_entry("28601")
    device.sensors["current"] = service_entry("28602")
    device.texts["count_down_switch"] = service_entry("28603")
    return device


@pytest.mark.asyncio
async def test_service_reads_are_issued_concurrently() -> None:
    """Every service-backed sensor and text is refreshed in one concurrent batch."""
    manager = ImouHaDeviceManager(MagicMock())
    recorder = ControlRecorder()
    manager.delegate.async_iot_device_control = recorder
    device = build_device()

    await manager._async_update_services_entities(device)

    assert sorted(recorder.refs) == ["28600", "28601", "28602", "28603"]
    assert recorder.max_in_flight == 4
    assert device.sensors["power"][PARAM_STATE] == 42
    # Text entities expose numbers as strings.
    assert device.texts["count_down_switch"][PARAM_STATE] == "42"


@pytest.mark.asyncio
async def test_property_backed_entities_are_skipped() -> None:
    """Entities read from the batched device detail must not issue service calls."""
    manager = ImouHaDeviceManager(MagicMock())
    recorder = ControlRecorder()
    manager.delegate.async_iot_device_control = recorder
    device = build_device()
    # No ref_type means properties, which the single detail request already covers.
    device.sensors["battery"] = {PARAM_REF: "14800", PARAM_STATE: None}

    await manager._async_update_services_entities(device)

    assert "14800" not in recorder.refs


@pytest.mark.asyncio
async def test_one_failing_read_does_not_block_the_others() -> None:
    """A failing service read is logged per entity and leaves siblings updated."""
    manager = ImouHaDeviceManager(MagicMock())
    device = build_device()

    async def control(
        device_id: str, product_id: str, ref: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        if ref == "28601":
            raise RuntimeError("voltage boom")
        return {PARAM_CONTENT: {PARAM_OUTPUT_DATA: 7}}

    manager.delegate.async_iot_device_control = control

    await manager._async_update_services_entities(device)

    assert device.sensors["power"][PARAM_STATE] == 7
    assert device.sensors["voltage"][PARAM_STATE] is None
    assert device.sensors["current"][PARAM_STATE] == 7


@pytest.mark.asyncio
async def test_no_service_entities_makes_no_calls() -> None:
    """A device without service-backed entities issues no requests at all."""
    manager = ImouHaDeviceManager(MagicMock())
    recorder = ControlRecorder()
    manager.delegate.async_iot_device_control = recorder
    device = ImouHaDevice("dev0", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("prod-1")

    await manager._async_update_services_entities(device)

    assert recorder.refs == []

"""Tests for ImouDeviceManager.async_get_devices ability-ref fetching."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    API_ENDPOINT_LIST_DEVICE_DETAILS,
    PARAM_ABILITY_REFS,
    PARAM_BRAND,
    PARAM_COUNT,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_LIST,
    PARAM_DEVICE_MODEL,
    PARAM_DEVICE_NAME,
    PARAM_DEVICE_STATUS,
    PARAM_PAGE,
    PARAM_PRODUCT_ID,
)
from pyimouapi.device import ImouDeviceManager


def make_device(device_id: str, product_id: str | None = None) -> dict:
    """Build one deviceList entry."""
    entry = {
        PARAM_DEVICE_ID: device_id,
        PARAM_DEVICE_NAME: f"Device {device_id}",
        PARAM_DEVICE_STATUS: "1",
        PARAM_BRAND: "Imou",
        PARAM_DEVICE_MODEL: "IPC-A1",
    }
    if product_id is not None:
        entry[PARAM_PRODUCT_ID] = product_id
    return entry


class DetailTracker:
    """Stands in for async_get_iot_device_detail_info and records concurrency."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.calls: list[tuple[str, str]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def __call__(self, device_id: str, product_id: str) -> dict:
        """Record the call and yield so overlapping callers are observable."""
        self.calls.append((device_id, product_id))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0)
        self.in_flight -= 1
        return {PARAM_ABILITY_REFS: "1,2,3"}


def make_manager(pages: dict[int, dict]) -> tuple[ImouDeviceManager, DetailTracker]:
    """Build a manager whose device list returns the given pages."""

    async def request(endpoint: str, params: dict) -> dict:
        assert endpoint == API_ENDPOINT_LIST_DEVICE_DETAILS
        return pages[params[PARAM_PAGE]]

    client = MagicMock()
    client.async_request_api = AsyncMock(side_effect=request)
    manager = ImouDeviceManager(client)
    tracker = DetailTracker()
    manager.async_get_iot_device_detail_info = tracker
    return manager, tracker


@pytest.mark.asyncio
async def test_iot_detail_requests_run_concurrently() -> None:
    """Listing N iot devices must not cost N serial detail round trips."""
    devices = [make_device(f"dev{i}", f"prod{i}") for i in range(4)]
    manager, tracker = make_manager({1: {PARAM_COUNT: 4, PARAM_DEVICE_LIST: devices}})

    result = await manager.async_get_devices()

    assert len(result) == 4
    assert len(tracker.calls) == 4
    assert tracker.max_in_flight == 4
    assert all(device.device_ability_refs == "1,2,3" for device in result)


@pytest.mark.asyncio
async def test_non_iot_devices_skip_detail_requests() -> None:
    """Devices without a productId must not trigger a detail call."""
    devices = [make_device("dev0"), make_device("dev1", "prod1")]
    manager, tracker = make_manager({1: {PARAM_COUNT: 2, PARAM_DEVICE_LIST: devices}})

    result = await manager.async_get_devices()

    assert len(result) == 2
    assert tracker.calls == [("dev1", "prod1")]


@pytest.mark.asyncio
async def test_detail_failure_still_propagates() -> None:
    """A failing detail call must not be swallowed by the concurrent fetch."""
    devices = [make_device(f"dev{i}", f"prod{i}") for i in range(3)]
    manager, _ = make_manager({1: {PARAM_COUNT: 3, PARAM_DEVICE_LIST: devices}})
    manager.async_get_iot_device_detail_info = AsyncMock(
        side_effect=RuntimeError("detail boom")
    )

    with pytest.raises(RuntimeError, match="detail boom"):
        await manager.async_get_devices()


@pytest.mark.asyncio
async def test_pagination_fetches_details_for_every_page() -> None:
    """Ability refs are resolved for devices found on later pages too."""
    page1 = [make_device(f"dev{i}", f"prod{i}") for i in range(10)]
    page2 = [make_device("dev10", "prod10")]
    manager, tracker = make_manager(
        {
            1: {PARAM_COUNT: 10, PARAM_DEVICE_LIST: page1},
            2: {PARAM_COUNT: 1, PARAM_DEVICE_LIST: page2},
        }
    )

    result = await manager.async_get_devices()

    assert len(result) == 11
    assert len(tracker.calls) == 11
    # Pages are sequential, so concurrency is bounded by the largest page.
    assert tracker.max_in_flight == 10

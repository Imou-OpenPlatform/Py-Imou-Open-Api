"""Tests for ImouDeviceManager.async_get_devices ability-ref fetching."""

import asyncio
import logging
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
async def test_one_failing_detail_does_not_cost_the_whole_account(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An accessory that will not answer must not hide every other device.

    The detail call fails for an accessory that is offline, rate limited, or
    answering 5xx. Raising here left Home Assistant with no devices at all for
    as long as that one device stayed unhappy.
    """
    devices = [make_device(f"dev{i}", f"prod{i}") for i in range(3)]
    manager, _ = make_manager({1: {PARAM_COUNT: 3, PARAM_DEVICE_LIST: devices}})

    async def detail(device_id: str, product_id: str) -> dict:
        if device_id == "dev1":
            raise RuntimeError("detail boom")
        return {PARAM_ABILITY_REFS: "1,2,3"}

    manager.async_get_iot_device_detail_info = detail

    with caplog.at_level(logging.WARNING):
        result = await manager.async_get_devices()

    assert [device.device_id for device in result] == ["dev0", "dev1", "dev2"]
    assert result[0].device_ability_refs == "1,2,3"
    assert result[2].device_ability_refs == "1,2,3"
    # The one that failed keeps its placeholder and is retried next listing.
    assert result[1].device_ability_refs == "unknown"
    assert "dev1" in caplog.text
    assert "detail boom" in caplog.text


@pytest.mark.asyncio
async def test_pagination_stops_on_a_short_page_whatever_count_means() -> None:
    """Paging must end when a page runs out, not when a count field says so.

    ``count`` is read as the number of entries on this page, but the API may
    well mean the total across all pages. Under that reading an account holding
    exactly one full page would ask for page after page forever, so the decision
    is based on what actually came back.
    """
    page1 = [make_device(f"dev{i}", f"prod{i}") for i in range(10)]
    manager, _ = make_manager(
        {
            # count repeats the account total on every page, as a total would.
            1: {PARAM_COUNT: 10, PARAM_DEVICE_LIST: page1},
            2: {PARAM_COUNT: 10, PARAM_DEVICE_LIST: []},
        }
    )

    result = await manager.async_get_devices()

    assert len(result) == 10


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


@pytest.mark.asyncio
async def test_fetch_ability_refs_false_skips_detail_calls() -> None:
    """Discovery can list devices without spending a detail call per IoT device."""
    devices = [make_device(f"dev{i}", f"prod{i}") for i in range(3)]
    manager, tracker = make_manager({1: {PARAM_COUNT: 3, PARAM_DEVICE_LIST: devices}})

    result = await manager.async_get_devices(fetch_ability_refs=False)

    assert len(result) == 3
    assert tracker.calls == []
    assert all(device.device_ability_refs == "unknown" for device in result)


@pytest.mark.asyncio
async def test_fetch_ability_refs_set_only_queries_named_devices() -> None:
    """Only the device ids in the set spend a detail call."""
    devices = [make_device(f"dev{i}", f"prod{i}") for i in range(3)]
    manager, tracker = make_manager({1: {PARAM_COUNT: 3, PARAM_DEVICE_LIST: devices}})

    result = await manager.async_get_devices(fetch_ability_refs={"dev1"})

    assert len(result) == 3
    assert tracker.calls == [("dev1", "prod1")]
    assert result[0].device_ability_refs == "unknown"
    assert result[1].device_ability_refs == "1,2,3"
    assert result[2].device_ability_refs == "unknown"

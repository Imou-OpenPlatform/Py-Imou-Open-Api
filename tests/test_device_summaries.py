"""Tests for ImouDeviceManager.async_get_device_summaries."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    API_ENDPOINT_LIST_DEVICE_DETAILS,
    PARAM_COUNT,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_LIST,
    PARAM_DEVICE_MODEL,
    PARAM_DEVICE_NAME,
    PARAM_DEVICE_STATUS,
    PARAM_PAGE,
    PARAM_PAGE_SIZE,
)
from pyimouapi.device import ImouDeviceManager, ImouDeviceSummary


def _make_device(
    device_id: str,
    name: str | None = "Camera",
    model: str = "IPC-A1",
    status: str | int = "1",
) -> dict:
    entry: dict = {
        PARAM_DEVICE_ID: device_id,
        PARAM_DEVICE_STATUS: status,
    }
    if name is not None:
        entry[PARAM_DEVICE_NAME] = name
    if model:
        entry[PARAM_DEVICE_MODEL] = model
    return entry


@pytest.mark.asyncio
async def test_get_device_summaries_single_page():
    client = MagicMock()
    client.async_request_api = AsyncMock(
        return_value={
            PARAM_COUNT: 2,
            PARAM_DEVICE_LIST: [
                _make_device("dev1", "Front Door", "IPC-A1", "1"),
                _make_device("dev2", None, "", "0"),
                {},
            ],
        }
    )
    manager = ImouDeviceManager(client)

    summaries = await manager.async_get_device_summaries()

    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_LIST_DEVICE_DETAILS,
        {PARAM_PAGE: 1, PARAM_PAGE_SIZE: 50},
    )
    assert summaries == [
        ImouDeviceSummary(
            device_id="dev1", name="Front Door", model="IPC-A1", status="1"
        ),
        ImouDeviceSummary(device_id="dev2", name="dev2", model="", status="0"),
    ]


@pytest.mark.asyncio
async def test_get_device_summaries_stop_on_a_short_page():
    """Paging ends when a page runs out, whatever `count` turns out to mean.

    This picker feeds the config flow's device list, so an account large enough
    to page would have hung device selection if `count` reports the account
    total rather than the size of the page in hand.
    """
    page1_devices = [
        _make_device(f"dev{i}", f"Device {i}", "IPC", "1") for i in range(50)
    ]

    async def mock_request(endpoint, params):
        if params[PARAM_PAGE] == 1:
            return {PARAM_COUNT: 50, PARAM_DEVICE_LIST: page1_devices}
        if params[PARAM_PAGE] == 2:
            # A total would keep reporting 50 here, with nothing left to hand out.
            return {PARAM_COUNT: 50, PARAM_DEVICE_LIST: []}
        raise AssertionError(f"Unexpected page: {params[PARAM_PAGE]}")

    client = MagicMock()
    client.async_request_api = AsyncMock(side_effect=mock_request)
    manager = ImouDeviceManager(client)

    summaries = await manager.async_get_device_summaries()

    assert len(summaries) == 50


@pytest.mark.asyncio
async def test_get_device_summaries_pagination():
    page1_devices = [
        _make_device(f"dev{i}", f"Device {i}", "IPC", "1") for i in range(50)
    ]
    page2_devices = [_make_device("dev50", "Device 50", "IPC", "1")]

    async def mock_request(endpoint, params):
        if params[PARAM_PAGE] == 1:
            return {PARAM_COUNT: 50, PARAM_DEVICE_LIST: page1_devices}
        if params[PARAM_PAGE] == 2:
            return {PARAM_COUNT: 1, PARAM_DEVICE_LIST: page2_devices}
        raise AssertionError(f"Unexpected page: {params[PARAM_PAGE]}")

    client = MagicMock()
    client.async_request_api = AsyncMock(side_effect=mock_request)
    manager = ImouDeviceManager(client)

    summaries = await manager.async_get_device_summaries()

    assert client.async_request_api.await_count == 2
    assert len(summaries) == 51
    assert summaries[0].device_id == "dev0"
    assert summaries[50].device_id == "dev50"

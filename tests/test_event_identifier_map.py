"""Tests for product-model event ref → identifier mapping."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import API_ENDPOINT_GET_PRODUCT_MODEL, PARAM_PRODUCT_ID
from pyimouapi.device import ImouDeviceManager, _parse_event_ref_map
from pyimouapi.exceptions import RequestFailedException


def test_parse_event_ref_map_extracts_events_only():
    data = {
        "events": [
            {"ref": "33000", "identifier": "doorOpen", "name": "Door"},
            {"ref": 123900, "identifier": "electricity"},
            {"identifier": "missingRef"},
            {"ref": "999", "identifier": ""},
            {"ref": "1"},
        ],
        "properties": [{"ref": "1", "identifier": "battery"}],
    }
    assert _parse_event_ref_map(data) == {
        "33000": "doorOpen",
        "123900": "electricity",
    }


def test_parse_event_ref_map_missing_events():
    assert _parse_event_ref_map({}) == {}
    assert _parse_event_ref_map({"events": "bad"}) == {}


@pytest.mark.asyncio
async def test_ensure_event_map_fetches_once_and_caches():
    client = MagicMock()
    client.async_request_api = AsyncMock(
        return_value={
            "events": [{"ref": "33000", "identifier": "doorOpen"}],
        }
    )
    manager = ImouDeviceManager(client)

    await manager.async_ensure_event_map("pidA")
    await manager.async_ensure_event_map("pidA")

    assert client.async_request_api.await_count == 1
    client.async_request_api.assert_awaited_with(
        API_ENDPOINT_GET_PRODUCT_MODEL,
        {PARAM_PRODUCT_ID: "pidA"},
    )
    assert await manager.async_resolve_event_identifier("pidA", "33000") == "doorOpen"
    assert await manager.async_resolve_event_identifier("pidA", "missing") is None


@pytest.mark.asyncio
async def test_ensure_event_map_failure_does_not_poison_cache():
    client = MagicMock()
    client.async_request_api = AsyncMock(
        side_effect=[
            RequestFailedException("boom"),
            {"events": [{"ref": "1", "identifier": "ok"}]},
        ]
    )
    manager = ImouDeviceManager(client)

    await manager.async_ensure_event_map("pidB")
    assert await manager.async_resolve_event_identifier("pidB", "1") == "ok"
    assert client.async_request_api.await_count == 2


@pytest.mark.asyncio
async def test_ensure_event_map_single_flight():
    import asyncio

    client = MagicMock()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_request(endpoint, params):
        started.set()
        await release.wait()
        return {"events": [{"ref": "9", "identifier": "once"}]}

    client.async_request_api = AsyncMock(side_effect=slow_request)
    manager = ImouDeviceManager(client)

    t1 = asyncio.create_task(manager.async_ensure_event_map("pidC"))
    await started.wait()
    t2 = asyncio.create_task(manager.async_ensure_event_map("pidC"))
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(t1, t2)

    assert client.async_request_api.await_count == 1

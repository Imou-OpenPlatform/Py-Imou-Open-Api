"""Tests for bindDevice API wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import API_ENDPOINT_BIND_DEVICE, PARAM_CODE, PARAM_DEVICE_ID
from pyimouapi.device import ImouDeviceManager


@pytest.mark.asyncio
async def test_async_bind_device_calls_api_with_device_id_and_code() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_bind_device("TESTQWERXXXX", "Admin123")

    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_BIND_DEVICE,
        {PARAM_DEVICE_ID: "TESTQWERXXXX", PARAM_CODE: "Admin123"},
    )


@pytest.mark.asyncio
async def test_async_bind_device_allows_empty_code() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_bind_device("TESTQWERXXXX", "")

    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_BIND_DEVICE,
        {PARAM_DEVICE_ID: "TESTQWERXXXX", PARAM_CODE: ""},
    )

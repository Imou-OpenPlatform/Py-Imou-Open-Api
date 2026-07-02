"""Tests for ImouOpenApiClient.async_set_message_callback."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.const import API_ENDPOINT_SET_MESSAGE_CALLBACK
from pyimouapi.openapi import ImouOpenApiClient


@pytest.fixture
def client() -> ImouOpenApiClient:
    return ImouOpenApiClient("app_id", "app_secret", "api.example.com")


@pytest.mark.asyncio
async def test_set_message_callback_on(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(return_value={})
    await client.async_set_message_callback(
        status="on",
        callback_url="https://example.com/webhook",
        callback_flag=["alarm", "deviceStatus"],
    )
    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_SET_MESSAGE_CALLBACK,
        {
            "status": "on",
            "basePush": "2",
            "callbackUrl": "https://example.com/webhook",
            "callbackFlag": "alarm,deviceStatus",
        },
    )


@pytest.mark.asyncio
async def test_set_message_callback_off(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(return_value={})
    await client.async_set_message_callback(status="off")
    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_SET_MESSAGE_CALLBACK,
        {
            "status": "off",
            "basePush": "2",
        },
    )


@pytest.mark.asyncio
async def test_set_message_callback_on_requires_url(client: ImouOpenApiClient) -> None:
    with pytest.raises(ValueError):
        await client.async_set_message_callback(status="on")

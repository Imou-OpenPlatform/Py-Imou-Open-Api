"""Tests for ImouOpenApiClient.async_set_message_callback."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from pyimouapi.const import (
    API_ENDPOINT_GET_MESSAGE_CALLBACK,
    API_ENDPOINT_GET_PLAY_TOKEN_KEY,
    API_ENDPOINT_SET_MESSAGE_CALLBACK,
)
from pyimouapi.openapi import (
    REDACTED,
    ImouOpenApiClient,
    _redacted_request,
    _redacted_response,
)


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
async def test_get_message_callback(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(
        return_value={
            "status": "on",
            "callbackUrl": "https://example.com/webhook",
            "callbackFlag": "alarm,deviceStatus,capabilityEvent",
        }
    )
    data = await client.async_get_message_callback()
    assert data["callbackFlag"] == "alarm,deviceStatus,capabilityEvent"
    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_GET_MESSAGE_CALLBACK,
        {},
    )


@pytest.mark.asyncio
async def test_get_play_token_key(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(
        return_value={"playTokenKey": "ab" * 16, "playTokenKeyV2": "cd" * 32}
    )
    assert await client.async_get_play_token_key("SN1") == "cd" * 32
    client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_GET_PLAY_TOKEN_KEY,
        {"deviceId": "SN1"},
    )


def test_logged_response_masks_play_tokens_and_keeps_the_serial() -> None:
    """Debug logs must not keep a play token or its key."""
    body = {
        "result": {
            "data": {
                "deviceList": [{"deviceId": "SN1", "playTokenV2": "secret-token"}],
                "playTokenKey": "ab" * 16,
                "playTokenKeyV2": "cd" * 32,
            }
        }
    }
    masked = _redacted_response(body)
    device = masked["result"]["data"]["deviceList"][0]
    assert device["deviceId"] == "SN1"
    assert device["playTokenV2"] == REDACTED
    assert masked["result"]["data"]["playTokenKey"] == REDACTED
    assert masked["result"]["data"]["playTokenKeyV2"] == REDACTED
    assert body["result"]["data"]["deviceList"][0]["playTokenV2"] == "secret-token"


def test_request_redaction_masks_callback_url_without_mutating_body() -> None:
    """Request logging hides webhook identifiers as well as credentials."""
    body = {
        "system": {"sign": "signature-secret", "appId": "app-id"},
        "params": {
            "token": "request-token-secret",
            "code": "device-password-secret",
            "callbackUrl": (
                "https://user:password@callbacks.example:8443"
                "/webhooks/webhook-secret?token=query-secret#fragment-secret"
            ),
        },
    }
    original = deepcopy(body)

    masked = _redacted_request(body)

    assert masked["system"]["sign"] == REDACTED
    assert masked["params"]["token"] == REDACTED
    assert masked["params"]["code"] == REDACTED
    assert masked["params"]["callbackUrl"] == "https://callbacks.example:8443"
    assert body == original


def test_response_redaction_recurses_and_conservatively_masks_bad_urls() -> None:
    """Nested stream URLs retain only safe hosts; malformed values reveal nothing."""
    signed_url = (
        "https://user:password@media.example:9443/live/path-secret.flv"
        "?token=query-secret#fragment-secret"
    )
    body = {
        "result": {
            "data": {
                "url": signed_url,
                "hls": signed_url,
                "flv": signed_url,
                "flvHD": signed_url,
                "callbackUrl": signed_url,
                "streams": [[{"hls": signed_url}]],
                "malformed": {
                    "url": "https://",
                    "hls": "https://cdn.example:bad/live.flv",
                    "flv": "https://cdn.example/live\nsecret.flv",
                    "callbackUrl": "not a URL",
                },
            }
        }
    }
    original = deepcopy(body)

    masked = _redacted_response(body)
    data = masked["result"]["data"]

    for field in ("url", "hls", "flv", "flvHD", "callbackUrl"):
        assert data[field] == "https://media.example:9443"
    assert data["streams"][0][0]["hls"] == "https://media.example:9443"
    assert all(value == REDACTED for value in data["malformed"].values())
    for secret in (
        "user",
        "password",
        "path-secret",
        "query-secret",
        "fragment-secret",
        "secret.flv",
    ):
        assert secret not in repr(masked)
    assert body == original


@pytest.mark.asyncio
async def test_get_play_token_key_missing(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(return_value={})
    assert await client.async_get_play_token_key("SN1") is None


@pytest.mark.asyncio
async def test_set_message_callback_on_requires_url(client: ImouOpenApiClient) -> None:
    with pytest.raises(ValueError):
        await client.async_set_message_callback(status="on")

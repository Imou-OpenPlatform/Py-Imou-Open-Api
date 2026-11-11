"""Tests for v2 capability client and catalog parsing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pyimouapi.capability.catalog import capability_set_from_list_response
from pyimouapi.capability.client import (
    async_capability_list,
    async_property_get,
    async_property_set,
    async_service_invoke,
)
from pyimouapi.const import (
    API_V2_DEVICE_CAPABILITY_LIST,
    API_V2_DEVICE_PROPERTY_GET,
    API_V2_DEVICE_PROPERTY_SET,
    API_V2_DEVICE_SERVICE_INVOKE,
)
from pyimouapi.openapi import ImouOpenApiClient

LIST_FIXTURE = {
    "deviceId": "TESTIPC000012345",
    "channelId": "0",
    "productId": "mhpf7Dsz",
    "capabilities": [
        {
            "capabilityId": "detection.motion",
            "name": "Motion",
            "scope": "channel",
            "properties": [
                {
                    "propertyId": "detection.motion.enabled",
                    "name": "Motion detection",
                    "accessMode": "rw",
                    "dataType": {"type": "int", "specs": {"range": [0, 1]}},
                    "defaultData": 0,
                }
            ],
            "services": [],
            "events": [
                {
                    "eventId": "detection.motion.detected",
                    "name": "Motion",
                    "outputData": [],
                }
            ],
        },
        {
            "capabilityId": "image.wdr",
            "properties": [
                {
                    "propertyId": "image.wdr.mode",
                    "accessMode": "rw",
                    "dataType": {
                        "type": "enum",
                        "specs": {
                            "list": [
                                {"value": 0, "desc": "Off"},
                                {"value": 1, "desc": "On"},
                                {"value": 2, "desc": "Adaptive"},
                            ]
                        },
                    },
                }
            ],
            "services": [
                {
                    "serviceId": "ptz.aim.step",
                    "name": "PTZ step",
                    "inputData": [],
                    "outputData": [],
                }
            ],
            "events": [],
        },
    ],
}


@pytest.fixture
def client() -> ImouOpenApiClient:
    return ImouOpenApiClient("app_id", "app_secret", "api.example.com")


def test_capability_set_from_list_response() -> None:
    cap = capability_set_from_list_response(LIST_FIXTURE)
    assert cap.device_id == "TESTIPC000012345"
    assert cap.channel_id == "0"
    assert cap.has_property("detection.motion.enabled")
    assert cap.has_property("image.wdr.mode")
    assert cap.has_service("ptz.aim.step")
    assert cap.has_event("detection.motion.detected")
    motion = cap.properties["detection.motion.enabled"]
    assert motion.writable
    assert motion.data_type == "int"
    assert motion.range_min == 0 and motion.range_max == 1
    wdr = cap.properties["image.wdr.mode"]
    assert wdr.data_type == "enum"
    assert len(wdr.enum_options) == 3
    assert wdr.enum_options[2].desc == "Adaptive"


@pytest.mark.asyncio
async def test_async_capability_list(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(return_value=LIST_FIXTURE)
    cap = await async_capability_list(client, device_id="TESTIPC", channel_id="0")
    assert cap.has_property("detection.motion.enabled")
    client.async_request_api.assert_awaited_once_with(
        API_V2_DEVICE_CAPABILITY_LIST,
        {
            "incloudTsl": False,
            "deviceId": "TESTIPC",
            "channelId": "0",
        },
    )


@pytest.mark.asyncio
async def test_async_property_get(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(
        return_value={
            "properties": {
                "detection.motion.enabled": 1,
                "image.night.mode": 0,
            }
        }
    )
    values = await async_property_get(
        client,
        device_id="SN1",
        channel_id="0",
        properties=["detection.motion.enabled", "image.night.mode"],
    )
    assert values == {"detection.motion.enabled": 1, "image.night.mode": 0}
    client.async_request_api.assert_awaited_once_with(
        API_V2_DEVICE_PROPERTY_GET,
        {
            "deviceId": "SN1",
            "channelId": "0",
            "properties": ["detection.motion.enabled", "image.night.mode"],
        },
    )


@pytest.mark.asyncio
async def test_async_property_set(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(return_value={})
    await async_property_set(
        client,
        device_id="SN1",
        channel_id="0",
        properties={"detection.motion.enabled": 1},
    )
    client.async_request_api.assert_awaited_once_with(
        API_V2_DEVICE_PROPERTY_SET,
        {
            "deviceId": "SN1",
            "channelId": "0",
            "properties": {"detection.motion.enabled": 1},
        },
    )


@pytest.mark.asyncio
async def test_async_service_invoke(client: ImouOpenApiClient) -> None:
    client.async_request_api = AsyncMock(return_value={"outputData": {"ok": 1}})
    result = await async_service_invoke(
        client,
        device_id="SN1",
        channel_id="0",
        service_id="ptz.aim.step",
        input_data={"x": 1, "y": 0},
    )
    assert result["outputData"]["ok"] == 1
    client.async_request_api.assert_awaited_once_with(
        API_V2_DEVICE_SERVICE_INVOKE,
        {
            "deviceId": "SN1",
            "channelId": "0",
            "serviceId": "ptz.aim.step",
            "inputData": {"x": 1, "y": 0},
        },
    )


@pytest.mark.asyncio
async def test_capability_list_requires_device_or_product(
    client: ImouOpenApiClient,
) -> None:
    with pytest.raises(ValueError):
        await async_capability_list(client)

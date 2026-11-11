"""Open API v2 capability list / property / service helpers."""

from __future__ import annotations

from typing import Any

from ..const import (
    API_V2_DEVICE_CAPABILITY_LIST,
    API_V2_DEVICE_PROPERTY_GET,
    API_V2_DEVICE_PROPERTY_SET,
    API_V2_DEVICE_SERVICE_INVOKE,
)
from ..openapi import ImouOpenApiClient
from .catalog import CapabilitySet, capability_set_from_list_response


def _require_device_or_product(device_id: str | None, product_id: str | None) -> None:
    if not device_id and not product_id:
        msg = "device_id or product_id is required"
        raise ValueError(msg)


async def async_capability_list(
    client: ImouOpenApiClient,
    *,
    device_id: str | None = None,
    product_id: str | None = None,
    channel_id: str | None = None,
    lang: str | None = None,
    incloud_tsl: bool = False,
) -> CapabilitySet:
    """Call ``device.capability.list`` and return a parsed :class:`CapabilitySet`."""
    _require_device_or_product(device_id, product_id)
    params: dict[str, Any] = {"incloudTsl": bool(incloud_tsl)}
    if device_id:
        params["deviceId"] = device_id
    if product_id:
        params["productId"] = product_id
    if channel_id is not None and channel_id != "":
        params["channelId"] = str(channel_id)
    if lang:
        params["lang"] = lang
    data = await client.async_request_api(API_V2_DEVICE_CAPABILITY_LIST, params)
    if not isinstance(data, dict):
        return capability_set_from_list_response({})
    return capability_set_from_list_response(data)


async def async_property_get(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    properties: list[str],
    channel_id: str | None = None,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Read values for one or more property ids (same device/channel level)."""
    if not properties:
        return {}
    params: dict[str, Any] = {
        "deviceId": device_id,
        "properties": list(properties),
    }
    if product_id:
        params["productId"] = product_id
    if channel_id is not None and channel_id != "":
        params["channelId"] = str(channel_id)
    data = await client.async_request_api(API_V2_DEVICE_PROPERTY_GET, params)
    if not isinstance(data, dict):
        return {}
    raw = data.get("properties")
    return dict(raw) if isinstance(raw, dict) else {}


async def async_property_set(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    properties: dict[str, Any],
    channel_id: str | None = None,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Write property values (batch)."""
    if not properties:
        return {}
    params: dict[str, Any] = {
        "deviceId": device_id,
        "properties": properties,
    }
    if product_id:
        params["productId"] = product_id
    if channel_id is not None and channel_id != "":
        params["channelId"] = str(channel_id)
    data = await client.async_request_api(API_V2_DEVICE_PROPERTY_SET, params)
    return data if isinstance(data, dict) else {}


async def async_service_invoke(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    service_id: str,
    input_data: dict[str, Any] | None = None,
    channel_id: str | None = None,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Invoke a v2 service once."""
    params: dict[str, Any] = {
        "deviceId": device_id,
        "serviceId": service_id,
    }
    if product_id:
        params["productId"] = product_id
    if channel_id is not None and channel_id != "":
        params["channelId"] = str(channel_id)
    if input_data is not None:
        params["inputData"] = input_data
    data = await client.async_request_api(API_V2_DEVICE_SERVICE_INVOKE, params)
    return data if isinstance(data, dict) else {}

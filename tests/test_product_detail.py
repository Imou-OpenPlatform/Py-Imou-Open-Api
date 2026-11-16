"""Tests for batched product-detail discovery."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.const import API_ENDPOINT_LIST_PRODUCT_DETAIL
from pyimouapi.device import ImouDeviceManager
from pyimouapi.product_detail import ProductDetail, parse_product_details


def test_parse_product_details_indexes_items() -> None:
    assert parse_product_details(
        {
            "item": [
                {"productId": "lamp-pid", "deviceType": "Lamp"},
                {"productId": "ipc-pid", "deviceType": "IPC"},
            ]
        }
    ) == {
        "lamp-pid": ProductDetail("lamp-pid", "Lamp"),
        "ipc-pid": ProductDetail("ipc-pid", "IPC"),
    }


@pytest.mark.parametrize("data", [None, [], {}, {"item": None}, {"item": {}}])
def test_parse_product_details_rejects_malformed_items(data: object) -> None:
    assert parse_product_details(data) == {}


def test_parse_product_details_skips_missing_ids_and_allows_missing_types() -> None:
    assert parse_product_details(
        {
            "item": [
                None,
                {},
                {"deviceType": "Lamp"},
                {"productId": ""},
                {"productId": "missing-type"},
                {"productId": "blank-type", "deviceType": "  "},
            ]
        }
    ) == {
        "missing-type": ProductDetail("missing-type"),
        "blank-type": ProductDetail("blank-type"),
    }


@pytest.mark.asyncio
async def test_product_details_are_requested_once_for_unique_ids() -> None:
    api_client = AsyncMock()
    api_client.async_request_api.return_value = {
        "item": [
            {"productId": "lamp-pid", "deviceType": "Lamp"},
            {"productId": "ipc-pid", "deviceType": "IPC"},
        ]
    }
    manager = ImouDeviceManager(api_client)

    result = await manager.async_get_product_details(
        ["lamp-pid", "lamp-pid", "ipc-pid"]
    )

    api_client.async_request_api.assert_awaited_once_with(
        API_ENDPOINT_LIST_PRODUCT_DETAIL,
        {"productIds": ["ipc-pid", "lamp-pid"]},
    )
    assert result == {
        "lamp-pid": ProductDetail("lamp-pid", "Lamp"),
        "ipc-pid": ProductDetail("ipc-pid", "IPC"),
    }


@pytest.mark.asyncio
async def test_product_details_cache_returned_items_but_retry_missing_items() -> None:
    api_client = AsyncMock()
    api_client.async_request_api.side_effect = [
        {"item": [{"productId": "known-pid", "deviceType": "Lamp"}]},
        {"item": [{"productId": "missing-pid", "deviceType": "IPC"}]},
    ]
    manager = ImouDeviceManager(api_client)

    first = await manager.async_get_product_details(["known-pid", "missing-pid"])
    second = await manager.async_get_product_details(["known-pid", "missing-pid"])

    assert first == {"known-pid": ProductDetail("known-pid", "Lamp")}
    assert second == {
        "known-pid": ProductDetail("known-pid", "Lamp"),
        "missing-pid": ProductDetail("missing-pid", "IPC"),
    }
    assert api_client.async_request_api.await_args_list[1].args == (
        API_ENDPOINT_LIST_PRODUCT_DETAIL,
        {"productIds": ["missing-pid"]},
    )


@pytest.mark.asyncio
async def test_device_discovery_adds_product_type_without_ability_refs() -> None:
    api_client = AsyncMock()
    api_client.async_request_api.side_effect = [
        {
            "deviceList": [
                {
                    "deviceId": "lamp",
                    "deviceName": "Lamp",
                    "deviceStatus": "1",
                    "brand": "Imou",
                    "deviceModel": "Bulb",
                    "productId": "lamp-pid",
                }
            ]
        },
        {"item": [{"productId": "lamp-pid", "deviceType": "Lamp"}]},
    ]
    manager = ImouDeviceManager(api_client)

    devices = await manager.async_get_devices(fetch_ability_refs=False)

    assert devices[0].product_device_type == "Lamp"
    assert api_client.async_request_api.await_args_list[1].args == (
        API_ENDPOINT_LIST_PRODUCT_DETAIL,
        {"productIds": ["lamp-pid"]},
    )


@pytest.mark.asyncio
async def test_product_detail_failure_keeps_devices_and_retries_discovery(
    caplog: pytest.LogCaptureFixture,
) -> None:
    device_page = {
        "deviceList": [
            {
                "deviceId": "lamp",
                "deviceName": "Lamp",
                "deviceStatus": "1",
                "brand": "Imou",
                "deviceModel": "Bulb",
                "productId": "lamp-pid",
            }
        ]
    }
    api_client = AsyncMock()
    api_client.async_request_api.side_effect = [
        device_page,
        RuntimeError("product detail unavailable"),
        device_page,
        {"item": [{"productId": "lamp-pid", "deviceType": "Lamp"}]},
    ]
    manager = ImouDeviceManager(api_client)

    first = await manager.async_get_devices(fetch_ability_refs=False)
    second = await manager.async_get_devices(fetch_ability_refs=False)

    assert first[0].product_device_type is None
    assert second[0].product_device_type == "Lamp"
    assert "product detail unavailable" in caplog.text

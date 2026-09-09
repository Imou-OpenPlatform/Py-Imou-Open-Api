"""Tests for getStreamUrl live addresses."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    PARAM_CHANNEL_ID,
    PARAM_DEVICE_ID,
    PARAM_HD,
    PARAM_PRODUCT_ID,
    PARAM_STREAM_ID,
    PARAM_URL,
)
from pyimouapi.device import ImouDeviceManager
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

RTSP_URL = "rtsp://rtspproxy.example.com:8554/clip"


def camera(*, product_id: str | None = None) -> ImouHaDevice:
    """Return a camera channel, optionally as an IoT device."""
    ha_device = ImouHaDevice("dev1", "Cam", "Imou", "IPC", "1.0")
    ha_device.set_channel_id("0")
    if product_id is not None:
        ha_device.set_product_id(product_id)
    return ha_device


@pytest.mark.asyncio
async def test_rtsp_request_omits_product_id_for_paas_devices() -> None:
    """productId is only for IoT; a PaaS camera must not send it."""
    client = MagicMock()
    client.async_request_api = AsyncMock(return_value={PARAM_URL: RTSP_URL})
    manager = ImouDeviceManager(client)

    await manager.async_get_rtsp_stream_url("dev1", "0", 0)

    client.async_request_api.assert_awaited_once_with(
        "/openapi/getStreamUrl",
        {
            PARAM_DEVICE_ID: "dev1",
            PARAM_CHANNEL_ID: "0",
            PARAM_STREAM_ID: 0,
        },
    )


@pytest.mark.asyncio
async def test_rtsp_request_sends_product_id_for_iot_devices() -> None:
    """IoT cameras pass the product they were listed with."""
    client = MagicMock()
    client.async_request_api = AsyncMock(return_value={PARAM_URL: RTSP_URL})
    manager = ImouDeviceManager(client)

    await manager.async_get_rtsp_stream_url("dev1", "0", 1, "BF5W2WL4")

    client.async_request_api.assert_awaited_once_with(
        "/openapi/getStreamUrl",
        {
            PARAM_DEVICE_ID: "dev1",
            PARAM_CHANNEL_ID: "0",
            PARAM_STREAM_ID: 1,
            PARAM_PRODUCT_ID: "BF5W2WL4",
        },
    )


@pytest.mark.asyncio
async def test_live_stream_uses_get_stream_url_only() -> None:
    """Live view fetches getStreamUrl; it does not look up or create HLS."""
    delegate = MagicMock()
    delegate.async_get_stream_url = AsyncMock()
    delegate.async_create_stream_url = AsyncMock()
    delegate.async_get_rtsp_stream_url = AsyncMock(return_value={PARAM_URL: RTSP_URL})
    manager = ImouHaDeviceManager(delegate)

    assert (
        await manager.async_get_device_stream(camera(), PARAM_HD, "https") == RTSP_URL
    )

    delegate.async_get_stream_url.assert_not_awaited()
    delegate.async_create_stream_url.assert_not_awaited()
    delegate.async_get_rtsp_stream_url.assert_awaited_once_with("dev1", "0", 0, None)


@pytest.mark.asyncio
async def test_live_stream_passes_product_id_for_iot() -> None:
    """The request must include productId when the device has one."""
    delegate = MagicMock()
    delegate.async_get_rtsp_stream_url = AsyncMock(return_value={PARAM_URL: RTSP_URL})
    manager = ImouHaDeviceManager(delegate)

    await manager.async_get_device_stream(
        camera(product_id="BF5W2WL4"), PARAM_HD, "https"
    )

    delegate.async_get_rtsp_stream_url.assert_awaited_once_with(
        "dev1", "0", 0, "BF5W2WL4"
    )


@pytest.mark.asyncio
async def test_live_stream_uses_substream_for_sd() -> None:
    """SD live resolution maps to streamId 1."""
    delegate = MagicMock()
    delegate.async_get_rtsp_stream_url = AsyncMock(return_value={PARAM_URL: RTSP_URL})
    manager = ImouHaDeviceManager(delegate)

    await manager.async_get_device_stream(camera(), "SD", "https")

    delegate.async_get_rtsp_stream_url.assert_awaited_once_with("dev1", "0", 1, None)


@pytest.mark.asyncio
async def test_live_stream_without_url_reaches_the_caller() -> None:
    """An answer with no url must not look like a working stream."""
    delegate = MagicMock()
    delegate.async_get_rtsp_stream_url = AsyncMock(return_value={})
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(RequestFailedException, match="without a url"):
        await manager.async_get_device_stream(camera(), PARAM_HD, "https")

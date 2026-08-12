"""Tests for ImouHaDeviceManager.async_get_device_image."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import PARAM_URL
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

SNAP_URL = "https://cdn.example.com/snap.jpg"


def device() -> ImouHaDevice:
    """Return a camera device."""
    ha_device = ImouHaDevice("dev1", "Cam", "Imou", "IPC", "1.0")
    ha_device.set_channel_id("0")
    return ha_device


@pytest.mark.asyncio
async def test_image_is_downloaded_over_the_shared_session() -> None:
    """The snapshot download goes through the delegate, not a throwaway session."""
    delegate = MagicMock()
    delegate.async_get_device_snap = AsyncMock(return_value={PARAM_URL: SNAP_URL})
    delegate.async_download = AsyncMock(return_value=b"jpeg-bytes")
    manager = ImouHaDeviceManager(delegate)

    assert await manager.async_get_device_image(device(), 0) == b"jpeg-bytes"

    delegate.async_download.assert_awaited_once_with(SNAP_URL)


@pytest.mark.asyncio
async def test_failed_download_returns_none() -> None:
    """A failing download is logged and yields no image, as before."""
    delegate = MagicMock()
    delegate.async_get_device_snap = AsyncMock(return_value={PARAM_URL: SNAP_URL})
    delegate.async_download = AsyncMock(side_effect=RequestFailedException("boom"))
    manager = ImouHaDeviceManager(delegate)

    assert await manager.async_get_device_image(device(), 0) is None

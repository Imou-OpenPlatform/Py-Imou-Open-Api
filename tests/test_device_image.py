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
async def test_a_failed_download_reaches_the_caller() -> None:
    """The reason must survive to whoever can show it to a user.

    Swallowing it returned no image, which Home Assistant reports as "Unable to
    get image" with nothing to act on, and left the integration's translated
    camera error unreachable.
    """
    delegate = MagicMock()
    delegate.async_get_device_snap = AsyncMock(return_value={PARAM_URL: SNAP_URL})
    delegate.async_download = AsyncMock(side_effect=RequestFailedException("boom"))
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(RequestFailedException, match="boom"):
        await manager.async_get_device_image(device(), 0)


@pytest.mark.asyncio
async def test_a_snapshot_without_a_url_says_so() -> None:
    """A snap answer carrying no url used to surface as a bare KeyError."""
    delegate = MagicMock()
    delegate.async_get_device_snap = AsyncMock(return_value={})
    delegate.async_download = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(RequestFailedException, match="without a url"):
        await manager.async_get_device_image(device(), 0)

    delegate.async_download.assert_not_awaited()

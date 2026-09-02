"""Tests for waking a sleeping battery device before live view or a snapshot.

A battery camera answers ``DV1030`` while it sleeps. Reporting that to the user
leaves them nothing to do but open the Imou app, which is where the wake-up the
app sends comes from, so the call is made again after waking.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.const import PARAM_HD, PARAM_URL
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

RTSP_URL = "rtsp://rtspproxy.example.com:8554/clip"
SNAP_URL = "https://cdn.example.com/snap.jpg"
SLEEPING = "DV1030,device is sleeping"


def camera() -> ImouHaDevice:
    """Return a battery camera channel."""
    device = ImouHaDevice("dev1", "Cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    return device


@pytest.fixture(autouse=True)
def _no_wake_wait():
    """Skip the wait the device needs, so the tests do not pay for it."""
    with patch("pyimouapi.ha_device.asyncio.sleep", AsyncMock()):
        yield


async def test_a_sleeping_device_is_woken_before_the_stream_is_asked_again() -> None:
    """The user pressing play is what should wake the camera."""
    delegate = MagicMock()
    delegate.async_get_rtsp_stream_url = AsyncMock(
        side_effect=[RequestFailedException(SLEEPING), {PARAM_URL: RTSP_URL}]
    )
    delegate.async_wake_up_device = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    assert await manager.async_get_device_stream(camera(), PARAM_HD) == RTSP_URL

    delegate.async_wake_up_device.assert_awaited_once_with("dev1")
    assert delegate.async_get_rtsp_stream_url.await_count == 2


async def test_a_sleeping_device_is_woken_before_the_snapshot_is_asked_again() -> None:
    """A snapshot is worth the same wake-up as live view."""
    delegate = MagicMock()
    delegate.async_get_device_snap = AsyncMock(
        side_effect=[RequestFailedException(SLEEPING), {PARAM_URL: SNAP_URL}]
    )
    delegate.async_wake_up_device = AsyncMock()
    delegate.async_download = AsyncMock(return_value=b"jpeg-bytes")
    manager = ImouHaDeviceManager(delegate)

    assert await manager.async_get_device_image(camera(), 0) == b"jpeg-bytes"

    delegate.async_wake_up_device.assert_awaited_once_with("dev1")
    delegate.async_download.assert_awaited_once_with(SNAP_URL)


async def test_a_device_still_asleep_after_the_wake_up_says_so() -> None:
    """One retry, then the reason reaches whoever can show it to the user."""
    delegate = MagicMock()
    delegate.async_get_rtsp_stream_url = AsyncMock(
        side_effect=RequestFailedException(SLEEPING)
    )
    delegate.async_wake_up_device = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(RequestFailedException, match="DV1030"):
        await manager.async_get_device_stream(camera(), PARAM_HD)

    assert delegate.async_wake_up_device.await_count == 1
    assert delegate.async_get_rtsp_stream_url.await_count == 2


async def test_any_other_failure_is_not_a_wake_up() -> None:
    """An offline device, or a refused call, must not spend a wake-up call."""
    delegate = MagicMock()
    delegate.async_get_rtsp_stream_url = AsyncMock(
        side_effect=RequestFailedException("DV1007,device is offline")
    )
    delegate.async_wake_up_device = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(RequestFailedException, match="DV1007"):
        await manager.async_get_device_stream(camera(), PARAM_HD)

    delegate.async_wake_up_device.assert_not_awaited()
    assert delegate.async_get_rtsp_stream_url.await_count == 1

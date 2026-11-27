"""getAlarmMessageStatistics request parameters."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.const import API_ENDPOINT_GET_ALARM_MESSAGE_STATISTICS
from pyimouapi.device import ImouChannel, ImouDevice, ImouDeviceManager
from pyimouapi.ha_device import ImouHaDeviceManager


class _Client:
    def __init__(self) -> None:
        self.async_request_api = AsyncMock(return_value={})


def _camera() -> ImouDevice:
    device = ImouDevice("SN1", "Gate", "1", "Imou", "IPC")
    device.set_is_multi(True)
    device.set_channels(
        [
            ImouChannel("0", "Lens 1", "online", ""),
            ImouChannel("1", "Lens 2", "online", ""),
        ]
    )
    return device


def test_dual_camera_reports_two_views() -> None:
    camera = _camera()
    assert camera.multi_view == 2
    assert ImouHaDeviceManager.build_device(camera).view_count == 2


def test_recorder_stays_one_view() -> None:
    device = ImouDevice("NVR1", "NVR", "1", "Imou", "NVR")
    device.set_channel_number(8)
    device.set_channels(
        [ImouChannel(str(index), f"Ch {index}", "online", "") for index in range(8)]
    )
    assert device.multi_view == 1


@pytest.mark.asyncio
async def test_statistics_request_sends_views_and_four_message_samples() -> None:
    client = _Client()
    manager = ImouDeviceManager(client)  # type: ignore[arg-type]
    await manager.async_get_alarm_message_statistics(
        "SN1",
        "0",
        start_day="20260427",
        end_day="20260428",
        multi_view=2,
    )
    endpoint, params = client.async_request_api.await_args.args
    assert endpoint == API_ENDPOINT_GET_ALARM_MESSAGE_STATISTICS
    assert params["multiView"] == "2"
    assert params["msgAnalysis"]["analysisHourInterval"] == 2
    labels = params["msgAnalysis"]["labelTime"]
    assert [row["labelType"] for row in labels] == [
        "humanAlarm",
        "carAlarm",
        "petAlarm",
        "packageAlarm",
    ]
    assert {row["count"] for row in labels} == {10}
    assert {row["sortType"] for row in labels} == {"desc"}
    windows = params["riskStatement"]
    assert windows[0] == {"startHour": "00", "endHour": "02"}
    assert windows[-1] == {"startHour": "22", "endHour": "24"}
    assert len(windows) == 12

"""searchAiAlarmMessageByPage request parameters."""

from unittest.mock import AsyncMock

import pytest
from pyimouapi.device import ImouDeviceManager


class _Client:
    def __init__(self, api_url: str) -> None:
        self.api_url = api_url
        self.async_request_api = AsyncMock(return_value={})


async def _search(api_url: str) -> dict:
    client = _Client(api_url)
    manager = ImouDeviceManager(client)  # type: ignore[arg-type]
    await manager.async_search_ai_alarm_message(
        "8K11FAAPAZ9DAA1",
        "0",
        search_content="有人",
        begin_time="2026-11-16 00:00:00",
        end_time="2026-11-16 23:59:59",
    )
    return client.async_request_api.await_args.args[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_url",
    ["openapi-sg.easy4ip.com:443", "openapi.lechange.cn"],
)
async def test_search_sends_channel_ids(api_url: str) -> None:
    """Both gateways take channelIds."""
    params = await _search(api_url)
    assert params["channelIds"] == [0]
    assert "channelId" not in params
    assert params["searchContent"] == "有人"
    assert params["beginTime"] == "2026-11-16 00:00:00"


@pytest.mark.asyncio
async def test_later_page_sends_the_index_only() -> None:
    """Pages after the first send nextIndexId and leave the time window out."""
    client = _Client("openapi-sg.easy4ip.com:443")
    manager = ImouDeviceManager(client)  # type: ignore[arg-type]
    await manager.async_search_ai_alarm_message(
        "8K11FAAPAZ9DAA1",
        "0",
        search_content="有人",
        begin_time="2026-11-16 00:00:00",
        end_time="2026-11-16 23:59:59",
        next_index_id="cursor-2",
    )
    params = client.async_request_api.await_args.args[1]
    assert params["nextIndexId"] == "cursor-2"
    assert "beginTime" not in params
    assert "endTime" not in params

"""Tests for ImouDeviceManager.async_get_devices listing and channel fields."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.const import (
    API_ENDPOINT_LIST_DEVICE_DETAILS,
    API_ENDPOINT_LIST_PRODUCT_DETAIL,
    PARAM_AI_INSIGHT_STATUS,
    PARAM_BRAND,
    PARAM_CHANNEL_ID,
    PARAM_CHANNEL_LIST,
    PARAM_CHANNEL_NUM,
    PARAM_COUNT,
    PARAM_CS_STATUS,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_LIST,
    PARAM_DEVICE_MODEL,
    PARAM_DEVICE_NAME,
    PARAM_DEVICE_STATUS,
    PARAM_PAGE,
    PARAM_PRODUCT_ID,
    PARAM_PRODUCT_IDS,
)
from pyimouapi.device import ImouDeviceManager


def make_device(device_id: str, product_id: str | None = None) -> dict:
    """Build one deviceList entry."""
    entry = {
        PARAM_DEVICE_ID: device_id,
        PARAM_DEVICE_NAME: f"Device {device_id}",
        PARAM_DEVICE_STATUS: "1",
        PARAM_BRAND: "Imou",
        PARAM_DEVICE_MODEL: "IPC-A1",
    }
    if product_id is not None:
        entry[PARAM_PRODUCT_ID] = product_id
    return entry


def make_manager(pages: dict[int, dict]) -> ImouDeviceManager:
    """Build a manager whose device list returns the given pages."""

    async def request(endpoint: str, params: dict) -> dict:
        if endpoint == API_ENDPOINT_LIST_PRODUCT_DETAIL:
            return {
                "item": [
                    {"productId": product_id, "deviceType": "IPC"}
                    for product_id in params[PARAM_PRODUCT_IDS]
                ]
            }
        assert endpoint == API_ENDPOINT_LIST_DEVICE_DETAILS
        return pages[params[PARAM_PAGE]]

    client = MagicMock()
    client.async_request_api = AsyncMock(side_effect=request)
    return ImouDeviceManager(client)


@pytest.mark.asyncio
async def test_pagination_stops_on_a_short_page_whatever_count_means() -> None:
    """Paging must end when a page runs out, not when a count field says so.

    ``count`` is read as the number of entries on this page, but the API may
    well mean the total across all pages. Under that reading an account holding
    exactly one full page would ask for page after page forever, so the decision
    is based on what actually came back.
    """
    page1 = [make_device(f"dev{i}", f"prod{i}") for i in range(10)]
    manager = make_manager(
        {
            1: {PARAM_COUNT: 10, PARAM_DEVICE_LIST: page1},
            2: {PARAM_COUNT: 10, PARAM_DEVICE_LIST: []},
        }
    )

    result = await manager.async_get_devices()

    assert len(result) == 10


@pytest.mark.asyncio
async def test_pagination_keeps_devices_from_later_pages() -> None:
    page1 = [make_device(f"dev{i}", f"prod{i}") for i in range(10)]
    page2 = [make_device("dev10", "prod10")]
    manager = make_manager(
        {
            1: {PARAM_COUNT: 10, PARAM_DEVICE_LIST: page1},
            2: {PARAM_COUNT: 1, PARAM_DEVICE_LIST: page2},
        }
    )

    result = await manager.async_get_devices()

    assert [device.device_id for device in result] == [
        *(f"dev{i}" for i in range(10)),
        "dev10",
    ]


@pytest.mark.asyncio
async def test_channel_list_tolerates_missing_name_and_status() -> None:
    """Some device details omit channelName / channelStatus on a channel."""
    entry = make_device("cam1")
    entry[PARAM_CHANNEL_NUM] = 1
    entry[PARAM_CHANNEL_LIST] = [{PARAM_CHANNEL_ID: 0, "csstatus": "using"}]
    manager = make_manager({1: {PARAM_COUNT: 1, PARAM_DEVICE_LIST: [entry]}})

    result = await manager.async_get_devices()

    assert len(result) == 1
    assert len(result[0].channels) == 1
    channel = result[0].channels[0]
    assert channel.channel_id == "0"
    assert channel.channel_name == ""
    assert channel.channel_status == ""
    assert channel.cs_status == "using"


@pytest.mark.asyncio
async def test_channel_cs_status_uses_documented_field() -> None:
    """device.detail.page reports cloud storage as channelList[].csStatus."""
    entry = make_device("cam1")
    entry[PARAM_CHANNEL_LIST] = [
        {
            PARAM_CHANNEL_ID: "0",
            PARAM_CS_STATUS: "expired",
            PARAM_AI_INSIGHT_STATUS: "on",
        }
    ]
    manager = make_manager({1: {PARAM_COUNT: 1, PARAM_DEVICE_LIST: [entry]}})

    result = await manager.async_get_devices()

    assert result[0].channels[0].cs_status == "expired"
    assert result[0].channels[0].ai_insight_status == "on"


@pytest.mark.asyncio
async def test_channel_inherits_device_ai_insight_status() -> None:
    """A device-level aiInsightStatus applies when the channel omits it."""
    entry = make_device("8K11FAAPAZ9DAA1")
    entry["aiInsightStatus"] = "using"
    entry[PARAM_CHANNEL_LIST] = [{PARAM_CHANNEL_ID: "0"}]
    manager = make_manager({1: {PARAM_COUNT: 1, PARAM_DEVICE_LIST: [entry]}})

    result = await manager.async_get_devices()

    assert result[0].channels[0].ai_insight_status == "using"


@pytest.mark.asyncio
async def test_access_type_keeps_paas_when_the_field_is_not_text() -> None:
    """A missing or null accessType stays PaaS. A real value is kept."""
    iot = make_device("iot-1")
    iot["accessType"] = " IoT "
    blank = make_device("blank-1")
    blank["accessType"] = None
    manager = make_manager({1: {PARAM_COUNT: 2, PARAM_DEVICE_LIST: [iot, blank]}})

    result = await manager.async_get_devices()

    assert result[0].access_type == "IoT"
    assert result[1].access_type == "PaaS"


@pytest.mark.asyncio
async def test_detail_page_keeps_device_and_channel_capability_ids() -> None:
    entry = make_device("CAM1", "PID1")
    entry["capabilityIds"] = ["device.reboot.execute", "storage.local.capacity"]
    entry[PARAM_CHANNEL_LIST] = [
        {
            PARAM_CHANNEL_ID: 0,
            "channelName": "Main",
            "channelStatus": "online",
            "capabilityIds": ["detection.motion.enabled", 1, ""],
        }
    ]
    entry[PARAM_CHANNEL_NUM] = 1
    manager = make_manager({1: {PARAM_DEVICE_LIST: [entry]}})

    devices = await manager.async_get_devices()

    assert devices[0].capability_ids == (
        "device.reboot.execute",
        "storage.local.capacity",
    )
    assert devices[0].channels[0].capability_ids == ("detection.motion.enabled",)


@pytest.mark.asyncio
async def test_device_rows_without_an_id_are_skipped() -> None:
    """One malformed row must not abort the whole account listing."""
    entry = make_device("good")
    manager = make_manager(
        {
            1: {
                PARAM_COUNT: 3,
                PARAM_DEVICE_LIST: [{}, {"deviceName": "no id"}, entry],
            }
        }
    )

    result = await manager.async_get_devices()

    assert [device.device_id for device in result] == ["good"]


@pytest.mark.asyncio
async def test_device_paging_has_a_hard_limit() -> None:
    """A looping page contract must not walk pages forever."""
    manager = make_manager({})

    assert await manager._async_get_devices(51, 10) == []

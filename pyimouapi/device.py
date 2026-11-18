from __future__ import annotations

import asyncio
import logging
from collections.abc import Collection
from dataclasses import dataclass, replace
from datetime import datetime
from math import ceil
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .local_record import LocalRecordSegment

from .const import (
    API_ENDPOINT_BIND_DEVICE,
    API_ENDPOINT_DEVICE_SNAP_DETECT,
    API_ENDPOINT_GET_ALARM_MESSAGE_STATISTICS,
    API_ENDPOINT_GET_STREAM_URL,
    API_ENDPOINT_LIST_DEVICE_DETAILS,
    API_ENDPOINT_LIST_PRODUCT_DETAIL,
    API_ENDPOINT_QUERY_CLOUD_RECORD_BITMAP,
    API_ENDPOINT_QUERY_CLOUD_RECORDS,
    API_ENDPOINT_SEARCH_AI_ALARM_MESSAGE,
    API_ENDPOINT_SET_DEVICE_SNAP,
    API_V2_DEVICE_DETAIL_LIST,
    API_V2_DEVICE_REBOOT_EXECUTE,
    PARAM_ACCESS_TYPE,
    PARAM_AI_INSIGHT_STATUS,
    PARAM_BRAND,
    PARAM_CAPABILITY_IDS,
    PARAM_CHANNEL_ABILITY,
    PARAM_CHANNEL_ID,
    PARAM_CHANNEL_LIST,
    PARAM_CHANNEL_NAME,
    PARAM_CHANNEL_NUM,
    PARAM_CHANNEL_STATUS,
    PARAM_CODE,
    PARAM_CS_STATUS,
    PARAM_DEVICE_ABILITY,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_LIST,
    PARAM_DEVICE_MODEL,
    PARAM_DEVICE_NAME,
    PARAM_DEVICE_STATUS,
    PARAM_DEVICE_VERSION,
    PARAM_MULTI_FLAG,
    PARAM_PAGE,
    PARAM_PAGE_SIZE,
    PARAM_PARENT_DEVICE_ID,
    PARAM_PARENT_PRODUCT_ID,
    PARAM_PRODUCT_ID,
    PARAM_PRODUCT_IDS,
    PARAM_STREAM_ID,
)
from .openapi import ImouOpenApiClient
from .product_detail import ProductDetail, parse_product_details

_LOGGER = logging.getLogger(__name__)

_MSG_ANALYSIS_LABELS = ("humanAlarm", "carAlarm", "petAlarm", "packageAlarm")
_MSG_ANALYSIS = {
    "analysisHourInterval": 2,
    "labelTime": [
        {"labelType": label, "count": 10, "sortType": "desc"}
        for label in _MSG_ANALYSIS_LABELS
    ],
}
_RISK_WINDOWS = [
    {"startHour": f"{hour:02d}", "endHour": f"{hour + 2:02d}"}
    for hour in range(0, 24, 2)
]


def _multi_view_param(multi_view: int) -> str:
    """multiView is a string lens count. Missing or invalid stays at one."""
    try:
        count = int(multi_view)
    except (TypeError, ValueError):
        return "1"
    return str(count if count > 0 else 1)


_RECORD_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_record_time(value: str) -> datetime | None:
    """Parse the device-local time format used by cloud-record APIs."""
    try:
        parsed = datetime.strptime(value, _RECORD_TIME_FORMAT)
    except ValueError:
        return None
    return parsed if parsed.strftime(_RECORD_TIME_FORMAT) == value else None


def _named_field(payload: dict[str, Any], name: str) -> str | None:
    """Read a status field, ignoring key case and blank values."""
    if not isinstance(payload, dict):
        return None
    wanted = name.lower()
    raw = None
    for key, value in payload.items():
        if str(key).lower() == wanted:
            raw = value
            break
    if isinstance(raw, dict):
        raw = raw.get("status", raw.get("value"))
    if isinstance(raw, list) and len(raw) == 1:
        raw = raw[0]
    if raw in (None, ""):
        return None
    text = str(raw).strip()
    return text or None


def _text_or_default(value: Any, default: str = "unknown") -> str:
    """Return a string field, treating JSON null and blanks as the default."""
    if isinstance(value, str) and value:
        return value
    return default


def compose_iot_device_id(
    device_id: str,
    parent_device_id: str | None,
    parent_product_id: str | None,
) -> str:
    """Return the id an iot device is addressed by.

    An accessory paired to a gateway is reached through both of its parent's
    ids. The API sends the pair or neither, so half of it identifies nothing and
    the device is addressed on its own instead.
    """
    if parent_device_id and parent_product_id:
        return f"{device_id}_{parent_device_id}_{parent_product_id}"
    return device_id


@dataclass(frozen=True)
class ImouDeviceSummary:
    device_id: str
    name: str
    model: str
    status: str  # "0" offline, "1" online


def capability_ids_from_raw(raw: object) -> tuple[str, ...]:
    """Keep non-blank string ids. Anything else is an empty tuple."""
    if not isinstance(raw, list):
        return ()
    return tuple(item.strip() for item in raw if isinstance(item, str) and item.strip())


class ImouChannel:
    def __init__(
        self,
        channel_id: str,
        channel_name: str,
        channel_status: str,
        channel_ability: str,
    ):
        self._channel_id = channel_id
        self._channel_name = channel_name
        self._channel_status = channel_status
        self._channel_ability = channel_ability
        self._capability_ids: tuple[str, ...] = ()
        self._cs_status: str | None = None
        self._ai_insight_status: str | None = None

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def channel_name(self) -> str:
        return self._channel_name

    @property
    def channel_status(self) -> str:
        return self._channel_status

    @property
    def channel_ability(self) -> str:
        return self._channel_ability

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return self._capability_ids

    def set_capability_ids(self, capability_ids: tuple[str, ...]) -> None:
        self._capability_ids = capability_ids

    @property
    def cs_status(self) -> str | None:
        """Cloud storage status from the device list, such as ``using``."""
        return self._cs_status

    def set_cs_status(self, cs_status: str | None) -> None:
        self._cs_status = cs_status

    @property
    def ai_insight_status(self) -> str | None:
        """AI Insight status from the device list, such as ``on``."""
        return self._ai_insight_status

    def set_ai_insight_status(self, ai_insight_status: str | None) -> None:
        self._ai_insight_status = ai_insight_status


class ImouDevice:
    def __init__(
        self,
        device_id: str,
        device_name: str,
        device_status: str,
        brand: str,
        device_model: str,
    ):
        self._device_id = device_id
        self._device_name = device_name
        self._device_status = device_status
        self._device_ability = "unknown"
        self._brand = brand
        self._device_model = device_model
        self._device_version = "unknown"
        self._channel_number = 0
        self._channels: list[ImouChannel] = []
        self._product_id: str | None = None
        self._product_device_type: str | None = None
        self._parent_product_id: str | None = None
        self._parent_device_id: str | None = None
        self._is_multi = False
        self._is_ipc = False
        self._access_type = "PaaS"
        self._play_token_v2: str | None = None
        self._capability_ids: tuple[str, ...] = ()

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def device_status(self) -> str:
        return self._device_status

    @property
    def channels(self) -> list[ImouChannel]:
        return self._channels

    @property
    def device_ability(self) -> str:
        return self._device_ability

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return self._capability_ids

    def set_capability_ids(self, capability_ids: tuple[str, ...]) -> None:
        self._capability_ids = capability_ids

    @property
    def brand(self) -> str:
        return self._brand

    @property
    def device_model(self) -> str:
        return self._device_model

    @property
    def device_version(self) -> str:
        return self._device_version

    @property
    def product_id(self) -> str | None:
        return self._product_id

    @property
    def product_device_type(self) -> str | None:
        return self._product_device_type

    @property
    def parent_product_id(self) -> str | None:
        return self._parent_product_id

    @property
    def parent_device_id(self) -> str | None:
        return self._parent_device_id

    @property
    def channel_number(self) -> int:
        return self._channel_number

    @property
    def is_ipc(self) -> bool:
        return (
            self._channel_number is not None and self._channel_number == 1
        ) or self._is_multi

    @property
    def multi_view(self) -> int:
        """Lens count for a camera. Recorders stay at one view."""
        if not self.is_ipc:
            return 1
        raw = len(self._channels) or self._channel_number or 1
        try:
            count = int(raw)
        except (TypeError, ValueError):
            return 1
        return count if count > 0 else 1

    @property
    def access_type(self) -> str:
        return self._access_type

    def set_product_id(self, product_id: str) -> None:
        self._product_id = product_id

    def set_product_device_type(self, product_device_type: str | None) -> None:
        self._product_device_type = product_device_type

    def set_channels(self, channels: list[ImouChannel]) -> None:
        self._channels = channels

    def set_channel_number(self, channel_number: int):
        self._channel_number = channel_number

    def set_device_ability(self, device_ability: str):
        self._device_ability = device_ability

    @property
    def play_token_v2(self) -> str | None:
        """Encrypted play credential from the device list, if the cloud sent one."""
        return self._play_token_v2

    def set_play_token_v2(self, play_token_v2: str | None) -> None:
        self._play_token_v2 = play_token_v2 or None

    def set_device_version(self, device_version: str):
        self._device_version = device_version

    def set_parent_product_id(self, parent_product_id: str):
        self._parent_product_id = parent_product_id

    def set_parent_device_id(self, parent_device_id: str):
        self._parent_device_id = parent_device_id

    def set_is_multi(self, is_multi: bool):
        self._is_multi = is_multi

    def set_access_type(self, access_type: str):
        self._access_type = access_type


def _search_channel_param(channel_id: str) -> dict[str, Any]:
    """searchAiAlarmMessageByPage takes channelIds on both gateways."""
    channel = int(channel_id) if str(channel_id).isdigit() else str(channel_id)
    return {"channelIds": [channel]}


class ImouDeviceManager:
    def __init__(self, imou_api_client: ImouOpenApiClient):
        self._imou_api_client = imou_api_client
        self._product_details: dict[str, ProductDetail] = {}

    @property
    def api_client(self) -> ImouOpenApiClient:
        return self._imou_api_client

    async def async_close(self) -> None:
        """Close the underlying Open API HTTP session."""
        await self._imou_api_client.async_close()

    async def async_download(self, url: str) -> bytes:
        """GET a binary payload over the shared Open API session."""
        return await self._imou_api_client.async_download(url)

    async def async_get_product_details(
        self, product_ids: Collection[str]
    ) -> dict[str, ProductDetail]:
        """Return cached product details, fetching uncached ids in one request."""
        requested_ids = {product_id for product_id in product_ids if product_id}
        missing_ids = sorted(requested_ids - self._product_details.keys())
        if missing_ids:
            data = await self._imou_api_client.async_request_api(
                API_ENDPOINT_LIST_PRODUCT_DETAIL,
                {PARAM_PRODUCT_IDS: missing_ids},
            )
            self._product_details.update(parse_product_details(data))
        return {
            product_id: self._product_details[product_id]
            for product_id in requested_ids
            if product_id in self._product_details
        }

    async def async_get_devices(
        self,
        page: int = 1,
        page_size: int = 10,
    ) -> list[ImouDevice]:
        """Return the account device list.

        Entities are registered later from page capability ids.
        """
        devices = await self._async_get_devices(page, page_size)
        product_ids = {
            device.product_id for device in devices if device.product_id is not None
        }
        if product_ids:
            try:
                details = await self.async_get_product_details(product_ids)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.warning("Could not read product details: %s", err)
            else:
                for device in devices:
                    if (
                        device.product_id is not None
                        and (detail := details.get(device.product_id)) is not None
                    ):
                        device.set_product_device_type(detail.device_type)
        return devices

    async def _async_get_devices(
        self,
        page: int,
        page_size: int,
    ) -> list[ImouDevice]:
        params = {
            PARAM_PAGE: page,
            PARAM_PAGE_SIZE: page_size,
        }
        data = await self._imou_api_client.async_request_api(
            API_ENDPOINT_LIST_DEVICE_DETAILS, params
        )
        device_list = data.get(PARAM_DEVICE_LIST) if isinstance(data, dict) else None
        if not isinstance(device_list, list) or not device_list:
            return []
        devices = []
        for device in device_list:
            device_id = device[PARAM_DEVICE_ID]
            device_name = device[PARAM_DEVICE_NAME]
            device_status = device[PARAM_DEVICE_STATUS]
            brand = device[PARAM_BRAND]
            device_model = device.get(PARAM_DEVICE_MODEL, "unknown")
            imou_device = ImouDevice(
                device_id, device_name, device_status, brand, device_model
            )
            imou_device.set_capability_ids(
                capability_ids_from_raw(device.get(PARAM_CAPABILITY_IDS))
            )
            if PARAM_DEVICE_ABILITY in device:
                imou_device.set_device_ability(
                    _text_or_default(device[PARAM_DEVICE_ABILITY])
                )
            if PARAM_DEVICE_VERSION in device:
                imou_device.set_device_version(device[PARAM_DEVICE_VERSION])
            if PARAM_PARENT_PRODUCT_ID in device:
                imou_device.set_parent_product_id(device[PARAM_PARENT_PRODUCT_ID])
            if PARAM_PARENT_DEVICE_ID in device:
                imou_device.set_parent_device_id(device[PARAM_PARENT_DEVICE_ID])
            if PARAM_CHANNEL_NUM in device:
                imou_device.set_channel_number(device[PARAM_CHANNEL_NUM])
            if PARAM_MULTI_FLAG in device:
                imou_device.set_is_multi(device[PARAM_MULTI_FLAG])
            access_type = device.get(PARAM_ACCESS_TYPE)
            if isinstance(access_type, str) and access_type.strip():
                imou_device.set_access_type(access_type.strip())
            play_token = device.get("playTokenV2")
            if isinstance(play_token, str) and play_token:
                imou_device.set_play_token_v2(play_token)
            if PARAM_CHANNEL_LIST in device:
                channel_list = device[PARAM_CHANNEL_LIST] or []
                if not isinstance(channel_list, list):
                    channel_list = []
                channels = []
                for channel in channel_list:
                    channel_id = (
                        str(channel[PARAM_CHANNEL_ID])
                        if isinstance(channel[PARAM_CHANNEL_ID], int)
                        else channel[PARAM_CHANNEL_ID]
                    )
                    channel_name = channel.get(PARAM_CHANNEL_NAME) or ""
                    channel_status = channel.get(PARAM_CHANNEL_STATUS) or ""
                    channel_ability = _text_or_default(
                        channel.get(PARAM_CHANNEL_ABILITY)
                    )
                    parsed = ImouChannel(
                        channel_id, channel_name, channel_status, channel_ability
                    )
                    parsed.set_capability_ids(
                        capability_ids_from_raw(channel.get(PARAM_CAPABILITY_IDS))
                    )
                    raw_cs = _named_field(channel, PARAM_CS_STATUS)
                    if raw_cs is None:
                        raw_cs = _named_field(device, PARAM_CS_STATUS)
                    if raw_cs is not None:
                        parsed.set_cs_status(raw_cs)
                    raw_insight = _named_field(channel, PARAM_AI_INSIGHT_STATUS)
                    if raw_insight is None:
                        raw_insight = _named_field(device, PARAM_AI_INSIGHT_STATUS)
                    if raw_insight is not None:
                        parsed.set_ai_insight_status(raw_insight)
                    _LOGGER.debug(
                        "device %s ch%s csStatus=%s aiInsightStatus=%s",
                        device_id,
                        channel_id,
                        parsed.cs_status,
                        parsed.ai_insight_status,
                    )
                    channels.append(parsed)
                imou_device.set_channels(channels)
            if PARAM_PRODUCT_ID in device:
                imou_device.set_product_id(device[PARAM_PRODUCT_ID])
            devices.append(imou_device)
        # A full page may have more behind it. This counts what actually arrived
        # rather than trusting `count`, which stops the paging either way: were
        # that field the account total instead of this page's size, an account
        # holding an exact multiple of page_size would page on forever.
        if len(device_list) >= page_size:
            devices.extend(await self._async_get_devices(page + 1, page_size))
        return devices

    async def async_get_device_summaries(
        self, page: int = 1, page_size: int = 50
    ) -> list[ImouDeviceSummary]:
        params = {
            PARAM_PAGE: page,
            PARAM_PAGE_SIZE: page_size,
        }
        data = await self._imou_api_client.async_request_api(
            API_ENDPOINT_LIST_DEVICE_DETAILS, params
        )
        device_list = data.get(PARAM_DEVICE_LIST) if isinstance(data, dict) else None
        if not isinstance(device_list, list) or not device_list:
            return []
        summaries: list[ImouDeviceSummary] = []
        for device in device_list:
            device_id = device.get(PARAM_DEVICE_ID)
            if not device_id:
                continue
            name = device.get(PARAM_DEVICE_NAME) or device_id
            model = device.get(PARAM_DEVICE_MODEL, "")
            status = str(device.get(PARAM_DEVICE_STATUS, ""))
            summaries.append(
                ImouDeviceSummary(
                    device_id=device_id,
                    name=name,
                    model=model,
                    status=status,
                )
            )
        # Counts what arrived rather than trusting `count`; see async_get_devices.
        if len(device_list) >= page_size:
            summaries.extend(await self.async_get_device_summaries(page + 1, page_size))
        return summaries

    async def async_list_device_details(
        self, device_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Batch device detail: status, cloud storage, and AI Insight."""
        rows: list[dict[str, Any]] = []
        unique = list(dict.fromkeys(device_ids))
        for start in range(0, len(unique), 50):
            chunk = unique[start : start + 50]
            data = await self._imou_api_client.async_request_api(
                API_V2_DEVICE_DETAIL_LIST,
                {
                    PARAM_DEVICE_LIST: [
                        {PARAM_DEVICE_ID: device_id} for device_id in chunk
                    ]
                },
            )
            listed = data.get(PARAM_DEVICE_LIST) if isinstance(data, dict) else None
            if isinstance(listed, list):
                rows.extend(item for item in listed if isinstance(item, dict))
        return rows

    async def async_restart_device(
        self, device_id: str, product_id: str | None = None
    ) -> None:
        """reboot device via device.reboot.execute"""
        params: dict[str, Any] = {PARAM_DEVICE_ID: device_id}
        if product_id:
            params[PARAM_PRODUCT_ID] = product_id
        await self._imou_api_client.async_request_api(
            API_V2_DEVICE_REBOOT_EXECUTE, params
        )

    async def async_bind_device(self, device_id: str, code: str) -> None:
        """Bind device to the open-platform account (bindDevice)."""
        params = {PARAM_DEVICE_ID: device_id, PARAM_CODE: code}
        await self._imou_api_client.async_request_api(API_ENDPOINT_BIND_DEVICE, params)

    async def async_get_rtsp_stream_url(
        self,
        device_id: str,
        channel_id: str | None,
        stream_id: int = 0,
        product_id: str | None = None,
    ) -> dict[str, Any]:
        """Obtain a short-lived cloud RTSP URL (getStreamUrl).

        ``productId`` is only sent for IoT devices that have one.
        """
        params: dict[str, Any] = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_STREAM_ID: stream_id,
        }
        if product_id:
            params[PARAM_PRODUCT_ID] = product_id
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_STREAM_URL, params
        )

    async def async_get_device_snap(
        self, device_id: str, channel_id: str | None
    ) -> dict[str, Any]:
        params = {PARAM_DEVICE_ID: device_id, PARAM_CHANNEL_ID: channel_id}
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_SET_DEVICE_SNAP, params
        )

    async def async_device_snap_detect(
        self, device_id: str, channel_id: str | None
    ) -> dict[str, Any]:
        """Capture a still and run on-device detection (human / vehicle / animal)."""
        params = {PARAM_DEVICE_ID: device_id, PARAM_CHANNEL_ID: channel_id}
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_DEVICE_SNAP_DETECT, params
        )

    async def async_query_cloud_record_bitmap(
        self, device_id: str, channel_id: str, *, year: int, month: int
    ) -> dict[str, Any]:
        """Monthly cloud-recording presence bitmap."""
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            "year": year,
            "month": month,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_QUERY_CLOUD_RECORD_BITMAP, params
        )

    async def async_query_cloud_records(
        self,
        device_id: str,
        channel_id: str,
        *,
        begin_time: str,
        end_time: str,
        query_range: str | None = "1-100",
        count: int | None = None,
    ) -> dict[str, Any]:
        """List cloud recording segments in a time window."""
        params: dict[str, Any] = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            "beginTime": begin_time,
            "endTime": end_time,
        }
        if count is not None:
            params["count"] = max(1, min(100, int(count)))
        elif query_range:
            params["queryRange"] = query_range
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_QUERY_CLOUD_RECORDS, params
        )

    async def async_list_cloud_record_segments(
        self,
        device_id: str,
        channel_id: str,
        *,
        begin_time: str,
        end_time: str,
    ) -> list:
        """List all cloud segments in a window, paging queryCloudRecords."""
        from .cloud_record import RECORD_QUERY_PAGE_SIZE, parse_cloud_records_data

        cursor_time = _parse_record_time(begin_time)
        window_end_time = _parse_record_time(end_time)
        if (
            cursor_time is None
            or window_end_time is None
            or cursor_time >= window_end_time
        ):
            return []

        segments: list = []
        seen: set[str | tuple[str, str, str]] = set()
        cursor_begin = begin_time
        max_pages = 1000
        for _page in range(max_pages):
            data = await self.async_query_cloud_records(
                device_id,
                channel_id,
                begin_time=cursor_begin,
                end_time=end_time,
                count=RECORD_QUERY_PAGE_SIZE,
            )
            records = data.get("records") if isinstance(data, dict) else None
            raw_records = records if isinstance(records, list) else []
            batch: list[tuple[Any, str]] = []
            for item in raw_records:
                file_name = ""
                parsed = parse_cloud_records_data({"records": [item]})
                if isinstance(item, dict):
                    file_name = str(item.get("fileName") or "").strip()
                    if not parsed and not str(item.get("recordId") or "").strip():
                        item_with_id = dict(item)
                        item_with_id["recordId"] = "__missing_record_id__"
                        parsed = [
                            replace(segment, record_id="")
                            for segment in parse_cloud_records_data(
                                {"records": [item_with_id]}
                            )
                        ]
                batch.extend((segment, file_name) for segment in parsed)

            for segment, file_name in batch:
                identity: str | tuple[str, str, str]
                if segment.record_id:
                    identity = segment.record_id
                else:
                    identity = (
                        segment.begin_time,
                        segment.end_time,
                        file_name,
                    )
                if identity not in seen:
                    seen.add(identity)
                    segments.append(segment)

            if len(raw_records) < RECORD_QUERY_PAGE_SIZE:
                break

            usable_end_times: list[tuple[datetime, str]] = []
            for segment, _file_name in batch:
                parsed_end_time = _parse_record_time(segment.end_time)
                if parsed_end_time is not None:
                    usable_end_times.append((parsed_end_time, segment.end_time))
            if not usable_end_times:
                _LOGGER.warning(
                    "Cloud record page has no usable end time for %s", device_id
                )
                break
            next_cursor_time, next_cursor = max(usable_end_times)
            if next_cursor_time <= cursor_time:
                _LOGGER.warning("Cloud record cursor did not advance for %s", device_id)
                break
            if next_cursor_time >= window_end_time:
                break
            cursor_begin = next_cursor
            cursor_time = next_cursor_time
        else:
            _LOGGER.warning(
                "Cloud record pagination reached the %d-page safety limit for %s",
                max_pages,
                device_id,
            )
        return segments

    async def async_create_device_record_hls(
        self,
        device_id: str,
        channel_id: str,
        *,
        begin_time: str,
        end_time: str,
        record_type: str,
        stream_id: int | None = None,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """Create an HLS URL for a same-day recording interval."""
        from .playback.hls import async_create_device_record_hls

        return await async_create_device_record_hls(
            self._imou_api_client,
            device_id=device_id,
            channel_id=channel_id,
            begin_time=begin_time,
            end_time=end_time,
            record_type=record_type,
            stream_id=stream_id,
            file_name=file_name,
        )

    async def async_create_device_record_flv(
        self,
        device_id: str,
        channel_id: str,
        *,
        begin_time: str,
        end_time: str,
        record_type: str,
        prefer_hd: bool = True,
        speed: int | None = None,
    ) -> dict[str, Any]:
        """Create an HTTP-FLV URL for a recording interval (createDeviceFlvLive)."""
        from .playback.flv import async_create_device_record_flv

        url = await async_create_device_record_flv(
            self._imou_api_client,
            device_id=device_id,
            channel_id=channel_id,
            begin_time=begin_time,
            end_time=end_time,
            record_type=record_type,
            prefer_hd=prefer_hd,
            speed=speed,
        )
        return {"url": url} if url else {}

    async def async_local_record_bitmap(
        self,
        device_id: str,
        channel_id: str,
        *,
        year: int,
        month: int,
        record_type: str = "0",
        product_id: str | None = None,
    ) -> dict[str, Any]:
        """Local recording month bitmap via record.file.bitmap."""
        from .local_record import async_local_record_bitmap

        return await async_local_record_bitmap(
            self._imou_api_client,
            device_id=device_id,
            channel_id=channel_id,
            year=year,
            month=month,
            record_type=record_type,
            product_id=product_id,
        )

    async def async_local_record_list(
        self,
        device_id: str,
        channel_id: str,
        *,
        begin_time: str,
        end_time: str,
        limit: int = 50,
        record_type: str = "0",
        session_id: str | None = None,
        product_id: str | None = None,
    ) -> dict[str, Any]:
        """Local recording list for a time window."""
        from .local_record import async_local_record_list

        return await async_local_record_list(
            self._imou_api_client,
            device_id=device_id,
            channel_id=channel_id,
            begin_time=begin_time,
            end_time=end_time,
            limit=limit,
            record_type=record_type,
            session_id=session_id,
            product_id=product_id,
        )

    async def async_list_local_record_segments(
        self,
        device_id: str,
        channel_id: str,
        *,
        begin_time: str,
        end_time: str,
        product_id: str | None = None,
        limit: int = 100,
    ) -> list[LocalRecordSegment]:
        """List all local segments in a window, paging record.file.list."""
        from .local_record import parse_local_record_list

        cursor_time = _parse_record_time(begin_time)
        window_end_time = _parse_record_time(end_time)
        if (
            cursor_time is None
            or window_end_time is None
            or cursor_time >= window_end_time
        ):
            return []

        bounded_limit = max(30, min(100, int(limit)))
        window_seconds = min(
            24 * 60 * 60, int((window_end_time - cursor_time).total_seconds())
        )
        max_pages = max(1, ceil(window_seconds / bounded_limit) + 1)
        segments: list[LocalRecordSegment] = []
        seen: set[str | tuple[str, str, str]] = set()
        cursor_begin = begin_time
        for _page in range(max_pages):
            data = await self.async_local_record_list(
                device_id,
                channel_id,
                begin_time=cursor_begin,
                end_time=end_time,
                limit=bounded_limit,
                product_id=product_id,
            )
            output_data = data.get("outputData") if isinstance(data, dict) else None
            raw_records = (
                output_data.get("records") if isinstance(output_data, dict) else None
            )
            raw_records = raw_records if isinstance(raw_records, list) else []
            batch = parse_local_record_list(data)

            for segment in batch:
                record_id = getattr(segment, "record_id", None)
                identity: str | tuple[str, str, str]
                if record_id:
                    identity = str(record_id)
                else:
                    identity = (
                        segment.begin_time,
                        segment.end_time,
                        segment.file_name,
                    )
                if identity not in seen:
                    seen.add(identity)
                    segments.append(segment)

            if len(raw_records) < bounded_limit:
                break

            usable_end_times: list[tuple[datetime, str]] = []
            for segment in batch:
                parsed_end_time = _parse_record_time(segment.end_time)
                if parsed_end_time is not None:
                    usable_end_times.append((parsed_end_time, segment.end_time))
            if not usable_end_times:
                _LOGGER.warning(
                    "Local record page has no usable end time for %s", device_id
                )
                break
            next_cursor_time, next_cursor = max(usable_end_times)
            if next_cursor_time <= cursor_time:
                _LOGGER.warning("Local record cursor did not advance for %s", device_id)
                break
            if next_cursor_time >= window_end_time:
                break
            cursor_begin = next_cursor
            cursor_time = next_cursor_time
        else:
            _LOGGER.warning(
                "Local record pagination reached the %d-page safety limit for %s",
                max_pages,
                device_id,
            )
        return segments

    async def async_search_ai_alarm_message(
        self,
        device_id: str,
        channel_id: str,
        *,
        search_content: str,
        begin_time: str,
        end_time: str,
        page_size: int = 32,
        sort_type: str = "0",
        next_index_id: str | None = None,
        product_id: str | None = None,
    ) -> dict[str, Any]:
        """Keyword search over AI alarm messages."""
        params: dict[str, Any] = {
            PARAM_DEVICE_ID: device_id,
            "searchContent": search_content[:50],
            "pageSize": str(max(1, min(32, page_size))),
            "sortType": sort_type,
        }
        params.update(_search_channel_param(channel_id))
        if product_id:
            params[PARAM_PRODUCT_ID] = product_id
        if next_index_id:
            params["nextIndexId"] = next_index_id
        else:
            params["beginTime"] = begin_time
            params["endTime"] = end_time
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_SEARCH_AI_ALARM_MESSAGE, params
        )

    async def async_get_alarm_message_statistics(
        self,
        device_id: str,
        channel_id: str,
        *,
        start_day: str,
        end_day: str,
        product_id: str | None = None,
        ai_statistics_analysis_enable: bool = True,
        multi_view: int = 1,
    ) -> dict[str, Any]:
        """Daily AI alarm statistics for a channel."""
        params: dict[str, Any] = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            "startDay": start_day,
            "endDay": end_day,
            "aiStatisticsAnalysisEnable": ai_statistics_analysis_enable,
            "multiView": _multi_view_param(multi_view),
            "msgAnalysis": _MSG_ANALYSIS,
            "riskStatement": _RISK_WINDOWS,
        }
        if product_id:
            params[PARAM_PRODUCT_ID] = product_id
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_ALARM_MESSAGE_STATISTICS, params
        )

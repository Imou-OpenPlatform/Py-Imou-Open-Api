from __future__ import annotations

import asyncio
import logging
from collections.abc import Collection
from dataclasses import dataclass, replace
from datetime import datetime
from math import ceil
from time import monotonic
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .local_record import LocalRecordSegment

from .const import (
    API_ENDPOINT_BIND_DEVICE,
    API_ENDPOINT_BIND_DEVICE_LIVE,
    API_ENDPOINT_CONTROL_DEVICE_PTZ,
    API_ENDPOINT_DEVICE_SD_CARD_STATUS,
    API_ENDPOINT_DEVICE_SNAP_DETECT,
    API_ENDPOINT_DEVICE_STORAGE,
    API_ENDPOINT_GET_ALARM_MESSAGE_STATISTICS,
    API_ENDPOINT_GET_COLLECTION,
    API_ENDPOINT_GET_DEVICE_ALARM_PARAM,
    API_ENDPOINT_GET_DEVICE_CLOUD,
    API_ENDPOINT_GET_DEVICE_LIVE_INFO,
    API_ENDPOINT_GET_DEVICE_NIGHT_VISION_MODE,
    API_ENDPOINT_GET_DEVICE_POWER_INFO,
    API_ENDPOINT_GET_DEVICE_STATUS,
    API_ENDPOINT_GET_IOT_DEVICE_DETAIL_INFO,
    API_ENDPOINT_GET_IOT_DEVICE_PROPERTIES,
    API_ENDPOINT_GET_PRODUCT_MODEL,
    API_ENDPOINT_GET_STREAM_URL,
    API_ENDPOINT_IOT_DEVICE_CONTROL,
    API_ENDPOINT_LIST_DEVICE_DETAILS,
    API_ENDPOINT_LIST_PRODUCT_DETAIL,
    API_ENDPOINT_MODIFY_DEVICE_ALARM_STATUS,
    API_ENDPOINT_QUERY_CLOUD_RECORD_BITMAP,
    API_ENDPOINT_QUERY_CLOUD_RECORDS,
    API_ENDPOINT_SEARCH_AI_ALARM_MESSAGE,
    API_ENDPOINT_SET_DEVICE_NIGHT_VISION_MODE,
    API_ENDPOINT_SET_DEVICE_SNAP,
    API_ENDPOINT_SET_DEVICE_STATUS,
    API_ENDPOINT_SET_IOT_DEVICE_PROPERTIES,
    API_ENDPOINT_SIREN_START,
    API_ENDPOINT_SIREN_STOP,
    API_ENDPOINT_TURN_COLLECTION,
    API_ENDPOINT_WAKE_UP_DEVICE,
    API_V2_DEVICE_REBOOT_EXECUTE,
    API_V2_DEVICE_STATUS_GET,
    NIGHT_VISION_MODE_MAP,
    PARAM_ABILITY_REFS,
    PARAM_ACCESS_TYPE,
    PARAM_AI_INSIGHT_STATUS,
    PARAM_BRAND,
    PARAM_CHANNEL_ABILITY,
    PARAM_CHANNEL_ID,
    PARAM_CHANNEL_LIST,
    PARAM_CHANNEL_NAME,
    PARAM_CHANNEL_NUM,
    PARAM_CHANNEL_STATUS,
    PARAM_CHANNELS,
    PARAM_CODE,
    PARAM_COLLECTION_NAME,
    PARAM_CONTENT,
    PARAM_CS_STATUS,
    PARAM_DEVICE_ABILITY,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_LIST,
    PARAM_DEVICE_MODEL,
    PARAM_DEVICE_NAME,
    PARAM_DEVICE_STATUS,
    PARAM_DEVICE_VERSION,
    PARAM_DURATION,
    PARAM_ENABLE,
    PARAM_ENABLE_TYPE,
    PARAM_EVENTS,
    PARAM_IDENTIFIER,
    PARAM_MODE,
    PARAM_MULTI_FLAG,
    PARAM_OPERATION,
    PARAM_PAGE,
    PARAM_PAGE_SIZE,
    PARAM_PARENT_DEVICE_ID,
    PARAM_PARENT_PRODUCT_ID,
    PARAM_PRODUCT_ID,
    PARAM_PRODUCT_IDS,
    PARAM_PROPERTIES,
    PARAM_REF,
    PARAM_STREAM_ID,
    PARAM_URL,
)
from .openapi import ImouOpenApiClient
from .product_detail import ProductDetail, parse_product_details

_LOGGER = logging.getLogger(__name__)
_RECORD_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_record_time(value: str) -> datetime | None:
    """Parse the device-local time format used by cloud-record APIs."""
    try:
        parsed = datetime.strptime(value, _RECORD_TIME_FORMAT)
    except ValueError:
        return None
    return parsed if parsed.strftime(_RECORD_TIME_FORMAT) == value else None


# A failed product-model fetch is retried after this, instead of on every push.
_EVENT_MAP_RETRY_SECONDS = 60


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


def _parse_event_ref_map(data: dict[str, Any] | None) -> dict[str, str]:
    """Build {event.ref: event.identifier} from a getProductModel payload."""
    if not isinstance(data, dict):
        return {}
    events = data.get(PARAM_EVENTS)
    if not isinstance(events, list):
        return {}
    mapping: dict[str, str] = {}
    for item in events:
        if not isinstance(item, dict):
            continue
        ref = item.get(PARAM_REF)
        identifier = item.get(PARAM_IDENTIFIER)
        if ref is None or identifier is None or identifier == "":
            continue
        mapping[str(ref)] = str(identifier)
    return mapping


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
        self._channel_ability_refs = "unknown"
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
    def channel_ability_refs(self) -> str:
        return self._channel_ability_refs

    def set_channel_ability_refs(self, channel_ability_refs: str):
        self._channel_ability_refs = channel_ability_refs

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
        self._device_ability_refs = "unknown"
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
    def device_ability_refs(self) -> str:
        return self._device_ability_refs

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

    def set_device_ability_refs(self, device_ability_refs: str):
        self._device_ability_refs = device_ability_refs

    def set_access_type(self, access_type: str):
        self._access_type = access_type


def _search_channel_param(channel_id: str) -> dict[str, Any]:
    """searchAiAlarmMessageByPage takes channelIds on both gateways."""
    channel = int(channel_id) if str(channel_id).isdigit() else str(channel_id)
    return {"channelIds": [channel]}


class ImouDeviceManager:
    def __init__(self, imou_api_client: ImouOpenApiClient):
        self._imou_api_client = imou_api_client
        self._event_maps: dict[str, dict[str, str]] = {}
        self._event_map_failed_at: dict[str, float] = {}
        self._event_map_locks: dict[str, asyncio.Lock] = {}
        self._event_map_locks_guard = asyncio.Lock()
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

    async def _async_lock_for_product(self, product_id: str) -> asyncio.Lock:
        async with self._event_map_locks_guard:
            lock = self._event_map_locks.get(product_id)
            if lock is None:
                lock = asyncio.Lock()
                self._event_map_locks[product_id] = lock
            return lock

    async def async_ensure_event_map(self, product_id: str) -> None:
        """Fetch and cache events ref→identifier for product_id if missing."""
        if not product_id:
            return
        if product_id in self._event_maps:
            return
        lock = await self._async_lock_for_product(product_id)
        async with lock:
            if product_id in self._event_maps:
                return
            failed_at = self._event_map_failed_at.get(product_id)
            if (
                failed_at is not None
                and monotonic() - failed_at < _EVENT_MAP_RETRY_SECONDS
            ):
                return
            try:
                data = await self.async_get_product_model(product_id)
            except Exception:
                self._event_map_failed_at[product_id] = monotonic()
                _LOGGER.warning(
                    "getProductModel failed for product_id=%s",
                    product_id,
                    exc_info=True,
                )
                return
            self._event_map_failed_at.pop(product_id, None)
            self._event_maps[product_id] = _parse_event_ref_map(data)

    def cached_event_map(self, product_id: str) -> dict[str, str]:
        """Return the cached events ref→identifier map, or {} if not loaded."""
        if not product_id:
            return {}
        return dict(self._event_maps.get(product_id) or {})

    async def async_resolve_event_identifier(
        self, product_id: str, ref: str
    ) -> str | None:
        """Return event identifier for ref, fetching the product model if needed."""
        if not product_id or ref is None or ref == "":
            return None
        await self.async_ensure_event_map(product_id)
        mapping = self._event_maps.get(product_id)
        if mapping is None:
            return None
        return mapping.get(str(ref))

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
        *,
        fetch_ability_refs: bool | set[str] = False,
    ) -> list[ImouDevice]:
        """GET DEVICE LIST.

        ``fetch_ability_refs`` controls the per-IoT ``getIotDeviceDetailInfo``
        calls that resolve legacy ability refs. This compatibility lookup is
        deprecated and will be removed in the next major version; normal
        discovery registers capabilities from ``device.capability.list``:

        - ``False`` (default): skip every detail call
        - ``True``: fetch for every IoT device on the page
        - a set of device ids: fetch only for those ids
        """
        devices = await self._async_get_devices(
            page,
            page_size,
            fetch_ability_refs=fetch_ability_refs,
        )
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
        *,
        fetch_ability_refs: bool | set[str],
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
        iot_devices = []
        for device in device_list:
            device_id = device[PARAM_DEVICE_ID]
            device_name = device[PARAM_DEVICE_NAME]
            device_status = device[PARAM_DEVICE_STATUS]
            brand = device[PARAM_BRAND]
            device_model = device.get(PARAM_DEVICE_MODEL, "unknown")
            imou_device = ImouDevice(
                device_id, device_name, device_status, brand, device_model
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
            if PARAM_ACCESS_TYPE in device:
                imou_device.set_access_type(device[PARAM_ACCESS_TYPE])
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
            # If it is an iot device, update the abilityRefs field to determine the entity
            # that needs to be registered based on this field
            if PARAM_PRODUCT_ID in device:
                imou_device.set_product_id(device[PARAM_PRODUCT_ID])
                iot_devices.append(imou_device)
            devices.append(imou_device)
        # Each iot device costs one getIotDeviceDetailInfo call; issue them together
        # so listing N devices is one round trip instead of N serial ones. Callers
        # that only need the set of device keys (periodic rediscovery) pass
        # fetch_ability_refs=False and skip this entirely.
        if fetch_ability_refs is False:
            to_fetch: list[ImouDevice] = []
        elif fetch_ability_refs is True:
            to_fetch = iot_devices
        else:
            to_fetch = [d for d in iot_devices if d.device_id in fetch_ability_refs]
        if to_fetch:
            # One accessory that is offline, rate limited, or answering 5xx must
            # not cost the caller its whole account. That device keeps its
            # "unknown" refs and comes back with the next listing.
            results = await asyncio.gather(
                *(
                    self._async_update_device_ability_refs(iot_device)
                    for iot_device in to_fetch
                ),
                return_exceptions=True,
            )
            for iot_device, result in zip(to_fetch, results, strict=True):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                if isinstance(result, BaseException):
                    _LOGGER.warning(
                        "Could not read ability refs for device %s: %s",
                        iot_device.device_id,
                        result,
                    )
        # A full page may have more behind it. This counts what actually arrived
        # rather than trusting `count`, which stops the paging either way: were
        # that field the account total instead of this page's size, an account
        # holding an exact multiple of page_size would page on forever.
        if len(device_list) >= page_size:
            devices.extend(
                await self._async_get_devices(
                    page + 1,
                    page_size,
                    fetch_ability_refs=fetch_ability_refs,
                )
            )
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

    async def async_control_device_ptz(
        self, device_id: str, channel_id: str | None, operation: int, duration: int
    ) -> None:
        """control ptz"""
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_OPERATION: operation,
            PARAM_DURATION: duration,
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_CONTROL_DEVICE_PTZ, params
        )

    async def async_modify_device_alarm_status(
        self, device_id: str, channel_id: str | None, enabled: bool
    ) -> None:
        """SET DEVICE ALARM STATUS"""
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_ENABLE: enabled,
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_MODIFY_DEVICE_ALARM_STATUS, params
        )

    async def async_get_device_status(
        self, device_id: str, channel_id: str | None, enable_type: str
    ) -> dict[str, Any]:
        """obtain device capability switch status"""
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_ENABLE_TYPE: enable_type,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_DEVICE_STATUS, params
        )

    async def async_get_device_online_status(
        self, device_id: str, product_id: str | None = None
    ) -> dict[str, Any]:
        """GET DEVICE ONLINE STATUS via device.status.get."""
        params: dict[str, Any] = {
            PARAM_DEVICE_ID: device_id,
        }
        if product_id:
            params[PARAM_PRODUCT_ID] = product_id
        return await self._imou_api_client.async_request_api(
            API_V2_DEVICE_STATUS_GET, params
        )

    async def async_set_device_status(
        self, device_id: str, channel_id: str | None, enable_type: str, enable: bool
    ) -> None:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_ENABLE_TYPE: enable_type,
            PARAM_ENABLE: enable,
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_SET_DEVICE_STATUS, params
        )

    async def async_get_device_night_vision_mode(
        self, device_id: str, channel_id: str | None
    ) -> dict[str, Any]:
        """obtain device night vision mode"""
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_DEVICE_NIGHT_VISION_MODE, params
        )

    async def async_set_device_night_vision_mode(
        self, device_id: str, channel_id: str | None, night_vision_mode: str
    ) -> None:
        """set device night vision mode"""
        if night_vision_mode in NIGHT_VISION_MODE_MAP:
            night_vision_mode = NIGHT_VISION_MODE_MAP[night_vision_mode]
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_MODE: night_vision_mode,
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_SET_DEVICE_NIGHT_VISION_MODE, params
        )

    async def async_get_device_storage(self, device_id: str) -> dict[str, Any]:
        """obtain device storage media capacity information"""
        params = {PARAM_DEVICE_ID: device_id}
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_DEVICE_STORAGE, params
        )

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

    async def async_get_stream_url(
        self, device_id: str, channel_id: str | None
    ) -> dict[str, Any]:
        """obtain the hls stream address of the device"""
        params = {PARAM_DEVICE_ID: device_id, PARAM_CHANNEL_ID: channel_id}
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_DEVICE_LIVE_INFO, params
        )

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

    async def async_get_device_cloud(
        self, device_id: str, channel_id: str
    ) -> dict[str, Any]:
        """Return the active cloud storage plan for a device channel."""
        params = {PARAM_DEVICE_ID: device_id, PARAM_CHANNEL_ID: channel_id}
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_DEVICE_CLOUD, params
        )

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
    ) -> dict[str, Any]:
        """Daily AI alarm statistics for a channel."""
        params: dict[str, Any] = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            "startDay": start_day,
            "endDay": end_day,
            "aiStatisticsAnalysisEnable": ai_statistics_analysis_enable,
        }
        if product_id:
            params[PARAM_PRODUCT_ID] = product_id
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_ALARM_MESSAGE_STATISTICS, params
        )

    async def async_create_stream_url(
        self, device_id: str, channel_id: str | None, stream_id: int = 0
    ) -> dict[str, Any]:
        """create device hls stream address"""
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_STREAM_ID: stream_id,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_BIND_DEVICE_LIVE, params
        )

    async def async_get_device_alarm_param(
        self, device_id: str, channel_id: str
    ) -> None:
        """set device alarm status"""
        params = {PARAM_DEVICE_ID: device_id, PARAM_CHANNEL_ID: channel_id}
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_DEVICE_ALARM_PARAM, params
        )

    async def async_get_iot_device_properties(
        self,
        device_id: str,
        channel_id: str | None,
        product_id: str,
        properties: list[Any],
    ) -> dict[str, Any]:
        params = {
            PARAM_DEVICE_LIST: [
                {
                    PARAM_DEVICE_ID: device_id,
                    PARAM_CHANNEL_ID: int(channel_id)
                    if channel_id is not None
                    else channel_id,
                    PARAM_PRODUCT_ID: product_id,
                    PARAM_PROPERTIES: properties,
                }
            ]
        }
        data = await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_IOT_DEVICE_PROPERTIES, params
        )
        device_list = data.get(PARAM_DEVICE_LIST) if isinstance(data, dict) else None
        if not device_list:
            return {}
        return device_list[0]

    async def async_set_iot_device_properties(
        self, device_id: str, channel_id: str | None, product_id: str, properties: dict
    ) -> None:
        params = {
            PARAM_DEVICE_LIST: [
                {
                    PARAM_DEVICE_ID: device_id,
                    PARAM_CHANNEL_ID: int(channel_id)
                    if channel_id is not None
                    else channel_id,
                    PARAM_PRODUCT_ID: product_id,
                    PARAM_PROPERTIES: properties,
                }
            ]
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_SET_IOT_DEVICE_PROPERTIES, params
        )

    async def async_get_device_sd_card_status(self, device_id: str) -> dict[str, Any]:
        params = {PARAM_DEVICE_ID: device_id}
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_DEVICE_SD_CARD_STATUS, params
        )

    async def async_iot_device_control(
        self, device_id: str, product_id: str, ref: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_PRODUCT_ID: product_id,
            PARAM_REF: ref,
            PARAM_CONTENT: content,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_IOT_DEVICE_CONTROL, params
        )

    async def async_get_device_power_info(self, device_id: str) -> dict[str, Any]:
        params = {
            PARAM_DEVICE_ID: device_id,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_DEVICE_POWER_INFO, params
        )

    async def async_wake_up_device(self, device_id: str) -> None:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_URL: "/device/wakeup",
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_WAKE_UP_DEVICE, params
        )

    async def async_get_product_model(self, product_id: str) -> dict[str, Any]:
        params = {
            PARAM_PRODUCT_ID: product_id,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_PRODUCT_MODEL, params
        )

    async def async_get_iot_device_detail_info(
        self, device_id: str, product_id: str
    ) -> dict[str, Any]:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_PRODUCT_ID: product_id,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_IOT_DEVICE_DETAIL_INFO, params
        )

    async def async_get_device_collection(
        self, device_id: str, channel_id: str
    ) -> dict[str, Any]:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
        }
        return await self._imou_api_client.async_request_api(
            API_ENDPOINT_GET_COLLECTION, params
        )

    async def async_turn_device_collection(
        self, device_id: str, channel_id: str, name: str
    ) -> None:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
            PARAM_COLLECTION_NAME: name,
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_TURN_COLLECTION, params
        )

    async def async_siren_start(
        self, device_id: str, channels: list[int] | None = None
    ) -> None:
        params: dict[str, Any] = {PARAM_DEVICE_ID: device_id}
        if channels is not None:
            params[PARAM_CHANNELS] = channels
        await self._imou_api_client.async_request_api(API_ENDPOINT_SIREN_START, params)

    async def async_siren_stop(
        self, device_id: str, channels: list[int] | None = None
    ) -> None:
        params: dict[str, Any] = {PARAM_DEVICE_ID: device_id}
        if channels is not None:
            params[PARAM_CHANNELS] = channels
        await self._imou_api_client.async_request_api(API_ENDPOINT_SIREN_STOP, params)

    async def _async_update_device_ability_refs(self, imou_device: ImouDevice) -> None:
        # Only iot devices carry a product id, and it is what the detail call
        # is keyed on, so there is nothing to ask about without one.
        if imou_device.product_id is None:
            return
        device_id = compose_iot_device_id(
            imou_device.device_id,
            imou_device.parent_device_id,
            imou_device.parent_product_id,
        )
        device_detail = await self.async_get_iot_device_detail_info(
            device_id,
            imou_device.product_id,
        )
        imou_device.set_device_ability_refs(
            _text_or_default(device_detail.get(PARAM_ABILITY_REFS))
        )
        channels_detail = device_detail.get(PARAM_CHANNELS)
        if channels_detail and imou_device.channels:
            channel_detail_map = {
                str(channel_detail.get(PARAM_CHANNEL_ID)): _text_or_default(
                    channel_detail.get(PARAM_ABILITY_REFS)
                )
                for channel_detail in channels_detail
                if channel_detail.get(PARAM_CHANNEL_ID) is not None
            }
            for channel in imou_device.channels:
                channel_id = (
                    str(channel.channel_id) if channel.channel_id is not None else None
                )
                if channel_id is not None and channel_id in channel_detail_map:
                    channel.set_channel_ability_refs(channel_detail_map[channel_id])

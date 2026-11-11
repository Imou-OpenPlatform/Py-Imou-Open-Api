"""createDeviceRecordHls helpers."""

from __future__ import annotations

from typing import Any

from ..const import (
    API_ENDPOINT_CREATE_DEVICE_RECORD_HLS,
    PARAM_CHANNEL_ID,
    PARAM_DEVICE_ID,
)
from ..openapi import ImouOpenApiClient

RECORD_TYPE_CLOUD = "cloudRecord"
RECORD_TYPE_LOCAL = "localRecord"


def parse_record_hls_url(data: Any) -> str | None:
    """Extract HLS url from createDeviceRecordHls data."""
    if not isinstance(data, dict):
        return None
    url = data.get("url")
    if not url:
        return None
    url_str = str(url).strip()
    return url_str or None


async def async_create_device_record_hls(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    channel_id: str,
    begin_time: str,
    end_time: str,
    record_type: str,
    stream_id: int | None = None,
) -> str | None:
    """Request an HLS playback URL for a same-day recording window."""
    params: dict[str, Any] = {
        PARAM_DEVICE_ID: device_id,
        PARAM_CHANNEL_ID: channel_id,
        "beginTime": begin_time,
        "endTime": end_time,
        "recordType": record_type,
    }
    if stream_id is not None:
        params["streamId"] = stream_id
    data = await client.async_request_api(API_ENDPOINT_CREATE_DEVICE_RECORD_HLS, params)
    return parse_record_hls_url(data)

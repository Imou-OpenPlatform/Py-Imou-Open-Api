"""createDeviceFlvLive helpers for recording playback."""

from __future__ import annotations

from typing import Any, Literal

from ..const import (
    API_ENDPOINT_CREATE_DEVICE_FLV_LIVE,
    PARAM_CHANNEL_ID,
    PARAM_DEVICE_ID,
)
from ..openapi import ImouOpenApiClient
from .hls import RECORD_TYPE_CLOUD, RECORD_TYPE_LOCAL

PLAYBACK_TYPE_PLAYBACK = "playback"


def is_flv_playback_url(url: str) -> bool:
    """Return whether the URL looks like an Imou FLV playback address."""
    candidate = url.strip()
    if not candidate.startswith(("http://", "https://")):
        return False
    lowered = candidate.lower()
    return lowered.endswith(".flv") or ".flv?" in lowered


def parse_record_flv_urls(
    data: Any, *, prefer_hd: bool = True
) -> tuple[str | None, str | None]:
    """Extract SD/HD FLV urls from createDeviceFlvLive data."""
    if not isinstance(data, dict):
        return None, None
    flv = str(data.get("flv") or "").strip() or None
    flv_hd = str(data.get("flvHD") or "").strip() or None
    if flv and not is_flv_playback_url(flv):
        flv = None
    if flv_hd and not is_flv_playback_url(flv_hd):
        flv_hd = None
    primary = flv_hd if prefer_hd else flv
    if primary is None:
        primary = flv if prefer_hd else flv_hd
    return primary, flv_hd if prefer_hd else flv


async def async_create_device_record_flv(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    channel_id: str,
    begin_time: str,
    end_time: str,
    record_type: Literal["localRecord", "cloudRecord"] | str,
    prefer_hd: bool = True,
    speed: int | None = None,
) -> str | None:
    """Request an HTTP-FLV playback URL for a recording window."""
    if record_type not in (RECORD_TYPE_CLOUD, RECORD_TYPE_LOCAL):
        record_type = RECORD_TYPE_CLOUD
    params: dict[str, Any] = {
        PARAM_DEVICE_ID: device_id,
        PARAM_CHANNEL_ID: channel_id,
        "type": PLAYBACK_TYPE_PLAYBACK,
        "beginTime": begin_time,
        "endTime": end_time,
        "recordType": record_type,
    }
    if speed is not None:
        params["speed"] = speed
    data = await client.async_request_api(API_ENDPOINT_CREATE_DEVICE_FLV_LIVE, params)
    url, _ = parse_record_flv_urls(data, prefer_hd=prefer_hd)
    return url

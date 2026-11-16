"""createDeviceRecordHls helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

from ..const import (
    API_ENDPOINT_CREATE_DEVICE_RECORD_HLS,
    PARAM_CHANNEL_ID,
    PARAM_DEVICE_ID,
)
from ..openapi import ImouOpenApiClient

RECORD_TYPE_CLOUD = "cloudRecord"
RECORD_TYPE_LOCAL = "localRecord"
_RECORD_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def validate_record_playback_window(
    begin_time: str, end_time: str, record_type: str
) -> None:
    """Validate a same-day recording playback window."""
    if record_type not in (RECORD_TYPE_LOCAL, RECORD_TYPE_CLOUD):
        raise ValueError("record_type must be localRecord or cloudRecord")

    parsed_times: list[datetime] = []
    for name, value in (("begin_time", begin_time), ("end_time", end_time)):
        try:
            parsed = datetime.strptime(value, _RECORD_TIME_FORMAT)
        except (TypeError, ValueError) as err:
            raise ValueError(f"{name} must use the YYYY-MM-DD HH:MM:SS format") from err
        if parsed.strftime(_RECORD_TIME_FORMAT) != value:
            raise ValueError(f"{name} must use the YYYY-MM-DD HH:MM:SS format")
        parsed_times.append(parsed)

    begin, end = parsed_times
    if begin >= end:
        raise ValueError("begin_time must be before end_time")
    if begin.date() != end.date():
        raise ValueError("begin_time and end_time must be on the same calendar day")


def normalize_imou_hls_segment_url(url: str) -> str:
    """Fix Lechange segment URLs where auth query is appended after ``.ts?``."""
    return url.replace(".ts?", ".ts&", 1) if ".ts?" in url else url


def _absolute_hls_uri(line: str, base_url: str | None) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith(("http://", "https://")):
        return stripped
    if base_url:
        return urljoin(base_url, stripped)
    return None


def pick_hls_variant_playlist_url(playlist_body: str, base_url: str) -> str | None:
    """Return a child m3u8 URL when the playlist is a master playlist."""
    lines = [line.strip() for line in playlist_body.splitlines()]
    for index, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and index + 1 < len(lines):
            child = _absolute_hls_uri(lines[index + 1], base_url)
            if child and ".m3u8" in child.split("?", 1)[0].lower():
                return child
    for line in lines:
        child = _absolute_hls_uri(line, base_url)
        if child and ".m3u8" in child.split("?", 1)[0].lower():
            return child
    return None


def parse_hls_media_segment_urls(
    playlist_body: str, base_url: str | None = None
) -> list[str]:
    """Return absolute media segment URIs from an HLS media playlist."""
    segments: list[str] = []
    for line in playlist_body.splitlines():
        uri = _absolute_hls_uri(line, base_url)
        if not uri or not uri.startswith(("http://", "https://")):
            continue
        path = uri.split("?", 1)[0].lower()
        if path.endswith(".m3u8") or path.endswith(".m3u8/"):
            continue
        segments.append(normalize_imou_hls_segment_url(uri))
    return segments


def is_hls_playback_url(url: str) -> bool:
    """Reject SD paths or other non-stream urls from createDeviceRecordHls."""
    candidate = url.strip()
    if candidate != url or any(ord(character) < 32 for character in candidate):
        return False
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"http", "https"}
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and port != 0
        and not parsed.path.lower().endswith(".dav")
    )


def parse_record_hls_url(data: Any) -> str | None:
    """Extract HLS url from createDeviceRecordHls data."""
    if not isinstance(data, dict):
        return None
    url = data.get("url")
    if not url:
        return None
    url_str = str(url).strip()
    if not url_str or not is_hls_playback_url(url_str):
        return None
    return url_str


async def async_create_device_record_hls(
    client: ImouOpenApiClient,
    *,
    device_id: str,
    channel_id: str,
    begin_time: str,
    end_time: str,
    record_type: str,
    stream_id: int | None = None,
    file_name: str | None = None,
) -> str | None:
    """Request an HLS playback URL for a same-day recording window."""
    validate_record_playback_window(begin_time, end_time, record_type)
    params: dict[str, Any] = {
        PARAM_DEVICE_ID: device_id,
        PARAM_CHANNEL_ID: channel_id,
        "beginTime": begin_time,
        "endTime": end_time,
        "recordType": record_type,
    }
    if record_type == RECORD_TYPE_LOCAL and file_name:
        params["fileName"] = file_name
    if stream_id is not None:
        params["streamId"] = stream_id
    data = await client.async_request_api(API_ENDPOINT_CREATE_DEVICE_RECORD_HLS, params)
    return parse_record_hls_url(data)

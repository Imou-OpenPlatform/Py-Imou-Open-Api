"""createDeviceFlvLive parsing."""

import pytest
from pyimouapi.playback.flv import is_flv_playback_url, parse_record_flv_urls


@pytest.mark.parametrize(
    "url",
    [
        "https://flvproxy.lechange.com:7088/vod/abc.flv?expire=1&digest=x",
        "http://cdn.example/live.flv",
        "HTTPS://cdn.example/live.FLV",
        "https://cdn.example/live.flv#fragment",
        "https://[2001:db8::1]:8443/live.flv",
        "  https://localhost/live.flv  ",
    ],
)
def test_is_flv_playback_url(url: str) -> None:
    assert is_flv_playback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/vod/abc.m3u8",
        "ftp://example.test/vod/abc.flv",
        "https:///vod/abc.flv",
        "https://user:password@example.test/vod/abc.flv",
        "https://@example.test/vod/abc.flv",
        "https://example.test:0/vod/abc.flv",
        "https://example.test:65536/vod/abc.flv",
        "https://example.test:bad/vod/abc.flv",
        "https://example.test:/vod/abc.flv",
        "https://[2001:db8::1/vod/abc.flv",
        "https://bad host/vod/abc.flv",
        "https://-bad.example/vod/abc.flv",
        "https://bad..example/vod/abc.flv",
        "https://999.999.999.999/vod/abc.flv",
        "https://example.test/vod/abc.flv\n",
        "https://example.test/vod/abc\t.flv",
        "https://example.test/vod/abc.flv/extra",
        "https://example.test/vod/abc.m3u8?file=abc.flv",
    ],
)
def test_is_flv_playback_url_rejects_invalid_urls(url: str) -> None:
    assert not is_flv_playback_url(url)


def test_parse_record_flv_urls_prefers_hd() -> None:
    url, _ = parse_record_flv_urls(
        {
            "flv": "https://a/sd.flv?x=1",
            "flvHD": "https://a/hd.flv?x=1",
        },
        prefer_hd=True,
    )
    assert url == "https://a/hd.flv?x=1"

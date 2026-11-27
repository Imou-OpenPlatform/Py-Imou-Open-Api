"""createDeviceFlvLive parsing."""

from pyimouapi.playback.flv import is_flv_playback_url, parse_record_flv_urls


def test_is_flv_playback_url() -> None:
    assert is_flv_playback_url(
        "https://flvproxy.lechange.com:7088/vod/abc.flv?expire=1&digest=x"
    )
    assert not is_flv_playback_url("https://example.test/vod/abc.m3u8")


def test_parse_record_flv_urls_prefers_hd() -> None:
    url, _ = parse_record_flv_urls(
        {
            "flv": "https://a/sd.flv?x=1",
            "flvHD": "https://a/hd.flv?x=1",
        },
        prefer_hd=True,
    )
    assert url == "https://a/hd.flv?x=1"

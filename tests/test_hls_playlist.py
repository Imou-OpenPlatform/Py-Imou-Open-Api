"""HLS playlist helpers for Imou record playback."""

from pyimouapi.playback.hls import (
    normalize_imou_hls_segment_url,
    parse_hls_media_segment_urls,
    pick_hls_variant_playlist_url,
)


def test_normalize_imou_segment_url() -> None:
    url = "https://example.test/seg?a=1&userid=35664364_seg_0.ts?proto=https&uid=abc"
    assert normalize_imou_hls_segment_url(url).endswith("uid=abc")
    assert ".ts?" not in normalize_imou_hls_segment_url(url)


def test_parse_hls_media_segment_urls() -> None:
    body = "\n".join(
        [
            "#EXTM3U",
            "#EXTINF:2,",
            "https://example.test/one.ts?proto=https",
            "#EXTINF:2,",
            "https://example.test/two.ts?x=1&proto=y",
        ]
    )
    segments = parse_hls_media_segment_urls(body)
    assert len(segments) == 2
    assert segments[0] == "https://example.test/one.ts&proto=https"


def test_parse_hls_relative_segment_urls() -> None:
    body = "\n".join(["#EXTM3U", "#EXTINF:2,", "seg0.ts?proto=https"])
    base = "https://cdn.example.test/path/index.m3u8?token=1"
    segments = parse_hls_media_segment_urls(body, base)
    assert segments == ["https://cdn.example.test/path/seg0.ts&proto=https"]


def test_parse_hls_segment_ts_in_query_only() -> None:
    body = "\n".join(
        [
            "#EXTINF:2,",
            "https://example.test/seg?a=1&userid=35664364_seg_0.ts?proto=https",
        ]
    )
    segments = parse_hls_media_segment_urls(body)
    assert len(segments) == 1
    assert ".ts&" in segments[0] or ".ts?" not in segments[0]


def test_pick_hls_variant_playlist_url() -> None:
    body = "\n".join(
        [
            "#EXTM3U",
            "#EXT-X-STREAM-INF:BANDWIDTH=800000",
            "chunks.m3u8",
        ]
    )
    variant = pick_hls_variant_playlist_url(
        body, "https://cdn.example.test/vod/master.m3u8"
    )
    assert variant == "https://cdn.example.test/vod/chunks.m3u8"

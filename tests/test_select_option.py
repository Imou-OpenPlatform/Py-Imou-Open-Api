"""Tests for select option friendly-key normalization."""

from __future__ import annotations

import pytest
from pyimouapi.const import PARAM_MODE, PARAM_NIGHT_VISION_MODE
from pyimouapi.select_option import normalize_options, to_friendly, to_raw

PARAM_DEVICE_VOLUME = "device_volume"


@pytest.mark.parametrize(
    ("select_type", "raw", "friendly"),
    [
        (PARAM_DEVICE_VOLUME, "99", "mute"),
        (PARAM_DEVICE_VOLUME, "-1", "mute"),
        (PARAM_DEVICE_VOLUME, -1, "mute"),
        (PARAM_DEVICE_VOLUME, "0", "low"),
        (PARAM_DEVICE_VOLUME, "1", "medium"),
        (PARAM_DEVICE_VOLUME, "2", "high"),
        (PARAM_MODE, "0", "home"),
        (PARAM_MODE, "1", "away"),
        (PARAM_MODE, "2", "disarm"),
        (PARAM_NIGHT_VISION_MODE, "0", "intelligent"),
        (PARAM_NIGHT_VISION_MODE, "1", "fullcolor"),
        (PARAM_NIGHT_VISION_MODE, "2", "infrared"),
        (PARAM_NIGHT_VISION_MODE, "3", "off"),
        (PARAM_NIGHT_VISION_MODE, "4", "custom"),
        (PARAM_NIGHT_VISION_MODE, "intelligent", "intelligent"),
        (PARAM_NIGHT_VISION_MODE, "FullColor", "fullcolor"),
        (PARAM_NIGHT_VISION_MODE, "lowlight", "lowlight"),
        (PARAM_NIGHT_VISION_MODE, "smartlowlight", "smartlowlight"),
    ],
)
def test_to_friendly(select_type: str, raw: str | int, friendly: str) -> None:
    assert to_friendly(select_type, raw) == friendly


@pytest.mark.parametrize(
    ("select_type", "friendly", "raw"),
    [
        (PARAM_DEVICE_VOLUME, "mute", "99"),
        (PARAM_DEVICE_VOLUME, "low", "0"),
        (PARAM_DEVICE_VOLUME, "medium", "1"),
        (PARAM_DEVICE_VOLUME, "high", "2"),
        (PARAM_MODE, "home", "0"),
        (PARAM_MODE, "away", "1"),
        (PARAM_MODE, "disarm", "2"),
        (PARAM_NIGHT_VISION_MODE, "intelligent", "0"),
        (PARAM_NIGHT_VISION_MODE, "fullcolor", "1"),
        (PARAM_NIGHT_VISION_MODE, "infrared", "2"),
        (PARAM_NIGHT_VISION_MODE, "off", "3"),
        (PARAM_NIGHT_VISION_MODE, "custom", "4"),
        (PARAM_NIGHT_VISION_MODE, "lowlight", "lowlight"),
        (PARAM_NIGHT_VISION_MODE, "smartlowlight", "smartlowlight"),
    ],
)
def test_to_raw(select_type: str, friendly: str, raw: str) -> None:
    assert to_raw(select_type, friendly) == raw


def test_to_friendly_unknown_raw_passthrough() -> None:
    assert to_friendly(PARAM_MODE, "9") == "9"


def test_to_raw_unknown_friendly_raises() -> None:
    with pytest.raises(ValueError, match="unknown"):
        to_raw(PARAM_MODE, "vacation")


def test_normalize_options_maps_list() -> None:
    assert normalize_options(PARAM_MODE, ["0", "1", "2"]) == [
        "home",
        "away",
        "disarm",
    ]


def test_collection_point_identity() -> None:
    from pyimouapi.const import PARAM_COLLECTION_POINT

    assert to_friendly(PARAM_COLLECTION_POINT, "door") == "door"
    assert to_raw(PARAM_COLLECTION_POINT, "door") == "door"

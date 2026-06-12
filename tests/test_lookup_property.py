"""Tests for property lookup from getIotDeviceDetailInfo responses."""

from pyimouapi.const import PARAM_CHANNEL_ID, PARAM_CHANNELS, PARAM_PROPERTIES
from pyimouapi.ha_device import ImouHaDeviceManager

DETAIL = {
    PARAM_PROPERTIES: {"10001": 1, "15400": 50},
    PARAM_CHANNELS: [
        {
            PARAM_CHANNEL_ID: "0",
            PARAM_PROPERTIES: {"20001": 0},
        },
        {
            PARAM_CHANNEL_ID: "1",
            PARAM_PROPERTIES: {"30001": 1},
        },
    ],
}


def test_lookup_channel_property():
    assert ImouHaDeviceManager._lookup_property(DETAIL, "1", "30001") == 1


def test_lookup_channel_zero_fallback_to_device_properties():
    assert ImouHaDeviceManager._lookup_property(DETAIL, "0", "10001") == 1


def test_lookup_channel_zero_prefers_channel_properties():
    assert ImouHaDeviceManager._lookup_property(DETAIL, "0", "20001") == 0


def test_lookup_channel_id_none_uses_device_properties():
    assert ImouHaDeviceManager._lookup_property(DETAIL, None, "15400") == 50


def test_lookup_missing_ref_returns_none():
    assert ImouHaDeviceManager._lookup_property(DETAIL, "1", "99999") is None


def test_lookup_channel_id_integer_zero():
    detail = {
        PARAM_PROPERTIES: {"10001": 7},
        PARAM_CHANNELS: [{PARAM_CHANNEL_ID: 0, PARAM_PROPERTIES: {}}],
    }
    assert ImouHaDeviceManager._lookup_property(detail, "0", "10001") == 7

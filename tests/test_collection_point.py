"""Tests for collection point support."""

from __future__ import annotations

from pyimouapi.collection_point import (
    build_collection_point_options,
    parse_iot_collection_names,
    unique_preserve_order,
)
from pyimouapi.const import (
    PARAM_COLLECTION_POINT_PROMPT,
)
from pyimouapi.ha_device import ImouHaDevice


def _ha_device(*, product_id: str | None = None) -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Front Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    if product_id is not None:
        device.set_product_id(product_id)
    return device


def test_parse_iot_collection_names_ref_map() -> None:
    """Parse names from IoT outputData ref map."""
    output = {"21501": [{"21551": "door"}, {"21551": "gate", "21552": "30"}]}
    assert parse_iot_collection_names(output) == ["door", "gate"]


def test_unique_preserve_order_keeps_first_occurrence() -> None:
    """Dedupe names without reordering."""
    assert unique_preserve_order(["gate", "door", "gate", "door"]) == [
        "gate",
        "door",
    ]


def test_build_collection_point_options_preserves_api_order() -> None:
    """Options keep API order instead of sorting alphabetically."""
    assert build_collection_point_options(["gate", "door", "gate"]) == [
        PARAM_COLLECTION_POINT_PROMPT,
        "gate",
        "door",
    ]

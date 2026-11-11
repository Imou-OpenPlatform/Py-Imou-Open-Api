"""v2_target_map.yaml structure and PTZ resolution."""

from pathlib import Path

import pytest
from pyimouapi.capability.binding import (
    cached_v2_target_map,
    load_v2_target_map,
    resolve_ptz_target_id,
)

# imou_life P0 bindings (Canvas has ~71 rows; yaml is the integration subset).
EXPECTED_P0_HA_KEY_COUNT = 41


def test_load_packaged_map() -> None:
    bindings = load_v2_target_map()
    keys = {row.ha_key for row in bindings}
    assert len(keys) == EXPECTED_P0_HA_KEY_COUNT
    assert len(bindings) >= EXPECTED_P0_HA_KEY_COUNT
    keys = {row.ha_key for row in bindings}
    assert "ab_alarm_sound" in keys
    assert "bulb" in keys
    assert "wide_dynamic" in keys
    wide = next(row for row in bindings if row.ha_key == "wide_dynamic")
    assert wide.ha_platform == "select"
    assert wide.target_id == "image.wdr.mode"


def test_cached_map_matches_file() -> None:
    cached = cached_v2_target_map()
    fresh = tuple(load_v2_target_map())
    assert cached == fresh


def test_bulb_composite_properties() -> None:
    bulb = next(row for row in load_v2_target_map() if row.ha_key == "bulb")
    assert bulb.kind == "composite"
    assert bulb.gate_property == "light.white.mode"
    assert "light.white.colorLevel" in bulb.properties
    assert "light.white.hue" in bulb.properties


def test_power_sensors_share_read_service() -> None:
    bindings = load_v2_target_map()
    outlet = [row for row in bindings if row.target_id == "power.outlet.read"]
    fields = {row.ha_key: row.output_field for row in outlet}
    assert fields["power"] == "power"
    assert fields["voltage"] == "voltage"
    assert fields["switch_cnt"] == "switch_cnt"


@pytest.mark.parametrize(
    ("services", "expected"),
    [
        ({"ptz.aim.step", "ptz.aim.relative"}, "ptz.aim.step"),
        ({"ptz.aim.relative"}, "ptz.aim.relative"),
        (set(), None),
    ],
)
def test_resolve_ptz_target_id(services: set[str], expected: str | None) -> None:
    assert resolve_ptz_target_id(services) == expected


def test_map_file_path_override(tmp_path: Path) -> None:
    mini = tmp_path / "mini.yaml"
    mini.write_text(
        "version: 1\nbindings:\n"
        "  - ha_key: motion_detect\n"
        "    target_id: detection.motion.enabled\n"
        "    kind: property\n"
        "    ha_platform: switch\n",
        encoding="utf-8",
    )
    rows = load_v2_target_map(mini)
    assert len(rows) == 1
    assert rows[0].ha_key == "motion_detect"

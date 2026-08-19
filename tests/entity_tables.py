"""Shared harness describing how each entity table is turned into entities.

Used by the golden test that pins the configured output of every table entry.
"""

from typing import Any

from pyimouapi.const import (
    ALARM_CONTROL_PANEL_REF,
    BINARY_SENSOR_TYPE_ABILITY,
    BINARY_SENSOR_TYPE_REF,
    BUTTON_TYPE_ABILITY,
    BUTTON_TYPE_REF,
    PARAM_ABILITY,
    PARAM_REF,
    SELECT_TYPE_ABILITY,
    SELECT_TYPE_REF,
    SENSOR_TYPE_ABILITY,
    SENSOR_TYPE_REF,
    SWITCH_TYPE_ABILITY,
    SWITCH_TYPE_REF,
    TEXT_TYPE_REF,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

# No table lists this product, so nothing is filtered out by the excepts rule.
PRODUCT_ID = "product-not-in-any-excepts"

# name -> (table, configure function, attribute holding the configured entities)
REF_TABLES: dict[str, tuple[dict, Any, str]] = {
    "switch": (
        SWITCH_TYPE_REF,
        ImouHaDeviceManager.configure_switch_by_ref,
        "switches",
    ),
    "button": (
        BUTTON_TYPE_REF,
        ImouHaDeviceManager.configure_button_by_ref,
        "buttons",
    ),
    "select": (
        SELECT_TYPE_REF,
        ImouHaDeviceManager.configure_select_by_ref,
        "selects",
    ),
    "sensor": (
        SENSOR_TYPE_REF,
        ImouHaDeviceManager.configure_sensor_by_ref,
        "sensors",
    ),
    "binary_sensor": (
        BINARY_SENSOR_TYPE_REF,
        ImouHaDeviceManager.configure_binary_sensor_by_ref,
        "binary_sensors",
    ),
    "text": (TEXT_TYPE_REF, ImouHaDeviceManager.configure_text_by_ref, "texts"),
    "alarm_control_panel": (
        {"alarm_control_panel": ALARM_CONTROL_PANEL_REF},
        ImouHaDeviceManager.configure_alarm_control_panel_by_ref,
        "alarm_control_panel",
    ),
}

ABILITY_TABLES: dict[str, tuple[dict, Any, str]] = {
    "switch": (
        SWITCH_TYPE_ABILITY,
        ImouHaDeviceManager.configure_switch_by_ability,
        "switches",
    ),
    "button": (
        BUTTON_TYPE_ABILITY,
        ImouHaDeviceManager.configure_button_by_ability,
        "buttons",
    ),
    "select": (
        SELECT_TYPE_ABILITY,
        ImouHaDeviceManager.configure_select_by_ability,
        "selects",
    ),
    "sensor": (
        SENSOR_TYPE_ABILITY,
        ImouHaDeviceManager.configure_sensor_by_ability,
        "sensors",
    ),
    "binary_sensor": (
        BINARY_SENSOR_TYPE_ABILITY,
        ImouHaDeviceManager.configure_binary_sensor_by_ability,
        "binary_sensors",
    ),
}


def make_device() -> ImouHaDevice:
    """Return a device with no channel, so the device-level list is consulted."""
    device = ImouHaDevice("dev-1", "Device", "Imou", "Model", "1.0")
    device.set_product_id(PRODUCT_ID)
    return device


def ability_key(entry: Any) -> str:
    """Return the ability string of a table entry, which switches wrap in a dict."""
    return entry.get(PARAM_ABILITY) if isinstance(entry, dict) else entry


def configure(configure_fn: Any, supported: list[str]) -> ImouHaDevice:
    """Run a configure function against a device exposing the given refs."""
    device = make_device()
    configure_fn([], False, supported, device)
    return device


def snapshot_ref_table(name: str) -> dict[str, Any]:
    """Return the configured output for each entry, and for all entries at once."""
    table, configure_fn, attribute = REF_TABLES[name]
    per_entry: dict[str, Any] = {}
    if attribute == "alarm_control_panel":
        for entity_type, entries in table.items():
            for entry in entries:
                device = configure(configure_fn, [entry[PARAM_REF]])
                key = f"{entity_type}@{entry[PARAM_REF]}"
                per_entry[key] = device.alarm_control_panel
        every_ref = [
            entry[PARAM_REF] for entries in table.values() for entry in entries
        ]
        return {
            "per_entry": per_entry,
            "all_refs": configure(configure_fn, every_ref).alarm_control_panel,
        }
    for entity_type, entries in table.items():
        for entry in entries:
            device = configure(configure_fn, [entry[PARAM_REF]])
            key = f"{entity_type}@{entry[PARAM_REF]}"
            per_entry[key] = getattr(device, attribute).get(entity_type)
    every_ref = [entry[PARAM_REF] for entries in table.values() for entry in entries]
    return {
        "per_entry": per_entry,
        # Pins which entry wins when a device exposes all of them.
        "all_refs": getattr(configure(configure_fn, every_ref), attribute),
    }


def snapshot_ability_table(name: str) -> dict[str, Any]:
    """Return the configured output for each ability, and for all at once."""
    table, configure_fn, attribute = ABILITY_TABLES[name]
    per_entry: dict[str, Any] = {}
    for entity_type, entries in table.items():
        for entry in entries:
            ability = ability_key(entry)
            device = configure(configure_fn, [ability])
            per_entry[f"{entity_type}@{ability}"] = getattr(device, attribute).get(
                entity_type
            )
    every = [ability_key(entry) for entries in table.values() for entry in entries]
    return {
        "per_entry": per_entry,
        "all_abilities": getattr(configure(configure_fn, every), attribute),
    }


def full_snapshot() -> dict[str, Any]:
    """Return the configured output of every entity table."""
    return {
        "by_ref": {name: snapshot_ref_table(name) for name in REF_TABLES},
        "by_ability": {name: snapshot_ability_table(name) for name in ABILITY_TABLES},
    }


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    if "--update" not in sys.argv:
        raise SystemExit("pass --update to rewrite the golden snapshot")
    golden = Path(__file__).parent / "entity_tables_golden.json"
    golden.write_text(
        json.dumps(full_snapshot(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {golden}")

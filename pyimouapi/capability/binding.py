"""Load Ha V2 target bindings and resolve PTZ / bulb gate rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

PACKAGE_DATA = files("pyimouapi").joinpath("data")
MAP_FILE = "v2_target_map.yaml"


@dataclass(frozen=True, slots=True)
class TargetBinding:
    """One ha_key row from v2_target_map.yaml."""

    ha_key: str
    kind: str
    ha_platform: str
    scope: str = "channel"
    target_id: str | None = None
    write_target_id: str | None = None
    alternate_target_id: str | None = None
    resolve: str | None = None
    output_field: str | None = None
    struct_field: str | None = None
    gate_property: str | None = None
    properties: tuple[str, ...] = field(default_factory=tuple)
    extra_services: tuple[str, ...] = field(default_factory=tuple)


def _coerce_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _parse_binding(raw: dict[str, Any]) -> TargetBinding:
    return TargetBinding(
        ha_key=str(raw["ha_key"]),
        kind=str(raw["kind"]),
        ha_platform=str(raw["ha_platform"]),
        scope=str(raw.get("scope", "channel")),
        target_id=raw.get("target_id"),
        write_target_id=raw.get("write_target_id"),
        alternate_target_id=raw.get("alternate_target_id"),
        resolve=raw.get("resolve"),
        output_field=raw.get("output_field"),
        struct_field=raw.get("struct_field"),
        gate_property=raw.get("gate_property"),
        properties=_coerce_tuple(raw.get("properties")),
        extra_services=_coerce_tuple(raw.get("extra_services")),
    )


def load_v2_target_map(path: Path | None = None) -> list[TargetBinding]:
    """Load bindings from packaged yaml unless an explicit path is given."""
    if path is None:
        data = (PACKAGE_DATA / MAP_FILE).read_text(encoding="utf-8")
    else:
        data = path.read_text(encoding="utf-8")
    document = yaml.safe_load(data)
    if not isinstance(document, dict):
        msg = "v2_target_map root must be a mapping"
        raise ValueError(msg)
    rows = document.get("bindings")
    if not isinstance(rows, list):
        msg = "v2_target_map missing bindings list"
        raise ValueError(msg)
    return [_parse_binding(row) for row in rows]


@lru_cache
def cached_v2_target_map() -> tuple[TargetBinding, ...]:
    """Cached packaged map for repeated gate checks."""
    return tuple(load_v2_target_map())


def resolve_ptz_target_id(
    capability_services: set[str],
    primary: str = "ptz.aim.step",
    alternate: str = "ptz.aim.relative",
) -> str | None:
    """Pick PTZ invoke id: prefer step when both are listed."""
    has_primary = primary in capability_services
    has_alternate = alternate in capability_services
    if has_primary:
        return primary
    if has_alternate:
        return alternate
    return None


def bulb_gate_satisfied(
    capability_properties: set[str],
    binding: TargetBinding,
) -> bool:
    """True when the bulb composite gate property is on the device."""
    gate = binding.gate_property
    if not gate:
        return False
    return gate in capability_properties


def binding_by_ha_key(bindings: list[TargetBinding]) -> dict[str, TargetBinding]:
    """Index bindings by ha_key (last wins if duplicates)."""
    return {row.ha_key: row for row in bindings}


def binding_applies_to_device(
    binding: TargetBinding, channel_id: str | None, *, is_ipc: bool
) -> bool:
    """Whether a map row applies on this device/channel row."""
    scope = binding.scope
    if scope == "device":
        if channel_id is None:
            return True
        return is_ipc and channel_id == "0"
    if scope == "channel":
        return channel_id is not None
    return True


def binding_resolved_service_id(
    binding: TargetBinding, capability_services: set[str]
) -> str | None:
    """Resolve PTZ and similar rows to the invoke id present on the device."""
    if binding.resolve == "ptz_prefer_step":
        return resolve_ptz_target_id(capability_services)
    return binding.target_id


def binding_supported(
    binding: TargetBinding,
    capability_properties: set[str],
    capability_services: set[str],
    capability_events: set[str],
) -> bool:
    """True when the device list contains the binding's required target."""
    if binding.kind == "named_api":
        return True
    if binding.kind == "composite":
        return bulb_gate_satisfied(capability_properties, binding)
    if binding.kind == "property":
        return bool(binding.target_id and binding.target_id in capability_properties)
    if binding.kind == "service":
        target = binding.target_id
        if binding.resolve:
            target = binding_resolved_service_id(binding, capability_services)
        if not target or target not in capability_services:
            return False
        write_id = binding.write_target_id
        if write_id is not None and write_id not in capability_services:
            return False
        list_services = [s for s in binding.extra_services if s.endswith(".list")]
        return not list_services or any(s in capability_services for s in list_services)
    if binding.kind == "event":
        return bool(binding.target_id and binding.target_id in capability_events)
    return False

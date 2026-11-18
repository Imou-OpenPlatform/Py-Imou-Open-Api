"""Load Ha V2 target bindings and resolve PTZ / bulb gate rules."""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from ..bulb_light import BULB_PROP_SWITCH

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
    fallback_target_id: str | None = None
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
        fallback_target_id=raw.get("fallback_target_id"),
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


# Load once at import so discovery does not read yaml on the event loop.
cached_v2_target_map()


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
    device_type: str | None,
    property_ids: AbstractSet[str],
) -> bool:
    """True for a Lamp that exposes its controllable power property."""
    return (
        isinstance(device_type, str)
        and device_type.casefold() == "lamp"
        and BULB_PROP_SWITCH in property_ids
    )


def binding_by_ha_key(bindings: list[TargetBinding]) -> dict[str, TargetBinding]:
    """Index bindings by ha_key (last wins if duplicates)."""
    return {row.ha_key: row for row in bindings}


def applicable_capability_ids(
    device_ids: Iterable[str],
    channel_ids: Iterable[str],
    *,
    is_ipc: bool,
    channel_id: str | None,
) -> frozenset[str]:
    """Ids that may create entities on this device or channel row."""
    if channel_id is None:
        return frozenset(device_ids)
    ids = set(channel_ids)
    if is_ipc and channel_id == "0":
        ids.update(device_ids)
    return frozenset(ids)


def binding_resolved_service_id(
    binding: TargetBinding, capability_services: set[str]
) -> str | None:
    """Resolve PTZ and similar rows to the invoke id present on the device."""
    if binding.resolve == "ptz_prefer_step":
        return resolve_ptz_target_id(capability_services)
    return binding.target_id


def binding_supported(
    binding: TargetBinding,
    capability_ids: AbstractSet[str],
    *,
    device_type: str | None = None,
) -> bool:
    """True when the page ids contain this row's required targets."""
    if binding.kind == "named_api":
        return bool(binding.target_id and binding.target_id in capability_ids)
    if binding.kind == "composite":
        return bulb_gate_satisfied(device_type, capability_ids)
    if binding.kind == "property":
        return bool(
            (binding.target_id and binding.target_id in capability_ids)
            or (
                binding.fallback_target_id
                and binding.fallback_target_id in capability_ids
            )
        )
    if binding.kind == "service":
        target = binding.target_id
        if binding.resolve:
            target = binding_resolved_service_id(binding, set(capability_ids))
        if not target or target not in capability_ids:
            return False
        write_id = binding.write_target_id
        if write_id is not None and write_id not in capability_ids:
            return False
        list_services = [
            service for service in binding.extra_services if service.endswith(".list")
        ]
        return not list_services or any(
            service in capability_ids for service in list_services
        )
    if binding.kind == "event":
        return bool(binding.target_id and binding.target_id in capability_ids)
    return False

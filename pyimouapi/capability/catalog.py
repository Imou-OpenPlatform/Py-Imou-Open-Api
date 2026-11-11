"""Parse ``device.capability.list`` responses into a :class:`CapabilitySet`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EnumOption:
    """One enum entry from list ``dataType.specs.list``."""

    value: Any
    desc: str = ""


@dataclass(frozen=True, slots=True)
class PropertyCapability:
    """Metadata for a single v2 property id."""

    property_id: str
    access_mode: str
    data_type: str | None = None
    enum_options: tuple[EnumOption, ...] = field(default_factory=tuple)
    range_min: Any | None = None
    range_max: Any | None = None
    default_data: Any = None

    @property
    def readable(self) -> bool:
        return "r" in self.access_mode

    @property
    def writable(self) -> bool:
        return "w" in self.access_mode


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """Flattened property/service/event ids for one list query."""

    properties: dict[str, PropertyCapability]
    services: frozenset[str]
    events: frozenset[str]
    device_id: str | None = None
    product_id: str | None = None
    channel_id: str | None = None

    def has_property(self, target_id: str) -> bool:
        return target_id in self.properties

    def has_service(self, target_id: str) -> bool:
        return target_id in self.services

    def has_event(self, target_id: str) -> bool:
        return target_id in self.events


def _parse_enum_options(specs: dict[str, Any]) -> tuple[EnumOption, ...]:
    raw_list = specs.get("list")
    if not isinstance(raw_list, list):
        return ()
    options: list[EnumOption] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        options.append(
            EnumOption(value=item.get("value"), desc=str(item.get("desc") or ""))
        )
    return tuple(options)


def _parse_property(raw: dict[str, Any]) -> PropertyCapability | None:
    property_id = raw.get("propertyId")
    if not property_id:
        return None
    access_mode = str(raw.get("accessMode") or "")
    data_type_block = raw.get("dataType")
    data_type = None
    enum_options: tuple[EnumOption, ...] = ()
    range_min = None
    range_max = None
    if isinstance(data_type_block, dict):
        data_type = data_type_block.get("type")
        if isinstance(data_type, str):
            data_type = str(data_type)
        specs = data_type_block.get("specs")
        if isinstance(specs, dict):
            enum_options = _parse_enum_options(specs)
            raw_range = specs.get("range")
            if isinstance(raw_range, list) and len(raw_range) >= 2:
                range_min, range_max = raw_range[0], raw_range[1]
    return PropertyCapability(
        property_id=str(property_id),
        access_mode=access_mode,
        data_type=data_type,
        enum_options=enum_options,
        range_min=range_min,
        range_max=range_max,
        default_data=raw.get("defaultData"),
    )


def capability_set_from_list_response(data: dict[str, Any]) -> CapabilitySet:
    """Build a :class:`CapabilitySet` from ``result.data`` of capability.list."""
    properties: dict[str, PropertyCapability] = {}
    services: set[str] = set()
    events: set[str] = set()
    capabilities = data.get("capabilities")
    if isinstance(capabilities, list):
        for block in capabilities:
            if not isinstance(block, dict):
                continue
            props = block.get("properties")
            if isinstance(props, list):
                for raw_prop in props:
                    if not isinstance(raw_prop, dict):
                        continue
                    parsed = _parse_property(raw_prop)
                    if parsed is not None:
                        properties[parsed.property_id] = parsed
            for raw_svc in block.get("services") or []:
                if isinstance(raw_svc, dict) and raw_svc.get("serviceId"):
                    services.add(str(raw_svc["serviceId"]))
            for raw_evt in block.get("events") or []:
                if isinstance(raw_evt, dict) and raw_evt.get("eventId"):
                    events.add(str(raw_evt["eventId"]))
    return CapabilitySet(
        properties=properties,
        services=frozenset(services),
        events=frozenset(events),
        device_id=_optional_str(data.get("deviceId")),
        product_id=_optional_str(data.get("productId")),
        channel_id=_optional_str(data.get("channelId")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)

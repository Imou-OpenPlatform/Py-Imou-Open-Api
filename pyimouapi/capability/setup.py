"""Register :class:`ImouHaDevice` entities from ``device.capability.list`` ∩ map."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..alarm_mode import ALARM_MODES
from ..bulb_light import empty_bulb_state
from ..const import (
    PARAM_COLLECTION_POINT_PROMPT,
    PARAM_CURRENT_OPTION,
    PARAM_OPTIONS,
    PARAM_STATE,
    PARAM_SUPPORTED,
    PARAM_V2_LIST_SERVICE_ID,
    PARAM_V2_OUTPUT_FIELD,
    PARAM_V2_STRUCT_FIELD,
    PARAM_V2_TARGET_ID,
    PARAM_V2_WRITE_TARGET_ID,
    PARAM_VALUE_TYPE,
)
from ..property_on import property_is_on
from .binding import (
    TargetBinding,
    binding_applies_to_device,
    binding_resolved_service_id,
    binding_supported,
    cached_v2_target_map,
)
from .catalog import CapabilitySet, PropertyCapability

if TYPE_CHECKING:
    from ..ha_device import ImouHaDevice

_LOGGER = logging.getLogger(__name__)

_PLATFORM_ATTR = {
    "switch": "switches",
    "select": "selects",
    "sensor": "sensors",
    "binary_sensor": "binary_sensors",
    "button": "buttons",
    "text": "texts",
    "number": "texts",
}


def _select_options(prop: PropertyCapability) -> tuple[list[Any], Any, str]:
    if prop.enum_options:
        values = [opt.value for opt in prop.enum_options]
        default = prop.default_data if prop.default_data is not None else values[0]
        value_type = "int" if isinstance(default, int) else "str"
        return values, default, value_type
    if (
        prop.data_type == "int"
        and prop.range_min is not None
        and prop.range_max is not None
    ):
        values = list(range(int(prop.range_min), int(prop.range_max) + 1))
        default = prop.default_data if prop.default_data is not None else values[0]
        return values, default, "int"
    return [], prop.default_data or "", "str"


def _entity_bucket(
    ha_device: ImouHaDevice, binding: TargetBinding
) -> dict[str, Any] | None:
    platform = binding.ha_platform
    if platform == "alarm_control_panel":
        return None
    if platform == "light" and binding.ha_key == "bulb":
        return None
    if platform == "light":
        platform = "switch"
    attr = _PLATFORM_ATTR.get(platform)
    if not attr:
        return None
    return getattr(ha_device, attr)


def _add_property_switch(
    entities: dict[str, Any], binding: TargetBinding, prop: PropertyCapability
) -> None:
    default_on = property_is_on(prop.default_data)
    entities[binding.ha_key] = {
        PARAM_STATE: default_on if default_on is not None else False,
        PARAM_V2_TARGET_ID: binding.target_id,
    }


def _add_property_select(
    entities: dict[str, Any], binding: TargetBinding, prop: PropertyCapability
) -> None:
    options, current, value_type = _select_options(prop)
    entities[binding.ha_key] = {
        PARAM_V2_TARGET_ID: binding.target_id,
        PARAM_OPTIONS: options,
        PARAM_CURRENT_OPTION: current,
        PARAM_VALUE_TYPE: value_type,
    }


def _add_property_sensor(
    entities: dict[str, Any], binding: TargetBinding, prop: PropertyCapability
) -> None:
    entry: dict[str, Any] = {PARAM_V2_TARGET_ID: binding.target_id}
    if binding.output_field:
        entry[PARAM_V2_OUTPUT_FIELD] = binding.output_field
    if binding.struct_field:
        entry[PARAM_V2_STRUCT_FIELD] = binding.struct_field
    entities[binding.ha_key] = entry


def _add_service_button(
    entities: dict[str, Any],
    binding: TargetBinding,
    capability: CapabilitySet,
) -> None:
    service_id = binding_resolved_service_id(binding, set(capability.services))
    if not service_id:
        return
    entities[binding.ha_key] = {PARAM_V2_TARGET_ID: service_id}


def _add_service_sensor(entities: dict[str, Any], binding: TargetBinding) -> None:
    entities[binding.ha_key] = {
        PARAM_V2_TARGET_ID: binding.target_id,
        PARAM_V2_OUTPUT_FIELD: binding.output_field,
    }


def _configure_binding(
    ha_device: ImouHaDevice,
    binding: TargetBinding,
    capability: CapabilitySet,
) -> None:
    prop = (
        capability.properties.get(binding.target_id or "")
        if binding.target_id
        else None
    )
    platform = binding.ha_platform

    if binding.kind == "composite" and binding.ha_key == "bulb":
        ha_device.bulb_light = empty_bulb_state()
        ha_device.set_bulb_v2(True)
        ha_device.switches.pop("switch", None)
        return

    if platform == "alarm_control_panel" and binding.target_id:
        panel: dict[str, Any] = {
            PARAM_V2_TARGET_ID: binding.target_id,
            PARAM_STATE: None,
            PARAM_SUPPORTED: list(ALARM_MODES),
            PARAM_VALUE_TYPE: "int",
        }
        ha_device.alarm_control_panel = panel
        return

    bucket = _entity_bucket(ha_device, binding)
    if bucket is None:
        _LOGGER.debug(
            "Skipping v2 entity %s on platform %s (not wired yet)",
            binding.ha_key,
            platform,
        )
        return
    if binding.ha_key in bucket:
        return

    if binding.kind == "named_api" and platform == "button" and binding.target_id:
        bucket[binding.ha_key] = {PARAM_V2_TARGET_ID: binding.target_id}
        return

    if binding.kind == "service" and platform == "number":
        read_id = binding.target_id
        write_id = binding.write_target_id or binding.target_id
        if not read_id or not write_id:
            return
        bucket[binding.ha_key] = {
            PARAM_V2_TARGET_ID: read_id,
            PARAM_V2_WRITE_TARGET_ID: write_id,
            PARAM_STATE: "0",
        }
        return

    if binding.kind == "service" and platform == "select" and binding.target_id:
        list_services = [s for s in binding.extra_services if s.endswith(".list")]
        entry: dict[str, Any] = {
            PARAM_V2_TARGET_ID: binding.target_id,
            PARAM_OPTIONS: [PARAM_COLLECTION_POINT_PROMPT],
            PARAM_CURRENT_OPTION: PARAM_COLLECTION_POINT_PROMPT,
        }
        if list_services:
            entry[PARAM_V2_LIST_SERVICE_ID] = list_services[0]
        bucket[binding.ha_key] = entry
        return

    if binding.kind == "property" and prop is not None:
        if platform in ("switch", "light"):
            _add_property_switch(bucket, binding, prop)
        elif platform == "select":
            _add_property_select(bucket, binding, prop)
        elif platform == "sensor":
            _add_property_sensor(bucket, binding, prop)
        elif platform == "binary_sensor":
            default_on = property_is_on(prop.default_data)
            bucket[binding.ha_key] = {
                PARAM_V2_TARGET_ID: binding.target_id,
                PARAM_STATE: default_on if default_on is not None else False,
            }
        return

    if binding.kind == "service":
        if platform == "button":
            _add_service_button(bucket, binding, capability)
        elif platform == "sensor":
            _add_service_sensor(bucket, binding)


def configure_imou_ha_device_from_capability(
    ha_device: ImouHaDevice,
    capability: CapabilitySet,
    *,
    bindings: tuple[TargetBinding, ...] | None = None,
) -> None:
    """Populate entity dicts whose targets appear in ``capability``."""
    rows = bindings if bindings is not None else cached_v2_target_map()
    property_ids = set(capability.properties)
    service_ids = set(capability.services)
    event_ids = set(capability.events)
    for binding in rows:
        if not binding_applies_to_device(
            binding, ha_device.channel_id, is_ipc=ha_device.is_ipc
        ):
            continue
        if not binding_supported(binding, property_ids, service_ids, event_ids):
            continue
        _configure_binding(ha_device, binding, capability)

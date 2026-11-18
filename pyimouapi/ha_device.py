from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine, Mapping, Set
from enum import Enum
from math import isfinite
from typing import Any
from urllib.parse import urlparse

from .alarm_mode import to_friendly as alarm_mode_to_friendly
from .alarm_mode import to_raw as alarm_mode_to_raw
from .bulb_light import (
    BULB_PROP_SWITCH,
    BULB_V2_PROPERTY_IDS,
    apply_bulb_v2_properties,
    bulb_v2_property_ids_for_device,
)
from .capability.catalog import CapabilitySet
from .capability.client import (
    async_capability_list,
    async_property_get,
    async_property_set,
    async_service_invoke,
)
from .capability.setup import configure_imou_ha_device_from_capability
from .capability.v2_invoke import v2_service_input_data
from .collection_point import (
    build_collection_point_options,
    parse_iot_collection_names,
)
from .const import (
    ERROR_CODE_NO_PERMISSION,
    PARAM_AI_INSIGHT_STATUS,
    PARAM_BATTERY,
    PARAM_CHANNEL_ID,
    PARAM_CHANNEL_LIST,
    PARAM_CHANNEL_STATUS,
    PARAM_COLLECTION_POINT,
    PARAM_COLLECTION_POINT_PROMPT,
    PARAM_CS_STATUS,
    PARAM_CURRENT_OPTION,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_STATUS,
    PARAM_HD,
    PARAM_HUMIDITY_CURRENT,
    PARAM_OPTIONS,
    PARAM_OUTPUT_DATA,
    PARAM_PTZ,
    PARAM_STATE,
    PARAM_STATE_VARIANT,
    PARAM_STATUS,
    PARAM_STORAGE_USED,
    PARAM_SUPPORTED,
    PARAM_TEMPERATURE_CURRENT,
    PARAM_TOTAL_BYTES,
    PARAM_URL,
    PARAM_USED_BYTES,
    PARAM_V2_FALLBACK_TARGET_ID,
    PARAM_V2_LIST_SERVICE_ID,
    PARAM_V2_OUTPUT_FIELD,
    PARAM_V2_RAW_BY_OPTION,
    PARAM_V2_SOURCE_TARGET_IDS,
    PARAM_V2_STRUCT_FIELD,
    PARAM_V2_TARGET_ID,
    PARAM_V2_WRITE_TARGET_ID,
    PARAM_VALUE_TYPE,
)
from .device import ImouDevice, ImouDeviceManager, compose_iot_device_id
from .dormant_retry import DORMANT_WRITE_RETRY_WAIT_SECONDS, async_dormant_write_retry
from .exceptions import (
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
from .insight.cloud import (
    ai_insight_label_from_status,
    cloud_storage_label_from_cs_status,
)
from .property_on import property_is_on
from .select_option import to_friendly, to_raw
from .sensor import apply_sensor_state, normalize_sensor_state

_LOGGER: logging.Logger = logging.getLogger(__package__)


def _state_values_equal(current: Any, new: Any) -> bool:
    """Compare normalized HA state without treating bool as an integer."""
    if isinstance(current, bool) or isinstance(new, bool):
        return isinstance(current, bool) and isinstance(new, bool) and current is new
    return current == new


def _normalized_battery_level(value: Any) -> int | None:
    """Return one valid integer battery percentage."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or (isinstance(value, float) and not isfinite(value))
        or not 0 <= value <= 100
    ):
        return None
    return int(value)


def _battery_level_from_v2_info(data: Any) -> int | None:
    """Select one active battery percentage from power.battery.info."""
    if not isinstance(data, list):
        return None
    first_active_level: int | None = None
    for item in data:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        battery_type = item.get("type")
        level = _normalized_battery_level(item.get("elecPercent"))
        if (
            isinstance(category, bool)
            or not isinstance(category, int)
            or category != 1
            or isinstance(battery_type, bool)
            or not isinstance(battery_type, int)
            or battery_type < 0
            or level is None
        ):
            continue
        if battery_type == 0:
            return level
        if first_active_level is None:
            first_active_level = level
    return first_active_level


def _byte_count(value: Any) -> int | None:
    """Return a non-negative byte count, or None when the value is not one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not isfinite(value) or value < 0:
            return None
        return int(value)
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        if not isfinite(number) or number < 0:
            return None
        return int(number)
    return None


# storageState from storage.local.capacity. 1 is a normal card and 6 is
# "initialization succeeded"; both can carry a size. The other values cannot.
_HEALTHY_STORAGE_STATES = frozenset({"1", "6"})
_STORAGE_STATE_STATUS = {
    "0": "no_card",
    "2": "needs_init",
    "3": "restarting",
    "4": "initializing",
    "5": "init_failed",
    "7": "checking",
    "8": "uninitialized",
}
# storageAbnormal. 1 is also reported for healthy cards and for a missing
# card, so it is not a fault on its own. 4 only means lifetime cannot be read.
_STORAGE_FAULT_STATUS = {
    "2": "worn_out",
    "3": "needs_format",
    "5": "checking",
    "6": "unsupported",
    "7": "mount_failed",
    "8": "read_error",
    "9": "write_error",
    "10": "partition_error",
    "11": "read_only",
}


def _storage_value_from_capacity(raw: Any) -> int | str | None:
    """Return a used percentage, or a status key when no card has a size.

    Several cards on one device are summed when they report a size. A card
    without a size contributes its status instead, and only when no card
    had a size at all.
    """
    rows = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else None
    if not rows:
        return None
    total = 0
    used = 0
    status: str | None = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        state = str(row.get("storageState", "")).strip()
        fault = str(row.get("storageAbnormal", "")).strip()
        total_bytes = _byte_count(row.get(PARAM_TOTAL_BYTES))
        used_bytes = _byte_count(row.get(PARAM_USED_BYTES))
        if state in _HEALTHY_STORAGE_STATES and total_bytes and used_bytes is not None:
            total += total_bytes
            used += used_bytes
            continue
        if status is None:
            status = (
                _STORAGE_FAULT_STATUS.get(fault)
                or _STORAGE_STATE_STATUS.get(state)
                or "abnormal"
            )
    if total > 0:
        return int(used * 100 / total)
    return status


NUMBER_TYPE = [
    PARAM_STORAGE_USED,
    PARAM_TEMPERATURE_CURRENT,
    PARAM_HUMIDITY_CURRENT,
    PARAM_BATTERY,
]


def device_is_iot(device: ImouHaDevice) -> bool:
    """A device list row that includes productId is an IoT device."""
    product_id = device.product_id
    return isinstance(product_id, str) and bool(product_id.strip())


class ImouHaDevice:
    def __init__(
        self,
        device_id: str,
        device_name: str,
        manufacturer: str,
        model: str,
        swversion: str,
    ):
        self._device_id = device_id
        self._device_name = device_name
        self._manufacturer = manufacturer
        self._model = model
        self._swversion = swversion
        self._switches: dict[str, dict[str, Any]] = {}
        self._sensors: dict[str, dict[str, Any]] = {}
        apply_sensor_state(self._sensors, PARAM_STATUS, DeviceStatus.OFFLINE.value)
        self._binary_sensors: dict[str, dict[str, Any]] = {}
        self._selects: dict[str, dict[str, Any]] = {}
        self._buttons: dict[str, dict[str, Any]] = {}
        self._texts: dict[str, dict[str, Any]] = {}
        self._alarm_control_panel: dict[str, Any] | None = None
        self._bulb_light: dict[str, Any] | None = None
        self._channel_id: str | None = None
        self._channel_name: str | None = None
        self._is_ipc = False
        self._product_id: str | None = None
        self._product_device_type: str | None = None
        self._parent_product_id: str | None = None
        self._parent_device_id: str | None = None
        self._access_type = "PaaS"
        self._device_ability = "unknown"
        self._channel_ability = "unknown"
        self._capability_set: CapabilitySet | None = None
        self._bulb_v2: bool = False
        self._cs_status: str | None = None
        self._ai_insight_status: str | None = None
        self._play_token_v2: str | None = None

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def channel_id(self) -> str | None:
        return self._channel_id

    @property
    def channel_name(self) -> str | None:
        return self._channel_name

    @property
    def is_ipc(self) -> bool:
        return self._is_ipc

    @property
    def manufacturer(self) -> str:
        return self._manufacturer

    @property
    def model(self) -> str:
        return self._model

    @property
    def swversion(self) -> str:
        return self._swversion

    @property
    def switches(self) -> dict[str, dict[str, Any]]:
        return self._switches

    @property
    def sensors(self) -> dict[str, dict[str, Any]]:
        return self._sensors

    @property
    def binary_sensors(self) -> dict[str, dict[str, Any]]:
        return self._binary_sensors

    @property
    def selects(self) -> dict[str, dict[str, Any]]:
        return self._selects

    @property
    def buttons(self) -> dict[str, dict[str, Any]]:
        return self._buttons

    @property
    def texts(self) -> dict[str, dict[str, Any]]:
        return self._texts

    @property
    def alarm_control_panel(self) -> dict[str, Any] | None:
        return self._alarm_control_panel

    @alarm_control_panel.setter
    def alarm_control_panel(self, value: dict[str, Any] | None) -> None:
        self._alarm_control_panel = value

    @property
    def bulb_light(self) -> dict[str, Any] | None:
        """Color-bulb state, or None when this device is not that bulb."""
        return self._bulb_light

    @bulb_light.setter
    def bulb_light(self, value: dict[str, Any] | None) -> None:
        self._bulb_light = value

    @property
    def product_id(self) -> str | None:
        return self._product_id

    @property
    def product_device_type(self) -> str | None:
        return self._product_device_type

    @property
    def parent_product_id(self) -> str | None:
        return self._parent_product_id

    @property
    def access_type(self) -> str:
        return self._access_type

    @property
    def parent_device_id(self) -> str | None:
        return self._parent_device_id

    @property
    def device_ability(self) -> str:
        return self._device_ability

    @property
    def channel_ability(self) -> str:
        return self._channel_ability

    @property
    def device_name(self) -> str:
        return self._device_name

    def set_product_id(self, product_id: str) -> None:
        self._product_id = product_id

    def set_product_device_type(self, value: str | None) -> None:
        self._product_device_type = value

    def set_parent_product_id(self, parent_product_id: str) -> None:
        self._parent_product_id = parent_product_id

    def set_access_type(self, access_type: str) -> None:
        self._access_type = access_type

    def set_parent_device_id(self, parent_device_id: str) -> None:
        self._parent_device_id = parent_device_id

    def set_device_ability(self, device_ability: str) -> None:
        self._device_ability = device_ability

    @property
    def play_token_v2(self) -> str | None:
        """Encrypted play credential copied from the device list."""
        return self._play_token_v2

    def set_play_token_v2(self, play_token_v2: str | None) -> None:
        self._play_token_v2 = play_token_v2 or None

    def set_channel_ability(self, channel_ability: str) -> None:
        self._channel_ability = channel_ability

    @property
    def cs_status(self) -> str | None:
        """Raw cloud-storage status from the device list."""
        return self._cs_status

    def set_cs_status(self, cs_status: str | None) -> None:
        self._cs_status = cs_status

    @property
    def cloud_storage_label(self) -> str:
        """Cloud storage sensor state derived from ``csStatus``."""
        return cloud_storage_label_from_cs_status(self._cs_status)

    @property
    def ai_insight_status(self) -> str | None:
        """Raw AI Insight status from the device list."""
        return self._ai_insight_status

    def set_ai_insight_status(self, ai_insight_status: str | None) -> None:
        self._ai_insight_status = ai_insight_status

    @property
    def ai_insight_label(self) -> str:
        """AI Insight sensor state derived from ``aiInsightStatus``."""
        return ai_insight_label_from_status(self._ai_insight_status)

    @property
    def ai_insight_active(self) -> bool:
        """True when the device list says this channel has AI Insight."""
        return self.ai_insight_label == "active"

    def set_capability_set(self, capability_set: CapabilitySet) -> None:
        self._capability_set = capability_set

    @property
    def capability_set(self) -> CapabilitySet | None:
        return self._capability_set

    @property
    def capability_snapshot(self) -> tuple[str | None, CapabilitySet | None]:
        """Return the product type and V2 capabilities used for entity setup."""
        return (self._product_device_type, self._capability_set)

    def set_bulb_v2(self, enabled: bool = True) -> None:
        self._bulb_v2 = enabled

    @property
    def bulb_v2(self) -> bool:
        return self._bulb_v2

    def apply_identity(self, other: ImouHaDevice) -> None:
        """Copy name, model, and firmware from a freshly listed device."""
        self._device_name = other.device_name
        self._model = other.model
        self._swversion = other.swversion
        if other.channel_name is not None:
            self._channel_name = other.channel_name
        self._cs_status = other.cs_status
        self._ai_insight_status = other.ai_insight_status
        token = other.play_token_v2
        if isinstance(token, str) and token:
            self.set_play_token_v2(token)
        self._access_type = other.access_type

    def replace_capabilities(self, other: ImouHaDevice) -> list[str]:
        """Take another's entities, keeping state for keys that still exist.

        Returns entity suffixes that disappeared, so the caller can drop them.
        The online status sensor is never removed.
        """
        removed: list[str] = []
        for attr in (
            "switches",
            "sensors",
            "binary_sensors",
            "selects",
            "buttons",
            "texts",
        ):
            current: dict[str, dict[str, Any]] = getattr(self, attr)
            fresh: dict[str, dict[str, Any]] = getattr(other, attr)
            for key in list(current):
                if key in fresh or (attr == "sensors" and key == PARAM_STATUS):
                    continue
                del current[key]
                removed.append(key)
            for key, value in fresh.items():
                if key in current and PARAM_STATE in current[key]:
                    value = {**value, PARAM_STATE: current[key][PARAM_STATE]}
                current[key] = value
        if other.bulb_light is None:
            if self._bulb_light is not None:
                removed.append("bulb")
            self._bulb_light = None
        elif self._bulb_light is None:
            self._bulb_light = other.bulb_light
        if other.alarm_control_panel is None:
            if self._alarm_control_panel is not None:
                removed.append("alarm_control_panel")
            self._alarm_control_panel = None
        elif self._alarm_control_panel is None:
            self._alarm_control_panel = other.alarm_control_panel
        self._device_ability = other.device_ability
        self._channel_ability = other.channel_ability
        self._is_ipc = other.is_ipc
        self._product_device_type = other.product_device_type
        self._capability_set = other.capability_set
        self._bulb_v2 = other.bulb_v2
        return removed

    def __str__(self) -> str:
        return (
            f"device_id: {self._device_id}, product_id:{self._product_id},parent_device_id:{self._parent_product_id},device_name: {self._device_name}, manufacturer: {self._manufacturer}, "
            f"model: {self._model}, swversion: {self._swversion},selects:{self._selects},sensors:{self._sensors},"
            f"switches:{self._switches},binary_sensors:{self.binary_sensors},buttons:{self._buttons},texts:{self.texts}"
        )

    def set_channel_id(self, channel_id: str) -> None:
        self._channel_id = channel_id

    def set_channel_name(self, channel_name: str) -> None:
        self._channel_name = channel_name

    def set_is_ipc(self, is_ipc: bool) -> None:
        self._is_ipc = is_ipc


class ImouHaDeviceManager:
    """Builds Home Assistant devices from the account and keeps them current.

    A read that fails is logged and skipped so that one unhappy entity cannot
    stop a poll. Refused credentials are the exception to that: they are not
    one entity's problem, every later call will fail the same way, and the
    caller has to be told so it can ask the user to sign in again.
    """

    def __init__(
        self,
        device_manager: ImouDeviceManager,
        *,
        dormant_write_retry_wait_seconds: int = DORMANT_WRITE_RETRY_WAIT_SECONDS,
    ):
        self._delegate = device_manager
        self._dormant_write_retry_wait_seconds = dormant_write_retry_wait_seconds
        self._capability_by_channel: dict[
            tuple[str, str | None, str | None], CapabilitySet
        ] = {}

    @property
    def delegate(self) -> ImouDeviceManager:
        return self._delegate

    def set_dormant_write_retry_wait_seconds(self, wait_seconds: int) -> None:
        """How long to wait before retrying a control write on a sleeping device."""
        self._dormant_write_retry_wait_seconds = wait_seconds

    async def _async_dormant_write_retry(
        self,
        device: ImouHaDevice,
        operation: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        await async_dormant_write_retry(
            device,
            operation,
            wait_seconds=self._dormant_write_retry_wait_seconds,
        )

    async def async_set_bulb_light(
        self, device: ImouHaDevice, properties: dict[str, int]
    ) -> None:
        """Write bulb properties in one call and keep local state in step."""
        if device.bulb_light is None:
            raise RequestFailedException(f"device {device.device_id} has no color bulb")
        product_id = self._require_product_id(device)

        if device.bulb_v2:
            supported_property_ids = (
                set(device.capability_set.properties)
                if device.capability_set is not None
                else set()
            )
            v2_payload = {
                property_id: value
                for property_id, value in properties.items()
                if property_id in supported_property_ids
            }
            if not v2_payload:
                return

            async def _write_v2() -> None:
                await self._async_set_scoped_properties(
                    device, v2_payload, product_id=product_id
                )

            await self._async_dormant_write_retry(device, _write_v2)
            apply_bulb_v2_properties(device.bulb_light, v2_payload)
            return
        raise RequestFailedException(
            f"device {device.device_id} has no color bulb capability"
        )

    async def async_close(self) -> None:
        """Close the underlying Open API HTTP session."""
        await self._delegate.async_close()

    @staticmethod
    def _resolve_device_id(device: ImouHaDevice) -> str:
        return compose_iot_device_id(
            device.device_id, device.parent_device_id, device.parent_product_id
        )

    @staticmethod
    def _debug_missing_property(
        device: ImouHaDevice,
        property_id: str,
        *,
        source: str,
        kind: str | None = None,
        key: str | None = None,
    ) -> None:
        entity = f"{kind}.{key}" if kind and key else "unknown"
        _LOGGER.debug(
            "property %s not found (%s), device_id=%s channel_id=%s entity=%s",
            property_id,
            source,
            device.device_id,
            device.channel_id,
            entity,
        )

    @staticmethod
    def _collect_v2_property_entities(
        device: ImouHaDevice,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Entities backed by Open API v2 property ids (not legacy refs)."""
        entities: list[tuple[str, str, dict[str, Any]]] = []
        for kind, mapping in (
            ("switch", device.switches),
            ("select", device.selects),
            ("sensor", device.sensors),
            ("binary_sensor", device.binary_sensors),
            ("text", device.texts),
        ):
            for key, value in mapping.items():
                if PARAM_V2_TARGET_ID not in value:
                    continue
                if value.get(PARAM_V2_OUTPUT_FIELD):
                    continue
                if kind == "text" and value.get(PARAM_V2_WRITE_TARGET_ID):
                    continue
                entities.append((kind, key, value))
        if (
            device.alarm_control_panel
            and PARAM_V2_TARGET_ID in device.alarm_control_panel
        ):
            entities.append(
                (
                    "alarm_control_panel",
                    "alarm_control_panel",
                    device.alarm_control_panel,
                )
            )
        return entities

    @staticmethod
    def _v2_entity_raw_value(
        key: str, meta: dict[str, Any], values: Mapping[str, Any]
    ) -> tuple[bool, Any]:
        if key == PARAM_STORAGE_USED:
            target_id = str(meta[PARAM_V2_TARGET_ID])
            if target_id not in values:
                return False, None
            value = _storage_value_from_capacity(values[target_id])
            if value is None:
                return False, None
            return True, value
        if key == PARAM_BATTERY:
            scalar = _normalized_battery_level(values.get("power.battery.level"))
            if scalar is not None:
                return True, scalar
            if "power.battery.info" in values:
                level = _battery_level_from_v2_info(values["power.battery.info"])
                if level is not None:
                    return True, level
            return False, None
        target_id = str(meta[PARAM_V2_TARGET_ID])
        if target_id not in values:
            return False, None
        return True, values[target_id]

    def _apply_property_value(
        self,
        device: ImouHaDevice,
        kind: str,
        key: str,
        meta: dict[str, Any],
        raw_value: Any,
    ) -> bool:
        struct_field = meta.get(PARAM_V2_STRUCT_FIELD)
        if struct_field:
            if not isinstance(raw_value, dict) or struct_field not in raw_value:
                return False
            raw_value = raw_value[struct_field]
        elif (
            isinstance(raw_value, dict)
            and kind in ("switch", "binary_sensor")
            and "enabled" in raw_value
        ):
            raw_value = raw_value["enabled"]
        if kind in ("switch", "binary_sensor"):
            parsed = property_is_on(raw_value)
            if parsed is None:
                return False
            target = device.switches if kind == "switch" else device.binary_sensors
            if _state_values_equal(target[key].get(PARAM_STATE), parsed):
                return False
            target[key][PARAM_STATE] = parsed
        elif kind == "select":
            select_state = device.selects[key]
            raw_by_option = select_state.get(PARAM_V2_RAW_BY_OPTION)
            if isinstance(raw_by_option, dict):
                for friendly, raw in raw_by_option.items():
                    same_type_value = _state_values_equal(raw, raw_value)
                    same_text_value = not (
                        isinstance(raw, bool) or isinstance(raw_value, bool)
                    ) and str(raw) == str(raw_value)
                    if same_type_value or same_text_value:
                        if select_state.get(PARAM_CURRENT_OPTION) == friendly:
                            return False
                        select_state[PARAM_CURRENT_OPTION] = friendly
                        return True
                return False
            if isinstance(raw_value, dict | list) or raw_value is None:
                return False
            value = str(raw_value) if isinstance(raw_value, int) else raw_value
            normalized = to_friendly(key, value)
            if select_state.get(PARAM_CURRENT_OPTION) == normalized:
                return False
            select_state[PARAM_CURRENT_OPTION] = normalized
        elif kind in ("sensor", "text"):
            if isinstance(raw_value, dict | list) or raw_value is None:
                return False
            state = raw_value
            if kind == "sensor":
                normalized, variant = normalize_sensor_state(key, state)
                sensor = device.sensors[key]
                if (
                    _state_values_equal(sensor.get(PARAM_STATE), normalized)
                    and sensor.get(PARAM_STATE_VARIANT) == variant
                ):
                    return False
                apply_sensor_state(device.sensors, key, state)
            else:
                normalized = str(state) if isinstance(state, int) else state
                if _state_values_equal(device.texts[key].get(PARAM_STATE), normalized):
                    return False
                device.texts[key][PARAM_STATE] = normalized
        elif kind == "alarm_control_panel" and device.alarm_control_panel is not None:
            normalized = alarm_mode_to_friendly(raw_value)
            if device.alarm_control_panel.get(PARAM_STATE) == normalized:
                return False
            device.alarm_control_panel[PARAM_STATE] = normalized
        else:
            return False
        return True

    def apply_property_values(
        self, device: ImouHaDevice, values: Mapping[str, Any]
    ) -> bool:
        """Apply accepted property values to matching device entities."""
        if device.capability_set is not None:
            values = {
                key: value
                for key, value in values.items()
                if device.capability_set.has_property(key)
            }
            changed = False
            for kind, key, meta in self._collect_v2_property_entities(device):
                found, raw = self._v2_entity_raw_value(key, meta, values)
                if not found:
                    continue
                changed |= self._apply_property_value(device, kind, key, meta, raw)
            if device.bulb_v2 and device.bulb_light is not None:
                present = {
                    prop_id: values[prop_id]
                    for prop_id in BULB_V2_PROPERTY_IDS
                    if prop_id in values
                }
                if present:
                    changed |= apply_bulb_v2_properties(device.bulb_light, present)
            return changed
        return False

    @staticmethod
    def _require_product_id(device: ImouHaDevice) -> str:
        """Return the product id an Open API v2 call needs, or say why there is none.

        Callers reach these paths only for devices that carry one, so this
        turns a would-be request with a null key into a named failure.
        """
        if device.product_id is None:
            raise RequestFailedException(
                f"device {device.device_id} has no product_id for an iot request"
            )
        return device.product_id

    async def _async_press_button_by_v2(
        self,
        device: ImouHaDevice,
        button_type: str,
        service_id: str,
        duration: int,
    ) -> None:
        if service_id == "device.reboot.execute":
            await self.delegate.async_restart_device(
                device.device_id, device.product_id
            )
            return
        input_data = v2_service_input_data(service_id, button_type, duration)
        channel_id = self._channel_id_for_service(device, service_id, ipc_default=True)
        await async_service_invoke(
            self.delegate.api_client,
            device_id=device.device_id,
            service_id=service_id,
            input_data=input_data,
            channel_id=channel_id,
            product_id=device.product_id,
        )

    async def _async_update_v2_service_entities(self, device: ImouHaDevice) -> bool:
        """Poll sensors that read through a v2 service ``outputData``."""
        by_service: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for sensor_type, meta in device.sensors.items():
            service_id = meta.get(PARAM_V2_TARGET_ID)
            output_field = meta.get(PARAM_V2_OUTPUT_FIELD)
            if not service_id or not output_field:
                continue
            by_service.setdefault(str(service_id), []).append((sensor_type, meta))
        if not by_service:
            return True
        complete = True
        for service_id, items in by_service.items():
            try:
                data = await async_service_invoke(
                    self.delegate.api_client,
                    device_id=device.device_id,
                    service_id=service_id,
                    input_data={},
                    channel_id=self._channel_id_for_service(device, service_id),
                    product_id=device.product_id,
                )
            except InvalidAppIdOrSecretException:
                raise
            except Exception as exc:
                _LOGGER.warning(
                    "device.service.invoke %s failed for %s: %s",
                    service_id,
                    device.device_id,
                    exc,
                )
                complete = False
                continue
            output = data.get(PARAM_OUTPUT_DATA)
            if not isinstance(output, dict):
                complete = False
                continue
            fallback_items: list[tuple[str, dict[str, Any]]] = []
            for sensor_type, meta in items:
                field = meta[PARAM_V2_OUTPUT_FIELD]
                if field not in output:
                    if meta.get(PARAM_V2_FALLBACK_TARGET_ID):
                        fallback_items.append((sensor_type, meta))
                    else:
                        complete = False
                    continue
                apply_sensor_state(device.sensors, sensor_type, output[field])
            if not fallback_items:
                continue
            fallback_ids = [
                str(meta[PARAM_V2_FALLBACK_TARGET_ID]) for _, meta in fallback_items
            ]
            try:
                fallback_values = await self._async_read_scoped_properties(
                    device, fallback_ids
                )
            except InvalidAppIdOrSecretException:
                raise
            except Exception as exc:
                _LOGGER.warning(
                    "device.property.get service fallback failed for %s: %s",
                    device.device_id,
                    exc,
                )
                complete = False
                continue
            for sensor_type, meta in fallback_items:
                target_id = str(meta[PARAM_V2_FALLBACK_TARGET_ID])
                if target_id not in fallback_values:
                    complete = False
                    continue
                apply_sensor_state(
                    device.sensors, sensor_type, fallback_values[target_id]
                )
        return complete

    async def _async_update_v2_bulb_state(self, device: ImouHaDevice) -> bool:
        if device.bulb_light is None or not device.bulb_v2:
            return True
        capability = device.capability_set
        if capability is None:
            return True
        property_ids = list(bulb_v2_property_ids_for_device(set(capability.properties)))
        if not property_ids:
            return True
        try:
            values = await self._async_read_scoped_properties(device, property_ids)
        except InvalidAppIdOrSecretException:
            raise
        except Exception as exc:
            _LOGGER.warning(
                "device.property.get bulb failed for %s: %s",
                device.device_id,
                exc,
            )
            return False
        apply_bulb_v2_properties(device.bulb_light, values)
        return all(property_id in values for property_id in property_ids)

    def _channel_id_for_property(
        self, device: ImouHaDevice, property_id: str
    ) -> str | None:
        """Channel id for one property. Device scope omits it."""
        capability = device.capability_set
        if capability is not None:
            prop = capability.properties.get(property_id)
            if prop is not None and prop.scope == "device":
                return None
        return device.channel_id

    def _channel_id_for_service(
        self,
        device: ImouHaDevice,
        service_id: str,
        *,
        ipc_default: bool = False,
    ) -> str | None:
        """Channel id for one service. Device scope omits it."""
        capability = device.capability_set
        if (
            capability is not None
            and capability.service_scopes.get(service_id) == "device"
        ):
            return None
        if ipc_default and device.channel_id is None and device.is_ipc:
            return "0"
        return device.channel_id

    async def _async_set_scoped_properties(
        self,
        device: ImouHaDevice,
        properties: dict[str, Any],
        *,
        product_id: str | None = None,
    ) -> None:
        """Write properties without mixing device scope and channel scope."""
        groups: dict[str | None, dict[str, Any]] = {}
        for property_id, value in properties.items():
            channel_id = self._channel_id_for_property(device, property_id)
            groups.setdefault(channel_id, {})[property_id] = value
        resolved_product = device.product_id if product_id is None else product_id
        for channel_id, payload in groups.items():
            await async_property_set(
                self.delegate.api_client,
                device_id=device.device_id,
                channel_id=channel_id,
                product_id=resolved_product,
                properties=payload,
            )

    async def _async_read_scoped_properties(
        self, device: ImouHaDevice, property_ids: list[str]
    ) -> dict[str, Any]:
        """Read properties in scope groups. Device and channel ids cannot share a call."""
        groups: dict[str, list[str]] = {}
        capability = device.capability_set
        for property_id in property_ids:
            scope = "channel"
            if capability is not None:
                prop = capability.properties.get(property_id)
                if prop is not None and prop.scope:
                    scope = prop.scope
            groups.setdefault(scope, []).append(property_id)
        merged: dict[str, Any] = {}
        for scope, ids in groups.items():
            channel_id = None if scope == "device" else device.channel_id
            merged.update(
                await async_property_get(
                    self.delegate.api_client,
                    device_id=device.device_id,
                    channel_id=channel_id,
                    product_id=device.product_id,
                    properties=ids,
                )
            )
        return merged

    async def _async_update_v2_property_entities(self, device: ImouHaDevice) -> bool:
        """Refresh state for entities registered via capability.list."""
        entities = self._collect_v2_property_entities(device)
        if not entities:
            return True
        property_ids: list[str] = []
        seen: set[str] = set()
        capability = device.capability_set
        for _, _, meta in entities:
            raw_ids = meta.get(PARAM_V2_SOURCE_TARGET_IDS, [meta[PARAM_V2_TARGET_ID]])
            for raw_id in raw_ids:
                target_id = str(raw_id)
                if target_id in seen:
                    continue
                if capability is not None:
                    prop = capability.properties.get(target_id)
                    if prop is None or not prop.readable:
                        continue
                seen.add(target_id)
                property_ids.append(target_id)
        if not property_ids:
            return True
        try:
            values = await self._async_read_scoped_properties(device, property_ids)
        except InvalidAppIdOrSecretException:
            raise
        except Exception as exc:
            _LOGGER.warning(
                "device.property.get failed for %s: %s", device.device_id, exc
            )
            return False
        complete = True
        for kind, key, meta in entities:
            found, raw = self._v2_entity_raw_value(key, meta, values)
            if not found:
                complete = False
                target_id = str(meta[PARAM_V2_TARGET_ID])
                self._debug_missing_property(
                    device,
                    target_id,
                    source="device.property.get",
                    kind=kind,
                    key=key,
                )
                continue
            self._apply_property_value(device, kind, key, meta, raw)
        return complete

    async def async_update_devices_status(
        self,
        devices: list[ImouHaDevice],
        *,
        skip_iot_property_ids: Set[str] | None = None,
    ) -> set[str]:
        """Update many devices, sharing online/detail reads per physical device.

        ``skip_iot_property_ids`` must be physical ids as returned by this
        method (``compose_iot_device_id`` / ``_resolve_device_id``), not the
        bare ``did`` from a push payload. A gateway accessory is
        ``{device_id}_{parent_device_id}_{parent_product_id}``. Reuse this
        return set rather than building ids from push fields.

        When the detail list fails, the failure is raised so the caller can
        mark the poll failed. A single-device ``async_update_device_status``
        still logs ordinary read failures and returns.
        """
        if not devices:
            return set()
        await self._async_refresh_detail_status(devices)
        skip = skip_iot_property_ids or frozenset()
        groups: dict[str, list[ImouHaDevice]] = {}
        for device in devices:
            groups.setdefault(self._resolve_device_id(device), []).append(device)
        results = await asyncio.gather(
            *(
                self._async_update_device_group(group, skip_iot_property_ids=skip)
                for group in groups.values()
            ),
            return_exceptions=True,
        )
        fetched: set[str] = set()
        failures: list[BaseException] = []
        succeeded = 0
        for result in results:
            if isinstance(
                result, asyncio.CancelledError | InvalidAppIdOrSecretException
            ):
                raise result
            if isinstance(result, BaseException):
                _LOGGER.warning("Failed to update a device group: %s", result)
                failures.append(result)
                continue
            if isinstance(result, set):
                fetched.update(result)
                succeeded += 1
        if failures and succeeded == 0:
            raise failures[0]
        return fetched

    async def async_update_device_status(self, device: ImouHaDevice) -> set[str]:
        """Update device status, with the updater calling every time the coordinator is updated

        One device is its own outage, so a failed read is logged and skipped
        here rather than raised. Callers polling a whole account want
        ``async_update_devices_status``, which reports a total failure.
        """
        try:
            await self._async_refresh_detail_status([device])
            return await self._async_update_device_group([device])
        except InvalidAppIdOrSecretException:
            raise
        except Exception as e:
            _LOGGER.warning("Failed to update %s: %s", device.device_name, e)
            return set()

    async def _async_update_device_group(
        self,
        devices: list[ImouHaDevice],
        *,
        skip_iot_property_ids: Set[str] = frozenset(),
    ) -> set[str]:
        """Refresh one physical device and every HA channel that shares it."""
        if not devices:
            return set()
        online_devices = [
            device
            for device in devices
            if device.sensors[PARAM_STATUS][PARAM_STATE] != DeviceStatus.OFFLINE.value
        ]
        if len(online_devices) < len(devices):
            for device in devices:
                if device not in online_devices:
                    _LOGGER.debug(
                        "device %s is offline,stop updating", device.device_name
                    )
        if not online_devices:
            return set()

        fetched: set[str] = set()
        all_v2_devices = [d for d in devices if d.capability_set is not None]
        v2_devices = [d for d in online_devices if d.capability_set is not None]
        snapshot_complete = len(v2_devices) == len(all_v2_devices)
        for device in v2_devices:
            physical_id = self._resolve_device_id(device)
            if physical_id in skip_iot_property_ids and device_is_iot(device):
                continue
            snapshot_complete &= await self._async_update_v2_property_entities(device)
            snapshot_complete &= await self._async_update_v2_service_entities(device)
            snapshot_complete &= await self._async_update_v2_bulb_state(device)
        if (
            v2_devices
            and snapshot_complete
            and not (
                self._resolve_device_id(v2_devices[0]) in skip_iot_property_ids
                and device_is_iot(v2_devices[0])
            )
        ):
            fetched.add(physical_id)

        await self._async_gather_reads(
            [
                self._async_update_device_select_status(device)
                for device in online_devices
            ],
            online_devices[0],
            "entities",
        )
        for device in online_devices:
            _LOGGER.debug("update_device_status finish: %s", device)
        return fetched

    async def _async_refresh_detail_status(self, devices: list[ImouHaDevice]) -> None:
        """Set status, cloud storage, and AI Insight from one detail list.

        Channels that share a serial are one request. A serial the cloud
        omits is marked offline.
        """
        by_serial: dict[str, list[ImouHaDevice]] = {}
        for device in devices:
            by_serial.setdefault(device.device_id, []).append(device)
        listed = await self.delegate.async_list_device_details(list(by_serial))
        found = {
            str(item.get(PARAM_DEVICE_ID)): item
            for item in listed
            if isinstance(item, dict) and item.get(PARAM_DEVICE_ID) is not None
        }
        for serial, group in by_serial.items():
            item = found.get(serial)
            if item is None:
                for device in group:
                    apply_sensor_state(
                        device.sensors, PARAM_STATUS, DeviceStatus.OFFLINE.value
                    )
                continue
            self._apply_detail_list_item(group, item)

    def _apply_detail_list_item(
        self, devices: list[ImouHaDevice], item: dict[str, Any]
    ) -> None:
        """Write one detail-list device onto every channel that shares it."""
        channels = item.get(PARAM_CHANNEL_LIST) or []
        by_channel: dict[str, dict[str, Any]] = {}
        if isinstance(channels, list):
            for channel in channels:
                if (
                    isinstance(channel, dict)
                    and channel.get(PARAM_CHANNEL_ID) is not None
                ):
                    by_channel[str(channel[PARAM_CHANNEL_ID])] = channel
        device_status = item.get(PARAM_DEVICE_STATUS)
        for device in devices:
            try:
                if device.channel_id is None:
                    self._apply_online_value(device, device_status)
                    continue
                channel = by_channel.get(str(device.channel_id))
                if channel is None:
                    _LOGGER.debug(
                        "device.detail.list has no channel %s for %s; marking offline",
                        device.channel_id,
                        device.device_id,
                    )
                    apply_sensor_state(
                        device.sensors, PARAM_STATUS, DeviceStatus.OFFLINE.value
                    )
                    continue
                self._apply_online_value(
                    device, channel.get(PARAM_CHANNEL_STATUS, device_status)
                )
                self._apply_subscription_status(device, channel, item)
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.error(
                    "device.detail.list apply error for %s: %s",
                    device.device_name,
                    err,
                )

    @staticmethod
    def _apply_subscription_status(
        device: ImouHaDevice, channel: dict[str, Any], item: dict[str, Any]
    ) -> None:
        """Copy cloud storage and AI Insight from the channel, else the device.

        A missing field keeps the label already stored. A partial row must
        not clear a subscription we learned earlier.
        """
        cs_status = channel.get(PARAM_CS_STATUS)
        if cs_status is None:
            cs_status = item.get(PARAM_CS_STATUS)
        if cs_status is not None:
            device.set_cs_status(str(cs_status))
        insight = channel.get(PARAM_AI_INSIGHT_STATUS)
        if insight is None:
            insight = item.get(PARAM_AI_INSIGHT_STATUS)
        if insight is not None:
            device.set_ai_insight_status(str(insight))

    def _apply_online_value(self, device: ImouHaDevice, online: Any) -> None:
        """Write one onLine value, or offline when the field is missing."""
        if online is None:
            status = DeviceStatus.OFFLINE.value
        else:
            status = self.get_device_status(online)
        apply_sensor_state(device.sensors, PARAM_STATUS, status)

    def apply_online_status(self, device: ImouHaDevice, is_online: bool) -> None:
        """Update device online/offline sensor from push or poll."""
        status = DeviceStatus.ONLINE.value if is_online else DeviceStatus.OFFLINE.value
        apply_sensor_state(device.sensors, PARAM_STATUS, status)

    @staticmethod
    async def _async_gather_reads(
        coroutines: list[Coroutine[Any, Any, Any]], device: ImouHaDevice, what: str
    ) -> None:
        """Run status reads together, letting one failure not hide the rest."""
        for result in await asyncio.gather(*coroutines, return_exceptions=True):
            if isinstance(
                result, asyncio.CancelledError | InvalidAppIdOrSecretException
            ):
                raise result
            if isinstance(result, BaseException):
                _LOGGER.warning(
                    "Failed to update %s for %s: %s", what, device.device_name, result
                )

    async def _async_update_device_select_status(self, device: ImouHaDevice):
        """UPDATE SELECT STATUS"""
        coroutines: list[Coroutine[Any, Any, Any]] = []
        for select_type, _value in device.selects.items():
            if select_type == PARAM_COLLECTION_POINT:
                coroutines.append(self._async_update_device_collection_points(device))
        await self._async_gather_reads(coroutines, device, "selects")

    async def _async_update_device_collection_points(self, device: ImouHaDevice):
        """Refresh collection point preset names."""
        if device.channel_id is None:
            return
        try:
            names: list[str]
            select_state = device.selects[PARAM_COLLECTION_POINT]
            if device.capability_set is not None and not select_state.get(
                PARAM_V2_LIST_SERVICE_ID
            ):
                return
            list_service = select_state.get(PARAM_V2_LIST_SERVICE_ID)
            if not list_service:
                return
            data = await async_service_invoke(
                self.delegate.api_client,
                device_id=device.device_id,
                service_id=str(list_service),
                input_data={},
                channel_id=self._channel_id_for_service(device, str(list_service)),
                product_id=device.product_id,
            )
            output = data.get(PARAM_OUTPUT_DATA)
            names = parse_iot_collection_names(output) if output is not None else []
        except InvalidAppIdOrSecretException:
            raise
        except Exception as err:
            # A shared device can reject collection points on every refresh.
            # Keep the options already stored and do not warn each time.
            log = (
                _LOGGER.debug
                if isinstance(err, RequestFailedException)
                and err.api_code == ERROR_CODE_NO_PERMISSION
                else _LOGGER.warning
            )
            log(
                "Failed to fetch collection points for %s: %s",
                device.device_name,
                err,
            )
            return

        device.selects[PARAM_COLLECTION_POINT][PARAM_OPTIONS] = (
            build_collection_point_options(names)
        )
        device.selects[PARAM_COLLECTION_POINT][PARAM_CURRENT_OPTION] = (
            PARAM_COLLECTION_POINT_PROMPT
        )

    async def _async_select_collection_point_option(
        self, device: ImouHaDevice, option: str
    ) -> None:
        if option == PARAM_COLLECTION_POINT_PROMPT:
            return
        if device.channel_id is None:
            raise RequestFailedException("collection_point requires channel")

        select_state = device.selects[PARAM_COLLECTION_POINT]
        if device.capability_set is not None and not select_state.get(
            PARAM_V2_TARGET_ID
        ):
            raise RequestFailedException(
                "collection_point not available via device capabilities"
            )
        goto_service = select_state.get(PARAM_V2_TARGET_ID)
        if not goto_service:
            raise RequestFailedException(
                "collection_point not available via device capabilities"
            )
        await async_service_invoke(
            self.delegate.api_client,
            device_id=device.device_id,
            service_id=str(goto_service),
            input_data={"name": option},
            channel_id=self._channel_id_for_service(device, str(goto_service)),
            product_id=device.product_id,
        )
        select_state[PARAM_CURRENT_OPTION] = PARAM_COLLECTION_POINT_PROMPT

    async def async_get_device_stream(
        self, device: ImouHaDevice, live_resolution: str, live_protocol: str = ""
    ) -> str:
        """Return a fresh cloud RTSP URL from getStreamUrl.

        ``live_protocol`` is unused (kept so Home Assistant callers that
        still pass https keep working). Shared-account viewers cannot use
        HLS live addresses; getStreamUrl works for the owner and sharers.
        """
        del live_protocol
        stream_id = 0 if live_resolution == PARAM_HD else 1
        data = await self.delegate.async_get_rtsp_stream_url(
            device.device_id,
            device.channel_id,
            stream_id,
            device.product_id,
        )
        url = data.get(PARAM_URL) if data else None
        if not url:
            raise RequestFailedException(
                f"device {device.device_id} answered getStreamUrl without a url"
            )
        _LOGGER.debug("get_device_stream host=%s", urlparse(url).netloc)
        return url

    async def async_get_device_image(
        self, device: ImouHaDevice, wait_seconds: int
    ) -> bytes:
        """Ask the device for a fresh snapshot and fetch it.

        Failures are raised rather than logged and turned into no image. The
        caller cannot show one either way, and Home Assistant puts an ImouException
        in front of the user in their own language, where a bare None became
        "Unable to get image" with nothing to act on.
        """
        data = await self.delegate.async_get_device_snap(
            device.device_id, device.channel_id
        )
        if PARAM_URL not in data:
            raise RequestFailedException(
                f"device {device.device_id} answered a snapshot request without a url"
            )
        _LOGGER.debug("wait %s seconds to download a picture", wait_seconds)
        await asyncio.sleep(wait_seconds)
        return await self.delegate.async_download(data[PARAM_URL])

    async def async_get_devices(
        self,
        *,
        configure_device_ids: set[str] | None = None,
        skip_device_ids: set[str] | None = None,
    ) -> list[ImouHaDevice]:
        """Return Imou HA devices registered from ``device.capability.list`` only."""
        devices = []
        for device in await self.delegate.async_get_devices():
            should_configure = (
                configure_device_ids is None or device.device_id in configure_device_ids
            ) and not (bool(skip_device_ids) and device.device_id in skip_device_ids)
            # Prioritize whether it's a video device.
            if device.channels:
                for channel in device.channels:
                    imou_ha_device = self.build_device(device)
                    imou_ha_device.set_channel_id(channel.channel_id)
                    imou_ha_device.set_channel_name(channel.channel_name)
                    imou_ha_device.set_channel_ability(channel.channel_ability)
                    imou_ha_device.set_cs_status(channel.cs_status)
                    imou_ha_device.set_ai_insight_status(channel.ai_insight_status)
                    if (
                        should_configure
                        and not await self._async_try_configure_by_capability(
                            device, channel, imou_ha_device
                        )
                    ):
                        _LOGGER.warning(
                            "device.capability.list missing for %s ch%s; "
                            "no entities registered",
                            device.device_id,
                            channel.channel_id,
                        )
                    devices.append(imou_ha_device)
            elif device.product_id is not None:
                _LOGGER.debug(
                    "channels is none, device_id:%s,product_id:%s",
                    device.device_id,
                    device.product_id,
                )
                imou_ha_device = self.build_device(device)
                if (
                    should_configure
                    and not await self._async_try_configure_by_capability(
                        device, None, imou_ha_device
                    )
                ):
                    _LOGGER.warning(
                        "device.capability.list missing for %s; no entities registered",
                        device.device_id,
                    )
                devices.append(imou_ha_device)
        return devices

    @staticmethod
    def build_device(device: ImouDevice) -> ImouHaDevice:
        imou_ha_device = ImouHaDevice(
            device.device_id,
            device.device_name,
            device.brand,
            device.device_model,
            device.device_version,
        )
        if device.product_id is not None:
            imou_ha_device.set_product_id(device.product_id)
        imou_ha_device.set_access_type(device.access_type)
        imou_ha_device.set_product_device_type(device.product_device_type)
        if device.parent_product_id is not None:
            imou_ha_device.set_parent_product_id(device.parent_product_id)
        if device.parent_device_id is not None:
            imou_ha_device.set_parent_device_id(device.parent_device_id)
        imou_ha_device.set_is_ipc(device.is_ipc)
        imou_ha_device.set_device_ability(device.device_ability)
        token = getattr(device, "play_token_v2", None)
        if isinstance(token, str) and token:
            imou_ha_device.set_play_token_v2(token)
        return imou_ha_device

    async def async_press_button(
        self, device: ImouHaDevice, button_type: str, duration: int
    ):
        button_state = device.buttons.get(button_type, {})
        if service_id := button_state.get(PARAM_V2_TARGET_ID):
            await self._async_press_button_by_v2(
                device, button_type, str(service_id), duration
            )
            return
        if PARAM_PTZ in button_type:
            raise RequestFailedException("该设备没有云台能力")
        raise RequestFailedException(
            f"{button_type} is not exposed on this device capability set"
        )

    async def async_set_text_value(
        self, device: ImouHaDevice, text_type: str, text_value: str
    ):
        text_meta = device.texts[text_type]
        if text_meta.get(PARAM_V2_WRITE_TARGET_ID):
            await self._async_set_count_down_switch_time_v2(
                device, text_value, text_meta
            )
            return
        raise RequestFailedException(
            f"{text_type} is not exposed on this device capability set"
        )

    async def async_switch_operation(
        self, device: ImouHaDevice, switch_type: str, enable: bool
    ):
        if target_id := device.switches[switch_type].get(PARAM_V2_TARGET_ID):
            await self._async_switch_operation_by_v2(
                device, switch_type, enable, str(target_id)
            )
            return
        raise RequestFailedException(
            f"{switch_type} is not exposed on this device capability set"
        )

    async def async_select_option(
        self,
        device: ImouHaDevice,
        select_type: str,
        option: str,
    ):
        if select_type == PARAM_COLLECTION_POINT:
            await self._async_select_collection_point_option(device, option)
            return
        if target_id := device.selects[select_type].get(PARAM_V2_TARGET_ID):
            value_type = device.selects[select_type].get(PARAM_VALUE_TYPE, "str")
            await self._async_select_option_by_v2(
                device, select_type, option, str(target_id), value_type
            )
            device.selects[select_type][PARAM_CURRENT_OPTION] = option
            return
        raise RequestFailedException(
            f"{select_type} is not exposed on this device capability set"
        )

    @staticmethod
    def get_device_status(origin_value: object) -> str:
        """Map a detail-list word, or an older 0/1/3/4 code, to a status."""
        text = str(origin_value).strip() if origin_value is not None else ""
        match text.lower():
            case "1" | "online":
                return DeviceStatus.ONLINE.value
            case "0" | "offline":
                return DeviceStatus.OFFLINE.value
            case "4" | "sleep":
                return DeviceStatus.SLEEP.value
            case "3" | "upgrading":
                return DeviceStatus.UPGRADING.value
            case _:
                _LOGGER.warning("Unknown device status: %s", origin_value)
                return DeviceStatus.OFFLINE.value

    async def _async_try_configure_by_capability(
        self,
        device: ImouDevice,
        channel: Any,
        imou_ha_device: ImouHaDevice,
    ) -> bool:
        """Return True when v2 list + map registration succeeded.

        A successful list is kept for this process. Later discovery reuses it
        instead of calling ``device.capability.list`` on every poll.
        """
        channel_id = channel.channel_id if channel is not None else None
        cache_key = (device.device_id, channel_id, device.product_id)
        capability = self._capability_by_channel.get(cache_key)
        if capability is None:
            try:
                capability = await async_capability_list(
                    self.delegate.api_client,
                    device_id=device.device_id,
                    product_id=device.product_id,
                    channel_id=channel_id,
                )
            except InvalidAppIdOrSecretException:
                raise
            except ImouException as exc:
                _LOGGER.debug(
                    "device.capability.list failed for %s: %s",
                    device.device_id,
                    exc,
                )
                return False
            except (TypeError, ValueError, AttributeError) as exc:
                _LOGGER.debug(
                    "device.capability.list unavailable for %s: %s",
                    device.device_id,
                    exc,
                )
                return False
            self._capability_by_channel[cache_key] = capability
        if not (capability.properties or capability.services or capability.events):
            _LOGGER.debug(
                "device.capability.list empty for %s ch%s",
                device.device_id,
                channel_id,
            )
            return False
        imou_ha_device.set_capability_set(capability)
        configure_imou_ha_device_from_capability(imou_ha_device, capability)
        _LOGGER.debug(
            "device.capability.list %s ch%s properties=%s services=%s events=%s "
            "switches=%s buttons=%s",
            device.device_id,
            channel_id,
            sorted(capability.properties),
            sorted(capability.services),
            sorted(capability.events),
            sorted(imou_ha_device.switches),
            sorted(imou_ha_device.buttons),
        )
        return True

    async def async_set_alarm_mode(self, device: ImouHaDevice, mode: str) -> None:
        panel = device.alarm_control_panel
        if panel is None:
            raise ValueError("device has no alarm_control_panel")
        if mode not in panel[PARAM_SUPPORTED]:
            raise ValueError(f"unknown alarm mode: {mode!r}")
        write_option = alarm_mode_to_raw(mode)
        target_id = panel.get(PARAM_V2_TARGET_ID)
        if not target_id:
            raise RequestFailedException(
                "alarm_control_panel is not exposed on this device capability set"
            )
        await self._async_select_option_by_v2(
            device,
            "",
            write_option,
            str(target_id),
            panel.get(PARAM_VALUE_TYPE, "int"),
        )
        panel[PARAM_STATE] = mode

    async def _async_switch_operation_by_v2(
        self,
        device: ImouHaDevice,
        switch_type: str,
        enable: bool,
        target_id: str,
    ) -> None:
        payload = {target_id: 1 if enable else 0}

        async def _write() -> None:
            await self._async_set_scoped_properties(device, payload)

        await self._async_dormant_write_retry(device, _write)
        device.switches[switch_type][PARAM_STATE] = enable

    async def _async_select_option_by_v2(
        self,
        device: ImouHaDevice,
        select_type: str,
        option: str,
        target_id: str,
        value_type: str,
    ) -> None:
        if select_type:
            select_state = device.selects.get(select_type, {})
            raw_by_option = select_state.get(PARAM_V2_RAW_BY_OPTION)
            if isinstance(raw_by_option, dict) and option in raw_by_option:
                value: int | str = raw_by_option[option]
            elif value_type == "int":
                value = int(to_raw(select_type, option))
            else:
                value = option
        elif value_type == "int":
            value = int(option)
        else:
            value = option
        payload = {target_id: value}

        async def _write() -> None:
            await self._async_set_scoped_properties(device, payload)

        await self._async_dormant_write_retry(device, _write)

    @staticmethod
    def _countdown_minutes_from_v2_output(output: Any) -> str | None:
        if not isinstance(output, dict):
            return None
        for key in ("minutes", "countdownMinutes", "remainMinutes", "countdown"):
            value = output.get(key)
            if isinstance(value, (int, float)):
                return str(int(value))
            if isinstance(value, str) and value.isdigit():
                return value
        seconds = output.get("countdownSeconds")
        if isinstance(seconds, (int, float)):
            return str(int(seconds) // 60)
        return None

    async def _async_update_countdown_v2(
        self,
        device: ImouHaDevice,
        text_type: str,
        meta: dict[str, Any],
    ) -> None:
        read_id = meta.get(PARAM_V2_TARGET_ID)
        if not read_id:
            return
        try:
            data = await async_service_invoke(
                self.delegate.api_client,
                device_id=device.device_id,
                service_id=str(read_id),
                input_data={},
                channel_id=self._channel_id_for_service(device, str(read_id)),
                product_id=self._require_product_id(device),
            )
        except InvalidAppIdOrSecretException:
            raise
        except Exception as exc:
            _LOGGER.warning(
                "countdown read %s failed for %s: %s",
                read_id,
                device.device_id,
                exc,
            )
            return
        output = data.get(PARAM_OUTPUT_DATA)
        minutes = self._countdown_minutes_from_v2_output(output)
        if minutes is not None:
            device.texts[text_type][PARAM_STATE] = minutes

    async def _async_set_count_down_switch_time_v2(
        self,
        device: ImouHaDevice,
        text_value: str,
        meta: dict[str, Any],
    ) -> None:
        write_id = meta.get(PARAM_V2_WRITE_TARGET_ID)
        if not write_id:
            raise RequestFailedException("countdown missing v2 write service")
        if device.bulb_light is not None:
            is_on = await self._async_refresh_bulb_on(device)
        elif switch := device.switches.get("switch"):
            if not switch.get(PARAM_V2_TARGET_ID):
                raise RequestFailedException(
                    f"countdown on {device.device_id} has no switch to read"
                )
            props = await self._async_read_scoped_properties(
                device, [str(switch[PARAM_V2_TARGET_ID])]
            )
            is_on = bool(property_is_on(props.get(str(switch[PARAM_V2_TARGET_ID]))))
        else:
            raise RequestFailedException(
                f"countdown on {device.device_id} has no switch to read"
            )
        minutes = int(text_value)
        input_data = {
            "enable": 1,
            "countdown": minutes * 60,
            "action": 0 if is_on else 1,
        }

        async def _write() -> None:
            await async_service_invoke(
                self.delegate.api_client,
                device_id=device.device_id,
                service_id=str(write_id),
                input_data=input_data,
                channel_id=self._channel_id_for_service(device, str(write_id)),
                product_id=self._require_product_id(device),
            )

        await self._async_dormant_write_retry(device, _write)
        device.texts["count_down_switch"][PARAM_STATE] = str(text_value)

    async def _async_refresh_bulb_on(self, device: ImouHaDevice) -> bool:
        """Read the bulb relay so countdown follows the lamp, not a removed switch."""
        state = device.bulb_light
        if state is None:
            return False
        try:
            if device.bulb_v2:
                capability = device.capability_set
                outlet_id = BULB_PROP_SWITCH
                if capability is None or outlet_id not in capability.properties:
                    return bool(state["on"])
                properties = await self._async_read_scoped_properties(
                    device, [outlet_id]
                )
                if properties:
                    apply_bulb_v2_properties(state, properties)
            else:
                return bool(state["on"])
        except InvalidAppIdOrSecretException:
            raise
        except Exception as e:
            _LOGGER.error("_async_refresh_bulb_on fail:%s", e)
        return bool(state["on"])


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SLEEP = "sleep"
    UPGRADING = "upgrading"

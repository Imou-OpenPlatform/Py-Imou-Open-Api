"""Collection point (PTZ preset) parsing helpers."""

from __future__ import annotations

from typing import Any

from .const import IOT_COLLECTION_NAME_REF, PARAM_COLLECTION_POINT_PROMPT


def parse_paas_collection_names(data: dict[str, Any]) -> list[str]:
    """Extract preset names from getCollection PaaS response data."""
    names: list[str] = []
    for item in data.get("collections") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name and str(name) != PARAM_COLLECTION_POINT_PROMPT:
            names.append(str(name))
    return unique_preserve_order(names)


def _name_from_collection_item(item: dict[str, Any]) -> str | None:
    for key in ("Name", "name", IOT_COLLECTION_NAME_REF):
        value = item.get(key)
        if value:
            return str(value)
    return None


def parse_iot_collection_names(output_data: Any) -> list[str]:
    """Extract preset names from GetCollection IoT outputData."""
    names: list[str] = []
    if output_data is None:
        return names

    if isinstance(output_data, dict):
        for value in output_data.values():
            if isinstance(value, list):
                names.extend(_names_from_collection_items(value))
            elif isinstance(value, str) and value != PARAM_COLLECTION_POINT_PROMPT:
                names.append(value)
        return unique_preserve_order(names)

    if isinstance(output_data, list):
        if output_data and all(isinstance(item, dict) for item in output_data):
            if any(
                item.get("identifier") == "collection"
                or IOT_COLLECTION_NAME_REF in item
                or "Name" in item
                for item in output_data
            ):
                names.extend(_names_from_collection_items(output_data))
            else:
                for item in output_data:
                    if not isinstance(item, dict):
                        continue
                    nested = item.get("value")
                    if isinstance(nested, list):
                        names.extend(_names_from_collection_items(nested))
        return unique_preserve_order(names)

    return names


def _names_from_collection_items(items: list[Any]) -> list[str]:
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _name_from_collection_item(item)
        if name and name != PARAM_COLLECTION_POINT_PROMPT:
            names.append(name)
    return names


def unique_preserve_order(names: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def build_collection_point_options(names: list[str]) -> list[str]:
    """Build select options with placeholder first, preserving API order."""
    return [PARAM_COLLECTION_POINT_PROMPT, *unique_preserve_order(names)]

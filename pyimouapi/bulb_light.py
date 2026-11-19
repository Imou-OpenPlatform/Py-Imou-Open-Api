"""Color bulb state for one Home Assistant light.

White and color are color modes. Named scenes are effects. The relay is the
light itself, not a separate switch.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from math import isfinite
from typing import Any

BULB_PROP_SWITCH = "control.outlet.enabled"
BULB_PROP_MODE = "light.white.mode"
BULB_PROP_BRIGHTNESS = "light.white.level"
BULB_PROP_COLOR_TEMP = "light.white.colorTemperature"
BULB_PROP_HUE = "light.white.hue"
BULB_PROP_SATURATION = "light.white.saturation"
BULB_PROP_VALUE = "light.white.colorLevel"
BULB_PROP_SCENE = "light.white.scene"

MODE_WHITE = 0
MODE_COLOR = 1
MODE_SCENE = 2

MIN_KELVIN = 2700
MAX_KELVIN = 6500

BULB_V2_PROPERTY_IDS = (
    BULB_PROP_SWITCH,
    BULB_PROP_MODE,
    BULB_PROP_BRIGHTNESS,
    BULB_PROP_COLOR_TEMP,
    BULB_PROP_HUE,
    BULB_PROP_SATURATION,
    BULB_PROP_VALUE,
    BULB_PROP_SCENE,
)


def bulb_v2_property_ids_for_device(
    supported_property_ids: AbstractSet[str],
) -> tuple[str, ...]:
    """Property ids to read for a v2 bulb, limited to what capability.list reported."""
    return tuple(pid for pid in BULB_V2_PROPERTY_IDS if pid in supported_property_ids)


# Effect name shown on the light, and the scene enum the bulb stores.
BULB_SCENES: tuple[tuple[str, int], ...] = (
    ("Daylight", 0),
    ("Night light", 1),
    ("Movie", 2),
    ("Relax", 3),
    ("Romantic", 4),
    ("Party", 5),
    ("Christmas", 6),
    ("Halloween", 7),
    ("Wake up", 8),
)

_SCENE_BY_NAME = dict(BULB_SCENES)
_NAME_BY_SCENE = {value: name for name, value in BULB_SCENES}


def empty_bulb_state() -> dict[str, Any]:
    """Defaults match the thing model until the first property read."""
    return {
        "on": False,
        "mode": MODE_WHITE,
        "brightness": 50,
        "color_temp": 3500,
        "hue": 0,
        "saturation": 0,
        "value": 100,
        "scene": 0,
    }


def scene_effect_names() -> list[str]:
    """Effect list for the light card, in thing-model order."""
    return [name for name, _value in BULB_SCENES]


def scene_effect_name(scene: int) -> str | None:
    """Return the effect name for a scene enum, if we know it."""
    return _NAME_BY_SCENE.get(scene)


def percent_to_brightness(percent: int) -> int:
    """Map a 1-100 bulb level onto Home Assistant brightness 1-255."""
    clamped = max(1, min(100, percent))
    return max(1, min(255, round(clamped * 255 / 100)))


def brightness_to_percent(brightness: int) -> int:
    """Map Home Assistant brightness 0-255 onto a 1-100 bulb level."""
    clamped = max(0, min(255, brightness))
    return max(1, min(100, round(clamped * 100 / 255)))


def _as_int(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        if not isfinite(raw):
            return None
        return int(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def apply_bulb_v2_properties(state: dict[str, Any], values: dict[str, Any]) -> bool:
    """Apply accepted property ids and report whether any were assigned."""
    return apply_bulb_properties(state, values)


def apply_bulb_properties(state: dict[str, Any], values: dict[str, Any]) -> bool:
    """Apply accepted property ids and report whether normalized state changed."""
    changed = False
    if BULB_PROP_SWITCH in values:
        raw = values[BULB_PROP_SWITCH]
        if isinstance(raw, bool):
            if state.get("on") is not raw:
                state["on"] = raw
                changed = True
        else:
            parsed = _as_int(raw)
            if parsed is not None:
                is_on = parsed == 1
                if state.get("on") is not is_on:
                    state["on"] = is_on
                    changed = True
    for key, property_id in (
        ("mode", BULB_PROP_MODE),
        ("brightness", BULB_PROP_BRIGHTNESS),
        ("color_temp", BULB_PROP_COLOR_TEMP),
        ("hue", BULB_PROP_HUE),
        ("saturation", BULB_PROP_SATURATION),
        ("value", BULB_PROP_VALUE),
        ("scene", BULB_PROP_SCENE),
    ):
        if property_id not in values:
            continue
        parsed = _as_int(values[property_id])
        if parsed is None:
            continue
        normalized = _clamp_read(key, parsed)
        if state.get(key) != normalized:
            state[key] = normalized
            changed = True
    return changed


def properties_for_turn_off() -> dict[str, int]:
    """Turn the bulb off."""
    return {BULB_PROP_SWITCH: 0}


def properties_for_turn_on(
    state: dict[str, Any],
    *,
    brightness: int | None = None,
    color_temp_kelvin: int | None = None,
    hs_color: tuple[float, float] | None = None,
    effect: str | None = None,
) -> dict[str, int]:
    """Build one property write for light.turn_on.

    White mode is brightness plus color temperature. Color mode is hue,
    saturation, and its own brightness. A write only includes the values the
    caller passed, so moving color temperature does not copy the color
    brightness, and moving the color does not copy the white brightness.
    """
    payload: dict[str, int] = {BULB_PROP_SWITCH: 1}
    if effect is not None:
        scene = _SCENE_BY_NAME.get(effect)
        if scene is None:
            raise ValueError(f"unknown bulb effect: {effect}")
        payload[BULB_PROP_MODE] = MODE_SCENE
        payload[BULB_PROP_SCENE] = scene
        return payload
    if hs_color is not None:
        hue, saturation = hs_color
        payload[BULB_PROP_MODE] = MODE_COLOR
        payload[BULB_PROP_HUE] = max(0, min(360, round(hue)))
        payload[BULB_PROP_SATURATION] = max(0, min(100, round(saturation)))
        if brightness is not None:
            payload[BULB_PROP_VALUE] = max(
                1, min(100, brightness_to_percent(brightness))
            )
        return payload
    if color_temp_kelvin is not None:
        payload[BULB_PROP_MODE] = MODE_WHITE
        payload[BULB_PROP_COLOR_TEMP] = max(
            MIN_KELVIN, min(MAX_KELVIN, int(color_temp_kelvin))
        )
        if brightness is not None:
            payload[BULB_PROP_BRIGHTNESS] = max(
                1, min(100, brightness_to_percent(brightness))
            )
        return payload
    if brightness is not None:
        level = brightness_to_percent(brightness)
        if int(state["mode"]) == MODE_COLOR:
            payload[BULB_PROP_VALUE] = level
        else:
            # A scene (or any non-white mode) does not use the white slider.
            # Brightness alone moves the bulb back to white so the lamp matches.
            if int(state["mode"]) != MODE_WHITE:
                payload[BULB_PROP_MODE] = MODE_WHITE
            payload[BULB_PROP_BRIGHTNESS] = level
    return payload


def _clamp_read(key: str, value: int) -> int:
    """Keep a device reading inside the thing-model range."""
    if key == "brightness":
        return max(1, min(100, value))
    if key == "color_temp":
        return max(MIN_KELVIN, min(MAX_KELVIN, value))
    if key == "hue":
        return max(0, min(360, value))
    if key in ("saturation", "value"):
        return max(0, min(100, value))
    return value

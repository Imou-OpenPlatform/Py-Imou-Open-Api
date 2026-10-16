"""Color bulb state for one Home Assistant light.

White and color are color modes. Named scenes are effects. The relay is the
light itself, not a separate switch.
"""

from __future__ import annotations

from typing import Any

REF_SWITCH = "11900"
REF_MODE = "131800"
REF_BRIGHTNESS = "131900"
REF_COLOR_TEMP = "132000"
REF_HUE = "132100"
REF_SATURATION = "132200"
REF_VALUE = "132300"
REF_SCENE = "132400"

MODE_WHITE = 0
MODE_COLOR = 1
MODE_SCENE = 2

MIN_KELVIN = 2700
MAX_KELVIN = 6500

BULB_PROPERTY_REFS = (
    REF_SWITCH,
    REF_MODE,
    REF_BRIGHTNESS,
    REF_COLOR_TEMP,
    REF_HUE,
    REF_SATURATION,
    REF_VALUE,
    REF_SCENE,
)

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


def empty_bulb_state() -> dict[str, int | bool]:
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
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def apply_bulb_properties(state: dict[str, Any], values: dict[str, Any]) -> None:
    """Fold a ref→value map into bulb state. Unknown or empty values are skipped."""
    if REF_SWITCH in values:
        raw = values[REF_SWITCH]
        if isinstance(raw, bool):
            state["on"] = raw
        else:
            parsed = _as_int(raw)
            if parsed is not None:
                state["on"] = parsed == 1
    for key, ref in (
        ("mode", REF_MODE),
        ("brightness", REF_BRIGHTNESS),
        ("color_temp", REF_COLOR_TEMP),
        ("hue", REF_HUE),
        ("saturation", REF_SATURATION),
        ("value", REF_VALUE),
        ("scene", REF_SCENE),
    ):
        if ref not in values:
            continue
        parsed = _as_int(values[ref])
        if parsed is None:
            continue
        state[key] = _clamp_read(key, parsed)


def properties_for_turn_off() -> dict[str, int]:
    """Turn the bulb off."""
    return {REF_SWITCH: 0}


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
    payload: dict[str, int] = {REF_SWITCH: 1}
    if effect is not None:
        scene = _SCENE_BY_NAME.get(effect)
        if scene is None:
            raise ValueError(f"unknown bulb effect: {effect}")
        payload[REF_MODE] = MODE_SCENE
        payload[REF_SCENE] = scene
        return payload
    if hs_color is not None:
        hue, saturation = hs_color
        payload[REF_MODE] = MODE_COLOR
        payload[REF_HUE] = max(0, min(360, round(hue)))
        payload[REF_SATURATION] = max(0, min(100, round(saturation)))
        if brightness is not None:
            payload[REF_VALUE] = max(1, min(100, brightness_to_percent(brightness)))
        return payload
    if color_temp_kelvin is not None:
        payload[REF_MODE] = MODE_WHITE
        payload[REF_COLOR_TEMP] = max(
            MIN_KELVIN, min(MAX_KELVIN, int(color_temp_kelvin))
        )
        if brightness is not None:
            payload[REF_BRIGHTNESS] = max(
                1, min(100, brightness_to_percent(brightness))
            )
        return payload
    if brightness is not None:
        level = brightness_to_percent(brightness)
        if int(state["mode"]) == MODE_COLOR:
            payload[REF_VALUE] = level
        else:
            # A scene (or any non-white mode) does not use the white slider.
            # Brightness alone moves the bulb back to white so the lamp matches.
            if int(state["mode"]) != MODE_WHITE:
                payload[REF_MODE] = MODE_WHITE
            payload[REF_BRIGHTNESS] = level
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

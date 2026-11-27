"""Color bulb: one light, no duplicate relay switch."""

from unittest.mock import MagicMock

import pytest
from pyimouapi.bulb_light import (
    BULB_PROP_BRIGHTNESS,
    BULB_PROP_COLOR_TEMP,
    BULB_PROP_HUE,
    BULB_PROP_MODE,
    BULB_PROP_SATURATION,
    BULB_PROP_SCENE,
    BULB_PROP_SWITCH,
    BULB_PROP_VALUE,
    MODE_COLOR,
    MODE_SCENE,
    MODE_WHITE,
    apply_bulb_properties,
    brightness_to_percent,
    empty_bulb_state,
    properties_for_turn_off,
    properties_for_turn_on,
    scene_effect_name,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _device() -> ImouHaDevice:
    device = ImouHaDevice("bulb-1", "Bulb", "Imou", "L1", "1.0")
    device.set_product_id("3C1DUNTJ")
    return device


def test_apply_bulb_properties_reads_ints_and_bools() -> None:
    """Detail payloads use ints; a bool switch is still on or off."""
    state = empty_bulb_state()
    changed = apply_bulb_properties(
        state,
        {
            BULB_PROP_SWITCH: True,
            BULB_PROP_MODE: "1",
            BULB_PROP_HUE: 120,
            BULB_PROP_SATURATION: 80,
            BULB_PROP_VALUE: 40,
            BULB_PROP_SCENE: 2,
        },
    )
    assert changed is True
    assert state["on"] is True
    assert state["mode"] == MODE_COLOR
    assert state["hue"] == 120
    assert state["scene"] == 2
    assert scene_effect_name(2) == "Movie"


def test_apply_bulb_properties_ignores_normalized_equivalent_values() -> None:
    state = empty_bulb_state()
    state["on"] = True
    state["brightness"] = 100

    assert (
        apply_bulb_properties(
            state,
            {
                BULB_PROP_SWITCH: 1,
                BULB_PROP_BRIGHTNESS: 150,
            },
        )
        is False
    )


@pytest.mark.parametrize(
    ("ref", "key"),
    [
        (BULB_PROP_MODE, "mode"),
        (BULB_PROP_BRIGHTNESS, "brightness"),
        (BULB_PROP_COLOR_TEMP, "color_temp"),
        (BULB_PROP_HUE, "hue"),
        (BULB_PROP_SATURATION, "saturation"),
        (BULB_PROP_VALUE, "value"),
        (BULB_PROP_SCENE, "scene"),
    ],
)
@pytest.mark.parametrize("raw", [True, False])
def test_apply_bulb_properties_rejects_bool_for_numeric_fields(
    ref: str, key: str, raw: bool
) -> None:
    state = empty_bulb_state()
    state[key] = 37
    before = dict(state)

    assert apply_bulb_properties(state, {ref: raw}) is False
    assert state == before


def test_apply_bulb_properties_rejects_true_when_numeric_state_is_one() -> None:
    state = empty_bulb_state()
    state.update(
        {
            "mode": 1,
            "brightness": 1,
            "color_temp": 1,
            "hue": 1,
            "saturation": 1,
            "value": 1,
            "scene": 1,
        }
    )
    before = dict(state)

    assert (
        apply_bulb_properties(
            state,
            {
                BULB_PROP_MODE: True,
                BULB_PROP_BRIGHTNESS: True,
                BULB_PROP_COLOR_TEMP: True,
                BULB_PROP_HUE: True,
                BULB_PROP_SATURATION: True,
                BULB_PROP_VALUE: True,
                BULB_PROP_SCENE: True,
            },
        )
        is False
    )
    assert state == before


@pytest.mark.parametrize("raw", [True, False])
def test_apply_bulb_properties_accepts_bool_for_switch(raw: bool) -> None:
    state = empty_bulb_state()
    state["on"] = not raw

    assert apply_bulb_properties(state, {BULB_PROP_SWITCH: raw}) is True
    assert state["on"] is raw


@pytest.mark.parametrize(
    "values",
    [
        {BULB_PROP_SWITCH: {}},
        {BULB_PROP_BRIGHTNESS: []},
        {
            BULB_PROP_HUE: object(),
            BULB_PROP_SATURATION: None,
            BULB_PROP_VALUE: "invalid",
        },
        {BULB_PROP_SWITCH: float("nan"), BULB_PROP_BRIGHTNESS: float("inf")},
    ],
)
def test_apply_bulb_properties_rejects_malformed_values(
    values: dict[str, object],
) -> None:
    state = empty_bulb_state()
    before = dict(state)

    assert apply_bulb_properties(state, values) is False
    assert state == before


def test_apply_property_values_ignores_legacy_bulb_refs() -> None:
    manager = ImouHaDeviceManager(MagicMock())
    device = _device()
    device.bulb_light = empty_bulb_state()
    before = dict(device.bulb_light)

    assert (
        manager.apply_property_values(
            device,
            {
                "11900": {},
                "131900": [],
                "132100": "invalid",
            },
        )
        is False
    )
    assert device.bulb_light == before

    assert manager.apply_property_values(device, {"131900": 75}) is False
    assert device.bulb_light == before


def test_turn_on_color_temperature_selects_white_mode() -> None:
    """A kelvin write is white mode, brightness, and the relay, in one payload."""
    payload = properties_for_turn_on(
        empty_bulb_state(),
        brightness=255,
        color_temp_kelvin=2700,
    )
    assert payload[BULB_PROP_SWITCH] == 1
    assert payload[BULB_PROP_MODE] == MODE_WHITE
    assert payload[BULB_PROP_COLOR_TEMP] == 2700
    assert payload[BULB_PROP_BRIGHTNESS] == 100


def test_color_temperature_alone_does_not_write_brightness() -> None:
    """Moving color temperature leaves both brightnesses where they were."""
    state = empty_bulb_state()
    state["mode"] = MODE_COLOR
    state["brightness"] = 21
    state["value"] = 3
    payload = properties_for_turn_on(state, color_temp_kelvin=4000)
    assert payload[BULB_PROP_MODE] == MODE_WHITE
    assert payload[BULB_PROP_COLOR_TEMP] == 4000
    assert BULB_PROP_BRIGHTNESS not in payload
    assert BULB_PROP_VALUE not in payload


def test_color_alone_does_not_write_color_brightness() -> None:
    """Moving hue or saturation leaves the color brightness alone."""
    state = empty_bulb_state()
    state["mode"] = MODE_WHITE
    state["brightness"] = 80
    state["value"] = 15
    payload = properties_for_turn_on(state, hs_color=(120, 40))
    assert payload[BULB_PROP_MODE] == MODE_COLOR
    assert payload[BULB_PROP_HUE] == 120
    assert payload[BULB_PROP_SATURATION] == 40
    assert BULB_PROP_VALUE not in payload
    assert BULB_PROP_BRIGHTNESS not in payload


def test_turn_on_hs_selects_color_mode() -> None:
    """A hue write is color mode and stores hue, saturation, and color brightness."""
    payload = properties_for_turn_on(
        empty_bulb_state(),
        hs_color=(200.4, 50),
        brightness=128,
    )
    assert payload[BULB_PROP_MODE] == MODE_COLOR
    assert payload[BULB_PROP_HUE] == 200
    assert payload[BULB_PROP_SATURATION] == 50
    assert payload[BULB_PROP_VALUE] == brightness_to_percent(128)


def test_turn_on_effect_selects_a_scene() -> None:
    """A named effect is scene mode plus that scene enum."""
    payload = properties_for_turn_on(empty_bulb_state(), effect="Party")
    assert payload == {
        BULB_PROP_SWITCH: 1,
        BULB_PROP_MODE: MODE_SCENE,
        BULB_PROP_SCENE: 5,
    }


def test_unknown_effect_is_rejected() -> None:
    """A name that is not a scene must not be sent to the bulb."""
    with pytest.raises(ValueError, match="unknown bulb effect"):
        properties_for_turn_on(empty_bulb_state(), effect="Music")


def test_turn_off_only_clears_the_relay() -> None:
    """Off does not rewrite color. The next on keeps the last look."""
    assert properties_for_turn_off() == {BULB_PROP_SWITCH: 0}


def test_brightness_only_while_a_scene_is_active_selects_white() -> None:
    """A brightness write must leave scene mode, or the slider and the lamp disagree."""
    state = empty_bulb_state()
    state["mode"] = MODE_SCENE
    payload = properties_for_turn_on(state, brightness=128)
    assert payload[BULB_PROP_MODE] == MODE_WHITE
    assert payload[BULB_PROP_BRIGHTNESS] == brightness_to_percent(128)
    assert BULB_PROP_SCENE not in payload


def test_brightness_maps_the_ends_of_the_home_assistant_range() -> None:
    """0 and 1 both become the bulb's minimum. 255 is full."""
    assert brightness_to_percent(0) == 1
    assert brightness_to_percent(1) == 1
    assert brightness_to_percent(255) == 100


def test_turn_on_clamps_kelvin_and_hue() -> None:
    """Values outside the thing model are clamped before they are written."""
    cold = properties_for_turn_on(empty_bulb_state(), color_temp_kelvin=1000)
    hot = properties_for_turn_on(empty_bulb_state(), color_temp_kelvin=9000)
    color = properties_for_turn_on(empty_bulb_state(), hs_color=(-20, 140))
    assert cold[BULB_PROP_COLOR_TEMP] == 2700
    assert hot[BULB_PROP_COLOR_TEMP] == 6500
    assert color[BULB_PROP_HUE] == 0
    assert color[BULB_PROP_SATURATION] == 100


def test_apply_clamps_color_read_from_the_device() -> None:
    """A detail payload outside the thing model must not be stored raw."""
    state = empty_bulb_state()
    apply_bulb_properties(
        state,
        {
            BULB_PROP_COLOR_TEMP: 9000,
            BULB_PROP_HUE: 400,
            BULB_PROP_SATURATION: 140,
            BULB_PROP_VALUE: -5,
            BULB_PROP_BRIGHTNESS: 0,
        },
    )
    assert state["color_temp"] == 6500
    assert state["hue"] == 360
    assert state["saturation"] == 100
    assert state["value"] == 0
    assert state["brightness"] == 1

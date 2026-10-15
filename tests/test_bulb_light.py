"""Color bulb: one light, no duplicate relay switch."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.bulb_light import (
    MODE_COLOR,
    MODE_SCENE,
    MODE_WHITE,
    REF_BRIGHTNESS,
    REF_COLOR_TEMP,
    REF_HUE,
    REF_MODE,
    REF_SATURATION,
    REF_SCENE,
    REF_SWITCH,
    REF_VALUE,
    apply_bulb_properties,
    brightness_to_percent,
    empty_bulb_state,
    properties_for_turn_off,
    properties_for_turn_on,
    scene_effect_name,
)
from pyimouapi.const import PARAM_REF, PARAM_STATE
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _device() -> ImouHaDevice:
    device = ImouHaDevice("bulb-1", "Bulb", "Imou", "L1", "1.0")
    device.set_product_id("3C1DUNTJ")
    return device


async def test_bulb_mode_replaces_the_relay_switch() -> None:
    """A color bulb is a light. The same relay must not also be a switch."""
    manager = ImouHaDeviceManager(MagicMock())
    device = _device()
    await manager._async_configure_device_by_ref(
        [],
        False,
        ["11900", "131800", "131900", "132000", "132400"],
        device,
    )
    assert device.bulb_light is not None
    assert device.bulb_light["mode"] == MODE_WHITE
    assert "switch" not in device.switches


async def test_plug_relay_stays_a_switch_without_bulb_mode() -> None:
    """A plug that only reports the relay still gets the switch."""
    manager = ImouHaDeviceManager(MagicMock())
    device = _device()
    await manager._async_configure_device_by_ref([], False, ["11900"], device)
    assert device.bulb_light is None
    assert "switch" in device.switches


def test_apply_bulb_properties_reads_ints_and_bools() -> None:
    """Detail payloads use ints; a bool switch is still on or off."""
    state = empty_bulb_state()
    apply_bulb_properties(
        state,
        {
            REF_SWITCH: True,
            REF_MODE: "1",
            REF_HUE: 120,
            REF_SATURATION: 80,
            REF_VALUE: 40,
            REF_SCENE: 2,
        },
    )
    assert state["on"] is True
    assert state["mode"] == MODE_COLOR
    assert state["hue"] == 120
    assert state["scene"] == 2
    assert scene_effect_name(2) == "Movie"


def test_turn_on_color_temperature_selects_white_mode() -> None:
    """A kelvin write is white mode, brightness, and the relay, in one payload."""
    payload = properties_for_turn_on(
        empty_bulb_state(),
        brightness=255,
        color_temp_kelvin=2700,
    )
    assert payload[REF_SWITCH] == 1
    assert payload[REF_MODE] == MODE_WHITE
    assert payload[REF_COLOR_TEMP] == 2700
    assert payload[REF_BRIGHTNESS] == 100


def test_turn_on_hs_selects_color_mode() -> None:
    """A hue write is color mode and stores hue, saturation, and color brightness."""
    payload = properties_for_turn_on(
        empty_bulb_state(),
        hs_color=(200.4, 50),
        brightness=128,
    )
    assert payload[REF_MODE] == MODE_COLOR
    assert payload[REF_HUE] == 200
    assert payload[REF_SATURATION] == 50
    assert payload[REF_VALUE] == brightness_to_percent(128)


def test_turn_on_effect_selects_a_scene() -> None:
    """A named effect is scene mode plus that scene enum."""
    payload = properties_for_turn_on(empty_bulb_state(), effect="Party")
    assert payload == {REF_SWITCH: 1, REF_MODE: MODE_SCENE, REF_SCENE: 5}


def test_unknown_effect_is_rejected() -> None:
    """A name that is not a scene must not be sent to the bulb."""
    with pytest.raises(ValueError, match="unknown bulb effect"):
        properties_for_turn_on(empty_bulb_state(), effect="Music")


def test_turn_off_only_clears_the_relay() -> None:
    """Off does not rewrite color. The next on keeps the last look."""
    assert properties_for_turn_off() == {REF_SWITCH: 0}


def test_brightness_only_while_a_scene_is_active_selects_white() -> None:
    """A brightness write must leave scene mode, or the slider and the lamp disagree."""
    state = empty_bulb_state()
    state["mode"] = MODE_SCENE
    payload = properties_for_turn_on(state, brightness=128)
    assert payload[REF_MODE] == MODE_WHITE
    assert payload[REF_BRIGHTNESS] == brightness_to_percent(128)
    assert REF_SCENE not in payload


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
    assert cold[REF_COLOR_TEMP] == 2700
    assert hot[REF_COLOR_TEMP] == 6500
    assert color[REF_HUE] == 0
    assert color[REF_SATURATION] == 100


def test_apply_clamps_color_read_from_the_device() -> None:
    """A detail payload outside the thing model must not be stored raw."""
    state = empty_bulb_state()
    apply_bulb_properties(
        state,
        {
            REF_COLOR_TEMP: 9000,
            REF_HUE: 400,
            REF_SATURATION: 140,
            REF_VALUE: -5,
            REF_BRIGHTNESS: 0,
        },
    )
    assert state["color_temp"] == 6500
    assert state["hue"] == 360
    assert state["saturation"] == 100
    assert state["value"] == 0
    assert state["brightness"] == 1


async def test_countdown_reads_the_bulb_when_the_relay_switch_is_gone() -> None:
    """Countdown used to look up the relay switch. A color bulb no longer has one."""
    delegate = MagicMock()
    delegate.async_get_iot_device_properties = AsyncMock(
        return_value={"properties": {REF_SWITCH: 1}}
    )
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    device = _device()
    device.bulb_light = empty_bulb_state()
    device.texts["count_down_switch"] = {PARAM_REF: "28800", PARAM_STATE: "0"}

    await manager.async_set_text_value(device, "count_down_switch", "5")

    sent = delegate.async_iot_device_control.await_args.args[3]
    assert sent["28602"] == 5 * 60
    assert sent["28603"] == 0
    assert device.texts["count_down_switch"][PARAM_STATE] == "5"


async def test_channel_zero_writes_the_resolved_id_and_the_raw_id() -> None:
    """Channel 0 follows the same two-call write as the other property setters."""
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    device = _device()
    device.set_channel_id("0")
    device.bulb_light = empty_bulb_state()
    payload = properties_for_turn_off()

    await manager.async_set_bulb_light(device, payload)

    assert delegate.async_set_iot_device_properties.await_count == 2
    first, second = delegate.async_set_iot_device_properties.await_args_list
    assert first.args == (device.device_id, "0", device.product_id, payload)
    assert second.args == (device.device_id, None, device.product_id, payload)


async def test_set_bulb_light_writes_once_and_updates_local_state() -> None:
    """The cloud call and the cached state use the same property map."""
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    device = _device()
    device.bulb_light = empty_bulb_state()
    payload = properties_for_turn_on(device.bulb_light, effect="Daylight")

    await manager.async_set_bulb_light(device, payload)

    delegate.async_set_iot_device_properties.assert_awaited_once_with(
        device.device_id, None, device.product_id, payload
    )
    assert device.bulb_light["on"] is True
    assert device.bulb_light["mode"] == MODE_SCENE
    assert device.bulb_light["scene"] == 0

"""Tests for collecting property-backed entities."""

from pyimouapi.const import (
    PARAM_REF,
    PARAM_REF_TYPE,
    PARAM_SERVICES,
    PARAM_STATE,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _device() -> ImouHaDevice:
    device = ImouHaDevice("dev1", "Camera", "Imou", "IPC", "1.0")
    device.set_product_id("pid1")
    return device


def test_collect_skips_services_and_entities_without_ref():
    device = _device()
    device.switches["motion"] = {PARAM_REF: "10001", PARAM_STATE: False}
    device.switches["ability"] = {PARAM_STATE: False}
    device.sensors["svc"] = {
        PARAM_REF: "20001",
        PARAM_REF_TYPE: PARAM_SERVICES,
        PARAM_STATE: "0",
    }
    device.texts["text"] = {PARAM_REF: "30001", PARAM_STATE: ""}

    entities = ImouHaDeviceManager._collect_property_entities(device)

    refs = {(kind, key) for kind, key, _ in entities}
    assert ("switch", "motion") in refs
    assert ("text", "text") in refs
    assert ("switch", "ability") not in refs
    assert ("sensor", "svc") not in refs


def test_collect_includes_all_property_entity_kinds():
    device = _device()
    device.switches["sw"] = {PARAM_REF: "1", PARAM_STATE: False}
    device.selects["sel"] = {PARAM_REF: "2", PARAM_STATE: "0"}
    device.sensors["sen"] = {PARAM_REF: "3", PARAM_STATE: "0"}
    device.binary_sensors["bin"] = {PARAM_REF: "4", PARAM_STATE: False}
    device.texts["txt"] = {PARAM_REF: "5", PARAM_STATE: ""}

    entities = ImouHaDeviceManager._collect_property_entities(device)
    kinds = {kind for kind, _, _ in entities}

    assert kinds == {"switch", "select", "sensor", "binary_sensor", "text"}

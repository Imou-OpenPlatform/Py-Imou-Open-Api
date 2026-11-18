"""Tests for the id an accessory behind a gateway is addressed by."""

import pytest
from pyimouapi.device import compose_iot_device_id
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def test_a_standalone_device_keeps_its_own_id() -> None:
    """A device with no parent is addressed by its plain id."""
    assert compose_iot_device_id("dev0", None, None) == "dev0"


def test_an_accessory_is_addressed_through_its_parent() -> None:
    """Both parent ids are joined onto the accessory's own id."""
    assert compose_iot_device_id("dev0", "gw1", "prodA") == "dev0_gw1_prodA"


@pytest.mark.parametrize(
    ("parent_device_id", "parent_product_id"),
    [("gw1", None), (None, "prodA"), ("", "prodA"), ("gw1", "")],
)
def test_half_a_parent_is_not_a_parent(
    parent_device_id: str | None, parent_product_id: str | None
) -> None:
    """Half the pairing information cannot address anything.

    The API sends both ids or neither. Splicing in whatever is present built an
    id containing the text "None", or raised while concatenating, depending on
    which of the four copies of this logic ran.
    """
    composed = compose_iot_device_id("dev0", parent_device_id, parent_product_id)

    assert composed == "dev0"
    assert "None" not in composed


def test_ha_device_resolution_matches_the_shared_helper() -> None:
    """The Home Assistant side addresses accessories the same way."""
    device = ImouHaDevice("dev0", "Sensor", "Imou", "DS1", "1.0")
    device.set_parent_device_id("gw1")
    device.set_parent_product_id("prodGW")

    assert ImouHaDeviceManager._resolve_device_id(device) == "dev0_gw1_prodGW"

    lonely = ImouHaDevice("dev1", "Sensor", "Imou", "DS1", "1.0")
    lonely.set_parent_product_id("prodGW")

    assert ImouHaDeviceManager._resolve_device_id(lonely) == "dev1"

"""Tests for the id an accessory behind a gateway is addressed by."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.device import ImouDevice, ImouDeviceManager, compose_iot_device_id
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


@pytest.mark.asyncio
async def test_ability_refs_survive_a_missing_parent_device_id() -> None:
    """A half-populated parent must not abort the whole device listing.

    The refs are fetched inside a gather without return_exceptions, so raising
    here used to take down the listing for every other device too.
    """
    device = ImouDevice("dev0", "Sensor", "1", "Imou", "DS1")
    device.set_product_id("prodA")
    device.set_parent_product_id("prodGW")

    client = MagicMock()
    manager = ImouDeviceManager(client)
    manager.async_get_iot_device_detail_info = AsyncMock(
        return_value={"abilityRefs": "1,2"}
    )

    await manager._async_update_device_ability_refs(device)

    assert manager.async_get_iot_device_detail_info.await_args.args[0] == "dev0"
    assert device.device_ability_refs == "1,2"


def test_ha_device_resolution_matches_the_shared_helper() -> None:
    """The Home Assistant side addresses accessories the same way."""
    device = ImouHaDevice("dev0", "Sensor", "Imou", "DS1", "1.0")
    device.set_parent_device_id("gw1")
    device.set_parent_product_id("prodGW")

    assert ImouHaDeviceManager._resolve_device_id(device) == "dev0_gw1_prodGW"

    lonely = ImouHaDevice("dev1", "Sensor", "Imou", "DS1", "1.0")
    lonely.set_parent_product_id("prodGW")

    assert ImouHaDeviceManager._resolve_device_id(lonely) == "dev1"

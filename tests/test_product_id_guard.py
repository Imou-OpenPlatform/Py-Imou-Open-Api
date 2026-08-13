"""Tests for iot calls made against a device that carries no product id.

Every iot endpoint is keyed on the product id. Callers reach those paths only
for devices that have one, so a missing one means a request would go out with
a null key and come back as an opaque server error.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def build_device(product_id: str | None) -> ImouHaDevice:
    """Return a device with or without a product id."""
    device = ImouHaDevice("dev0", "Sensor", "Imou", "DS21", "1.0")
    if product_id is not None:
        device.set_product_id(product_id)
    return device


@pytest.mark.asyncio
async def test_a_device_without_a_product_id_names_the_problem() -> None:
    """The failure says which device and why, rather than reaching the API."""
    manager = ImouHaDeviceManager(MagicMock())
    manager.delegate.async_get_iot_device_detail_info = AsyncMock()

    with pytest.raises(RequestFailedException, match="dev0"):
        await manager._async_fetch_device_detail(build_device(None))

    manager.delegate.async_get_iot_device_detail_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_device_with_a_product_id_is_passed_through() -> None:
    """The guard must not get in the way of the normal case."""
    manager = ImouHaDeviceManager(MagicMock())
    manager.delegate.async_get_iot_device_detail_info = AsyncMock(return_value={})

    await manager._async_fetch_device_detail(build_device("prod-1"))

    manager.delegate.async_get_iot_device_detail_info.assert_awaited_once_with(
        "dev0", "prod-1"
    )

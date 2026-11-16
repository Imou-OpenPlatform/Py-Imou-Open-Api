"""Multi-channel devices must share online and detail reads within one poll."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability
from pyimouapi.const import (
    PARAM_BATTERY,
    PARAM_CHANNEL_ID,
    PARAM_CHANNELS,
    PARAM_ONLINE,
    PARAM_OUTPUT_DATA,
    PARAM_PROPERTIES,
    PARAM_STATE,
    PARAM_STATUS,
    PARAM_V2_FALLBACK_TARGET_ID,
    PARAM_V2_OUTPUT_FIELD,
    PARAM_V2_SOURCE_TARGET_IDS,
    PARAM_V2_TARGET_ID,
)
from pyimouapi.exceptions import RequestFailedException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice, ImouHaDeviceManager


def _channel_device(
    channel_id: str,
    *,
    target_id: str = "control.outlet.enabled",
) -> ImouHaDevice:
    device = ImouHaDevice("nvr1", f"Cam {channel_id}", "Imou", "NVR", "1.0")
    device.set_product_id("pid1")
    device.set_channel_id(channel_id)
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    device.set_capability_set(
        CapabilitySet(
            properties={
                target_id: PropertyCapability(
                    property_id=target_id,
                    access_mode="rw",
                    data_type="int",
                )
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.switches["relay"] = {PARAM_V2_TARGET_ID: target_id, PARAM_STATE: False}
    return device


def _v2_device(device_id: str, product_id: str) -> ImouHaDevice:
    target = "control.outlet.enabled"
    device = ImouHaDevice(device_id, device_id, "Imou", "IPC", "1.0")
    device.set_product_id(product_id)
    device.set_channel_id("0")
    device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value
    device.set_capability_set(
        CapabilitySet(
            properties={
                target: PropertyCapability(
                    property_id=target,
                    access_mode="rw",
                    data_type="int",
                )
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.switches["relay"] = {PARAM_V2_TARGET_ID: target, PARAM_STATE: False}
    return device


def _battery_device(*source_ids: str) -> ImouHaDevice:
    device = ImouHaDevice("battery1", "Battery", "Imou", "Sensor", "1.0")
    device.set_product_id("pid")
    device.set_capability_set(
        CapabilitySet(
            properties={
                target: PropertyCapability(target, "r", "array")
                for target in source_ids
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    device.sensors[PARAM_BATTERY] = {
        PARAM_V2_TARGET_ID: source_ids[0],
        PARAM_V2_SOURCE_TARGET_IDS: list(source_ids),
    }
    return device


@pytest.mark.asyncio
async def test_switch_count_prefers_service_output_over_property_fallback() -> None:
    device = ImouHaDevice("plug1", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("pid")
    device.sensors["switch_cnt"] = {
        PARAM_V2_TARGET_ID: "power.outlet.read",
        PARAM_V2_OUTPUT_FIELD: "switch_cnt",
        PARAM_V2_FALLBACK_TARGET_ID: "control.outlet.switchCount",
    }
    manager = ImouHaDeviceManager(MagicMock())

    with (
        patch(
            "pyimouapi.ha_device.async_service_invoke",
            AsyncMock(return_value={PARAM_OUTPUT_DATA: {"switch_cnt": 7}}),
        ),
        patch(
            "pyimouapi.ha_device.async_property_get",
            AsyncMock(return_value={"control.outlet.switchCount": 3}),
        ) as prop_get,
    ):
        await manager._async_update_v2_service_entities(device)

    assert device.sensors["switch_cnt"][PARAM_STATE] == 7
    prop_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_switch_count_falls_back_when_service_field_is_missing() -> None:
    device = ImouHaDevice("plug1", "Plug", "Imou", "Plug", "1.0")
    device.set_product_id("pid")
    device.sensors["switch_cnt"] = {
        PARAM_V2_TARGET_ID: "power.outlet.read",
        PARAM_V2_OUTPUT_FIELD: "switch_cnt",
        PARAM_V2_FALLBACK_TARGET_ID: "control.outlet.switchCount",
    }
    manager = ImouHaDeviceManager(MagicMock())

    with (
        patch(
            "pyimouapi.ha_device.async_service_invoke",
            AsyncMock(return_value={PARAM_OUTPUT_DATA: {"power": 10}}),
        ),
        patch(
            "pyimouapi.ha_device.async_property_get",
            AsyncMock(return_value={"control.outlet.switchCount": 3}),
        ) as prop_get,
    ):
        await manager._async_update_v2_service_entities(device)

    assert device.sensors["switch_cnt"][PARAM_STATE] == 3
    prop_get.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_ids", "values", "expected"),
    [
        (("power.battery.level",), {"power.battery.level": 83}, 83),
        (
            ("power.battery.info",),
            {
                "power.battery.info": [
                    {
                        "state": 1,
                        "type": 0,
                        "elecPercent": 72,
                        "localTime": "20261116T100000",
                        "mAh": 2400,
                        "category": 1,
                    }
                ]
            },
            72,
        ),
        (
            ("power.battery.level", "power.battery.info"),
            {
                "power.battery.level": 83,
                "power.battery.info": [{"category": 1, "type": 0, "elecPercent": 72}],
            },
            83,
        ),
    ],
)
async def test_battery_source_precedence(
    source_ids: tuple[str, ...],
    values: dict[str, object],
    expected: int,
) -> None:
    device = _battery_device(*source_ids)
    manager = ImouHaDeviceManager(MagicMock())

    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value=values),
    ):
        await manager._async_update_v2_property_entities(device)

    assert device.sensors[PARAM_BATTERY][PARAM_STATE] == expected


@pytest.mark.asyncio
async def test_battery_info_prefers_type_zero_then_first_active() -> None:
    device = _battery_device("power.battery.info")
    manager = ImouHaDeviceManager(MagicMock())
    values = {
        "power.battery.info": [
            {"category": 0, "type": 0, "elecPercent": 99},
            {"category": 1, "type": 2, "elecPercent": 61},
            {"category": 1, "type": 0, "elecPercent": 74},
        ]
    }

    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value=values),
    ):
        await manager._async_update_v2_property_entities(device)

    assert device.sensors[PARAM_BATTERY][PARAM_STATE] == 74


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "malformed",
    [
        None,
        {},
        "bad",
        [None, "bad", {"category": 0, "type": 0, "elecPercent": 99}],
        [{"category": 1, "type": 0}],
        [{"category": 1, "type": 0, "elecPercent": "bad"}],
    ],
)
async def test_battery_info_ignores_malformed_values(malformed: object) -> None:
    device = _battery_device("power.battery.info")
    manager = ImouHaDeviceManager(MagicMock())

    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value={"power.battery.info": malformed}),
    ):
        await manager._async_update_v2_property_entities(device)

    assert PARAM_STATE not in device.sensors[PARAM_BATTERY]


@pytest.mark.asyncio
async def test_update_devices_status_shares_online_and_detail_across_channels() -> None:
    """One online call per NVR; each channel reads v2 properties."""
    ch0 = _channel_device("0")
    ch1 = _channel_device("1")

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={
            PARAM_ONLINE: "1",
            PARAM_CHANNELS: [
                {PARAM_CHANNEL_ID: 0, PARAM_ONLINE: "1"},
                {PARAM_CHANNEL_ID: 1, PARAM_ONLINE: "1"},
            ],
        }
    )

    manager = ImouHaDeviceManager(delegate)
    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value={"control.outlet.enabled": 1}),
    ) as prop_get:
        await manager.async_update_devices_status([ch0, ch1])

    assert delegate.async_get_device_online_status.await_count == 1
    assert prop_get.await_count == 2
    assert ch0.switches["relay"][PARAM_STATE] is True
    assert ch1.switches["relay"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_update_devices_status_still_calls_once_per_physical_device() -> None:
    """Distinct device ids still each get their own online call."""
    a = _v2_device("cam_a", "pid_a")
    b = _v2_device("cam_b", "pid_b")

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={
            PARAM_ONLINE: "1",
            PARAM_CHANNELS: [{PARAM_CHANNEL_ID: 0, PARAM_ONLINE: "1"}],
        }
    )

    manager = ImouHaDeviceManager(delegate)
    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value={"control.outlet.enabled": 0}),
    ) as prop_get:
        await manager.async_update_devices_status([a, b])

    assert delegate.async_get_device_online_status.await_count == 2
    assert prop_get.await_count == 2


@pytest.mark.asyncio
async def test_update_devices_status_skips_offline_channel_detail() -> None:
    """One offline channel still shares online, but must not refresh properties."""
    ch0 = _channel_device("0")
    ch1 = _channel_device("1")

    delegate = MagicMock()
    delegate.api_client = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={
            PARAM_ONLINE: "1",
            PARAM_CHANNELS: [
                {PARAM_CHANNEL_ID: 0, PARAM_ONLINE: "1"},
                {PARAM_CHANNEL_ID: 1, PARAM_ONLINE: "0"},
            ],
        }
    )

    manager = ImouHaDeviceManager(delegate)
    with patch(
        "pyimouapi.ha_device.async_property_get",
        AsyncMock(return_value={"control.outlet.enabled": 1}),
    ) as prop_get:
        await manager.async_update_devices_status([ch0, ch1])

    assert delegate.async_get_device_online_status.await_count == 1
    assert prop_get.await_count == 1
    assert ch0.switches["relay"][PARAM_STATE] is True
    assert ch1.switches["relay"][PARAM_STATE] is False
    assert ch1.sensors[PARAM_STATUS][PARAM_STATE] == DeviceStatus.OFFLINE.value


@pytest.mark.asyncio
async def test_apply_online_status_marks_missing_channel_offline() -> None:
    """A channel absent from deviceOnline must not stay sticky-online."""
    ch = _channel_device("9")
    manager = ImouHaDeviceManager(MagicMock())
    manager._apply_online_status(
        ch,
        {
            PARAM_ONLINE: "1",
            PARAM_CHANNELS: [{PARAM_CHANNEL_ID: 0, PARAM_ONLINE: "1"}],
        },
    )
    assert ch.sensors[PARAM_STATUS][PARAM_STATE] == DeviceStatus.OFFLINE.value


@pytest.mark.asyncio
async def test_one_channel_apply_error_does_not_block_siblings() -> None:
    """A malformed channel write must not leave later channels unupdated."""
    channel = _channel_device("0")
    accessory = ImouHaDevice("nvr1", "Door", "Imou", "Lock", "1.0")
    accessory.set_product_id("lock1")
    accessory.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value

    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        return_value={PARAM_ONLINE: "1"}
    )
    manager = ImouHaDeviceManager(delegate)

    await manager._async_update_status_shared([channel, accessory])

    assert accessory.sensors[PARAM_STATUS][PARAM_STATE] == DeviceStatus.ONLINE.value


@pytest.mark.asyncio
async def test_update_devices_status_raises_when_every_group_fails() -> None:
    """A total outage must reach the caller so Home Assistant can fail the poll."""
    cam = ImouHaDevice("cam_a", "Cam A", "Imou", "IPC", "1.0")
    cam.set_channel_id("0")
    cam.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.ONLINE.value

    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        side_effect=RequestFailedException("cloud down")
    )
    manager = ImouHaDeviceManager(delegate)

    with pytest.raises(RequestFailedException, match="cloud down"):
        await manager.async_update_devices_status([cam])


@pytest.mark.asyncio
async def test_update_devices_status_keeps_going_when_one_group_fails() -> None:
    """One physical device failing online must not skip the rest of the account."""
    a = ImouHaDevice("cam_a", "Cam A", "Imou", "IPC", "1.0")
    a.set_channel_id("0")
    a.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value

    b = ImouHaDevice("cam_b", "Cam B", "Imou", "IPC", "1.0")
    b.set_channel_id("0")
    b.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value

    delegate = MagicMock()
    delegate.async_get_device_online_status = AsyncMock(
        side_effect=[
            RequestFailedException("cam_a busy"),
            {
                PARAM_ONLINE: "1",
                PARAM_CHANNELS: [{PARAM_CHANNEL_ID: 0, PARAM_ONLINE: "1"}],
            },
        ]
    )
    delegate.async_get_iot_device_detail_info = AsyncMock(
        return_value={PARAM_PROPERTIES: {}, PARAM_CHANNELS: []}
    )
    manager = ImouHaDeviceManager(delegate)

    fetched = await manager.async_update_devices_status([a, b])

    assert fetched == set()
    assert a.sensors[PARAM_STATUS][PARAM_STATE] == DeviceStatus.OFFLINE.value
    assert b.sensors[PARAM_STATUS][PARAM_STATE] == DeviceStatus.ONLINE.value

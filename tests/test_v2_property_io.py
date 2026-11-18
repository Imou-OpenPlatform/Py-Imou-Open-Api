"""V2 property.get / property.set switch and select paths."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyimouapi.capability.catalog import CapabilitySet, PropertyCapability
from pyimouapi.const import (
    PARAM_CURRENT_OPTION,
    PARAM_STATE,
    PARAM_STATE_VARIANT,
    PARAM_V2_OUTPUT_FIELD,
    PARAM_V2_RAW_BY_OPTION,
    PARAM_V2_STRUCT_FIELD,
    PARAM_V2_TARGET_ID,
    STATE_VARIANT_ENUM,
    STATE_VARIANT_NUMERIC,
)
from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient


@pytest.fixture
def ha_manager() -> ImouHaDeviceManager:
    client = ImouOpenApiClient("app", "secret", "api.example.com")
    return ImouHaDeviceManager(ImouDeviceManager(client))


def _switch_device() -> ImouHaDevice:
    device = ImouHaDevice("IPC1", "Cam", "Imou", "IPC", "1.0")
    device.set_product_id("pid")
    device.set_channel_id("0")
    device.switches["motion_detect"] = {
        PARAM_V2_TARGET_ID: "detection.motion.enabled",
        PARAM_STATE: False,
    }
    return device


def _property_capability_set(*target_ids: str) -> CapabilitySet:
    return CapabilitySet(
        properties={
            target_id: PropertyCapability(target_id, "rw", "struct")
            for target_id in target_ids
        },
        services=frozenset(),
        events=frozenset(),
    )


def test_storage_capacity_list_becomes_a_used_percentage() -> None:
    """storage.local.capacity is a list of byte counts, not a percentage."""
    device = _switch_device()
    device.sensors["storage_used"] = {
        PARAM_V2_TARGET_ID: "storage.local.capacity",
        PARAM_STATE: "0",
    }
    device.set_capability_set(_property_capability_set("storage.local.capacity"))
    manager = ImouHaDeviceManager(MagicMock())

    changed = manager.apply_property_values(
        device,
        {
            "storage.local.capacity": [
                {
                    "totalBytes": 31256674304,
                    "usedBytes": 14181138432,
                    "storageState": "1",
                    "index": 0,
                }
            ]
        },
    )

    assert changed is True
    assert device.sensors["storage_used"][PARAM_STATE] == 45
    assert device.sensors["storage_used"][PARAM_STATE_VARIANT] == STATE_VARIANT_NUMERIC


def test_storage_fault_becomes_a_status_instead_of_a_percentage() -> None:
    """A card with no size keeps its fault instead of an unknown percentage."""
    device = _switch_device()
    device.sensors["storage_used"] = {
        PARAM_V2_TARGET_ID: "storage.local.capacity",
        PARAM_STATE: None,
    }
    device.set_capability_set(_property_capability_set("storage.local.capacity"))
    manager = ImouHaDeviceManager(MagicMock())

    manager.apply_property_values(
        device,
        {
            "storage.local.capacity": [
                {
                    "totalBytes": 0,
                    "usedBytes": 0,
                    "storageState": "2",
                    "storageAbnormal": "7",
                    "index": 0,
                }
            ]
        },
    )

    assert device.sensors["storage_used"][PARAM_STATE] == "mount_failed"
    assert device.sensors["storage_used"][PARAM_STATE_VARIANT] == STATE_VARIANT_ENUM


def test_missing_storage_card_is_no_card() -> None:
    device = _switch_device()
    device.sensors["storage_used"] = {
        PARAM_V2_TARGET_ID: "storage.local.capacity",
        PARAM_STATE: None,
    }
    device.set_capability_set(_property_capability_set("storage.local.capacity"))
    manager = ImouHaDeviceManager(MagicMock())

    manager.apply_property_values(
        device,
        {
            "storage.local.capacity": [
                {
                    "totalBytes": 0,
                    "usedBytes": 0,
                    "storageState": "0",
                    "storageAbnormal": "1",
                    "index": 0,
                }
            ]
        },
    )

    assert device.sensors["storage_used"][PARAM_STATE] == "no_card"


def test_apply_property_values_updates_supported_entity_types() -> None:
    device = _switch_device()
    device.switches["motion_detect"][PARAM_V2_TARGET_ID] = "motion.enabled"
    device.sensors["temperature"] = {
        PARAM_V2_TARGET_ID: "environment.temperature",
        PARAM_STATE: None,
    }
    device.selects["mode"] = {
        PARAM_V2_TARGET_ID: "working.mode",
        PARAM_CURRENT_OPTION: "off",
        PARAM_V2_RAW_BY_OPTION: {"off": 0, "automatic": 2},
    }
    device.set_capability_set(
        _property_capability_set(
            "motion.enabled", "environment.temperature", "working.mode"
        )
    )
    manager = ImouHaDeviceManager(MagicMock())

    changed = manager.apply_property_values(
        device,
        {
            "motion.enabled": {"enabled": 1},
            "environment.temperature": 23.5,
            "working.mode": 2,
        },
    )

    assert changed is True
    assert device.switches["motion_detect"][PARAM_STATE] is True
    assert device.sensors["temperature"][PARAM_STATE] == 23.5
    assert device.selects["mode"][PARAM_CURRENT_OPTION] == "automatic"


def test_apply_property_values_ignores_normalized_equivalent_entity_values() -> None:
    """Equivalent scalar, bool, enum, struct, and text values are unchanged."""
    device = _switch_device()
    device.switches["motion_detect"] = {
        PARAM_V2_TARGET_ID: "motion.enabled",
        PARAM_STATE: True,
    }
    device.binary_sensors["door"] = {
        PARAM_V2_TARGET_ID: "door.state",
        PARAM_V2_STRUCT_FIELD: "active",
        PARAM_STATE: False,
    }
    device.sensors["temperature_current"] = {
        PARAM_V2_TARGET_ID: "environment.temperature",
        PARAM_STATE: 23.5,
        PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC,
    }
    device.selects["mode"] = {
        PARAM_V2_TARGET_ID: "working.mode",
        PARAM_CURRENT_OPTION: "automatic",
        PARAM_V2_RAW_BY_OPTION: {"off": 0, "automatic": 2},
    }
    device.texts["count"] = {
        PARAM_V2_TARGET_ID: "counter.value",
        PARAM_STATE: "7",
    }
    device.set_capability_set(
        _property_capability_set(
            "motion.enabled",
            "door.state",
            "environment.temperature",
            "working.mode",
            "counter.value",
        )
    )
    manager = ImouHaDeviceManager(MagicMock())

    changed = manager.apply_property_values(
        device,
        {
            "motion.enabled": {"enabled": 1},
            "door.state": {"active": "0"},
            "environment.temperature": "23.5",
            "working.mode": "2",
            "counter.value": 7,
        },
    )

    assert changed is False


def test_apply_property_values_reports_none_to_value_as_changed() -> None:
    device = _switch_device()
    device.sensors["temperature_current"] = {
        PARAM_V2_TARGET_ID: "environment.temperature",
        PARAM_STATE: None,
    }
    device.set_capability_set(_property_capability_set("environment.temperature"))
    manager = ImouHaDeviceManager(MagicMock())

    assert (
        manager.apply_property_values(device, {"environment.temperature": "23.5"})
        is True
    )
    assert device.sensors["temperature_current"][PARAM_STATE] == 23.5


def test_apply_property_values_does_not_confuse_bool_with_numeric_enum() -> None:
    device = _switch_device()
    device.selects["mode"] = {
        PARAM_V2_TARGET_ID: "working.mode",
        PARAM_CURRENT_OPTION: "off",
        PARAM_V2_RAW_BY_OPTION: {"off": 0, "automatic": 1},
    }
    device.set_capability_set(_property_capability_set("working.mode"))
    manager = ImouHaDeviceManager(MagicMock())

    assert manager.apply_property_values(device, {"working.mode": True}) is False
    assert device.selects["mode"][PARAM_CURRENT_OPTION] == "off"


@pytest.mark.parametrize(
    ("values", "entity"),
    [
        ({"motion.enabled": {"unexpected": 1}}, "switch"),
        ({"working.mode": 99}, "select"),
    ],
)
def test_apply_property_values_rejects_invalid_values(
    values: dict[str, object], entity: str
) -> None:
    device = _switch_device()
    device.switches["motion_detect"][PARAM_V2_TARGET_ID] = "motion.enabled"
    device.selects["mode"] = {
        PARAM_V2_TARGET_ID: "working.mode",
        PARAM_CURRENT_OPTION: "off",
        PARAM_V2_RAW_BY_OPTION: {"off": 0, "automatic": 2},
    }
    device.set_capability_set(
        _property_capability_set("motion.enabled", "working.mode")
    )
    manager = ImouHaDeviceManager(MagicMock())

    assert manager.apply_property_values(device, values) is False
    if entity == "switch":
        assert device.switches["motion_detect"][PARAM_STATE] is False
    else:
        assert device.selects["mode"][PARAM_CURRENT_OPTION] == "off"


def test_apply_property_values_ignores_property_missing_from_capability() -> None:
    device = _switch_device()
    device.set_capability_set(_property_capability_set("another.property"))
    manager = ImouHaDeviceManager(MagicMock())

    assert (
        manager.apply_property_values(device, {"detection.motion.enabled": 1}) is False
    )
    assert device.switches["motion_detect"][PARAM_STATE] is False


@pytest.mark.asyncio
async def test_switch_operation_uses_property_set(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = _switch_device()
    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager.async_switch_operation(device, "motion_detect", True)
    mock_set.assert_awaited_once()
    kwargs = mock_set.await_args.kwargs
    assert kwargs["properties"] == {"detection.motion.enabled": 1}
    assert device.switches["motion_detect"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_update_v2_property_entities_reads_batch(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = _switch_device()
    with patch(
        "pyimouapi.ha_device.async_property_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {"detection.motion.enabled": 1}
        await ha_manager._async_update_v2_property_entities(device)
    mock_get.assert_awaited_once_with(
        ha_manager.delegate.api_client,
        device_id="IPC1",
        channel_id="0",
        product_id="pid",
        properties=["detection.motion.enabled"],
    )
    assert device.switches["motion_detect"][PARAM_STATE] is True


@pytest.mark.asyncio
async def test_property_get_skips_service_commands(
    ha_manager: ImouHaDeviceManager,
) -> None:
    """A select that invokes a service is not sent to property.get."""
    device = _switch_device()
    device.selects["collection_point"] = {
        PARAM_V2_TARGET_ID: "ptz.preset.goto",
        PARAM_CURRENT_OPTION: "select_collection_point",
    }
    device.set_capability_set(
        CapabilitySet(
            properties={
                "detection.motion.enabled": PropertyCapability(
                    "detection.motion.enabled", "rw", "int"
                )
            },
            services=frozenset({"ptz.preset.goto", "ptz.preset.list"}),
            events=frozenset(),
        )
    )
    with patch(
        "pyimouapi.ha_device.async_property_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {"detection.motion.enabled": 1}
        await ha_manager._async_update_v2_property_entities(device)
    assert mock_get.await_args.kwargs["properties"] == ["detection.motion.enabled"]


@pytest.mark.asyncio
async def test_property_get_splits_device_and_channel_scope(
    ha_manager: ImouHaDeviceManager,
) -> None:
    """Device-level and channel-level properties are read in separate calls."""
    device = _switch_device()
    device.switches["prompt"] = {
        PARAM_V2_TARGET_ID: "audio.prompt.enabled",
        PARAM_STATE: False,
    }
    device.set_capability_set(
        CapabilitySet(
            properties={
                "detection.motion.enabled": PropertyCapability(
                    "detection.motion.enabled", "rw", "int", scope="channel"
                ),
                "audio.prompt.enabled": PropertyCapability(
                    "audio.prompt.enabled", "rw", "int", scope="device"
                ),
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    with patch(
        "pyimouapi.ha_device.async_property_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {}
        await ha_manager._async_update_v2_property_entities(device)
    calls = [
        (call.kwargs["channel_id"], call.kwargs["properties"])
        for call in mock_get.await_args_list
    ]
    assert calls == [
        ("0", ["detection.motion.enabled"]),
        (None, ["audio.prompt.enabled"]),
    ]


@pytest.mark.asyncio
async def test_switch_set_omits_channel_for_device_scope(
    ha_manager: ImouHaDeviceManager,
) -> None:
    """A device-scope switch is written without a channel id."""
    device = _switch_device()
    device.switches["prompt"] = {
        PARAM_V2_TARGET_ID: "audio.prompt.enabled",
        PARAM_STATE: False,
    }
    device.set_capability_set(
        CapabilitySet(
            properties={
                "audio.prompt.enabled": PropertyCapability(
                    "audio.prompt.enabled", "rw", "int", scope="device"
                )
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager.async_switch_operation(device, "prompt", True)
    assert mock_set.await_args.kwargs["channel_id"] is None
    assert mock_set.await_args.kwargs["properties"] == {"audio.prompt.enabled": 1}


@pytest.mark.asyncio
async def test_property_get_skips_write_only(
    ha_manager: ImouHaDeviceManager,
) -> None:
    """A command that cannot be read must not go out in property.get."""
    device = _switch_device()
    device.switches["siren"] = {
        PARAM_V2_TARGET_ID: "detection.siren.start",
        PARAM_STATE: False,
    }
    device.set_capability_set(
        CapabilitySet(
            properties={
                "detection.motion.enabled": PropertyCapability(
                    "detection.motion.enabled", "rw", "int"
                ),
                "detection.siren.start": PropertyCapability(
                    "detection.siren.start", "w", "int"
                ),
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    with patch(
        "pyimouapi.ha_device.async_property_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {"detection.motion.enabled": 1}
        await ha_manager._async_update_v2_property_entities(device)
    assert mock_get.await_args.kwargs["properties"] == ["detection.motion.enabled"]


@pytest.mark.asyncio
async def test_property_set_splits_device_and_channel_scope(
    ha_manager: ImouHaDeviceManager,
) -> None:
    """One write must not send a device property and a channel property together."""
    device = _switch_device()
    device.set_capability_set(
        CapabilitySet(
            properties={
                "detection.motion.enabled": PropertyCapability(
                    "detection.motion.enabled", "rw", "int", scope="channel"
                ),
                "audio.prompt.enabled": PropertyCapability(
                    "audio.prompt.enabled", "rw", "int", scope="device"
                ),
            },
            services=frozenset(),
            events=frozenset(),
        )
    )
    with patch(
        "pyimouapi.ha_device.async_property_set", new_callable=AsyncMock
    ) as mock_set:
        await ha_manager._async_set_scoped_properties(
            device,
            {"detection.motion.enabled": 1, "audio.prompt.enabled": 0},
        )
    calls = {
        (
            call.kwargs["channel_id"],
            tuple(call.kwargs["properties"].items()),
        )
        for call in mock_set.await_args_list
    }
    assert calls == {
        ("0", (("detection.motion.enabled", 1),)),
        (None, (("audio.prompt.enabled", 0),)),
    }


@pytest.mark.asyncio
async def test_service_read_omits_channel_for_device_scope(
    ha_manager: ImouHaDeviceManager,
) -> None:
    """A device-scope service is invoked without a channel id."""
    device = _switch_device()
    device.sensors["power"] = {
        PARAM_V2_TARGET_ID: "power.outlet.read",
        PARAM_V2_OUTPUT_FIELD: "power",
        PARAM_STATE: "unknown",
    }
    device.set_capability_set(
        CapabilitySet(
            properties={},
            services=frozenset({"power.outlet.read"}),
            events=frozenset(),
            service_scopes={"power.outlet.read": "device"},
        )
    )
    with patch(
        "pyimouapi.ha_device.async_service_invoke", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = {"outputData": {"power": 12}}
        await ha_manager._async_update_v2_service_entities(device)
    assert mock_invoke.await_args.kwargs["channel_id"] is None
    assert mock_invoke.await_args.kwargs["service_id"] == "power.outlet.read"


def test_apply_identity_copies_play_token() -> None:
    current = ImouHaDevice("IPC1", "Old", "Imou", "IPC", "1.0")
    fresh = ImouHaDevice("IPC1", "New", "Imou", "IPC", "2.0")
    fresh.set_play_token_v2("token-v2")
    current.apply_identity(fresh)
    assert current.play_token_v2 == "token-v2"
    assert current.device_name == "New"


@pytest.mark.asyncio
async def test_update_paas_v2_property_entities_omits_product_id(
    ha_manager: ImouHaDeviceManager,
) -> None:
    device = _switch_device()
    device.set_product_id(None)
    with patch(
        "pyimouapi.ha_device.async_property_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {"detection.motion.enabled": 1}
        await ha_manager._async_update_v2_property_entities(device)
    mock_get.assert_awaited_once_with(
        ha_manager.delegate.api_client,
        device_id="IPC1",
        channel_id="0",
        product_id=None,
        properties=["detection.motion.enabled"],
    )

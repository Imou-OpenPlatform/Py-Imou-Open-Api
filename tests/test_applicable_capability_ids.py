from pyimouapi.capability.binding import applicable_capability_ids
from pyimouapi.ha_device import ImouHaDevice


def test_no_channel_uses_only_device_ids() -> None:
    assert applicable_capability_ids(
        {"device.reboot.execute"},
        {"detection.motion.enabled"},
        is_ipc=False,
        channel_id=None,
    ) == frozenset({"device.reboot.execute"})


def test_nvr_channel_zero_does_not_inherit_device_ids() -> None:
    assert applicable_capability_ids(
        {"device.reboot.execute"},
        {"detection.motion.enabled"},
        is_ipc=False,
        channel_id="0",
    ) == frozenset({"detection.motion.enabled"})


def test_ipc_channel_zero_inherits_device_ids() -> None:
    assert applicable_capability_ids(
        {"device.reboot.execute"},
        {"detection.motion.enabled"},
        is_ipc=True,
        channel_id="0",
    ) == frozenset({"device.reboot.execute", "detection.motion.enabled"})


def test_ipc_channel_one_does_not_inherit_device_ids() -> None:
    assert applicable_capability_ids(
        {"device.reboot.execute"},
        {"detection.motion.enabled"},
        is_ipc=True,
        channel_id="1",
    ) == frozenset({"detection.motion.enabled"})


def test_replace_capabilities_copies_capability_ids() -> None:
    current = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1")
    fresh = ImouHaDevice("SN", "Cam", "Imou", "IPC", "1")
    fresh.set_capability_ids({"detection.motion.enabled"})
    current.replace_capabilities(fresh)
    assert current.capability_ids == frozenset({"detection.motion.enabled"})

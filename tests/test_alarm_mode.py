"""Friendly-key mapping for IoT alarm mode (ref 15200)."""

import pytest
from pyimouapi.alarm_mode import ALARM_MODES, to_friendly, to_raw


@pytest.mark.parametrize(
    ("raw", "friendly"),
    [("0", "home"), (0, "home"), ("1", "away"), ("2", "disarm")],
)
def test_to_friendly(raw: str | int, friendly: str) -> None:
    assert to_friendly(raw) == friendly


@pytest.mark.parametrize(
    ("friendly", "raw"),
    [("home", "0"), ("away", "1"), ("disarm", "2")],
)
def test_to_raw(friendly: str, raw: str) -> None:
    assert to_raw(friendly) == raw


def test_to_friendly_unknown_passthrough() -> None:
    assert to_friendly("9") == "9"


def test_to_raw_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown"):
        to_raw("vacation")


def test_alarm_modes() -> None:
    assert ALARM_MODES == ("home", "away", "disarm")

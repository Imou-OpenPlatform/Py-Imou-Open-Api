"""Tests for siren local time helper."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pyimouapi.siren import client_local_time_iso


def test_client_local_time_iso() -> None:
    with patch("pyimouapi.siren.datetime") as mock_dt:
        aware = datetime(2026, 7, 31, 15, 8, tzinfo=UTC)
        now_mock = MagicMock()
        now_mock.astimezone.return_value = aware
        mock_dt.now.return_value = now_mock
        assert client_local_time_iso() == "20260731T150800"

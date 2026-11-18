"""Siren helpers for V2 service invoke."""

from __future__ import annotations

from datetime import datetime


def client_local_time_iso() -> str:
    """Return client local time for detection.siren.start (yyyyMMdd'T'HHmmss)."""
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")

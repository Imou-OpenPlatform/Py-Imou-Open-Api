"""Siren button helpers."""

from __future__ import annotations

from datetime import datetime


def client_local_time_iso() -> str:
    """Return client local time for IoT SirenStart (ISO 8601 with timezone)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def build_siren_start_iot_content(input_ref: str) -> dict[str, str]:
    """Build iotDeviceControl content for SirenStart."""
    return {input_ref: client_local_time_iso()}

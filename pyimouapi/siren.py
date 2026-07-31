"""Siren button helpers."""

from __future__ import annotations

from datetime import datetime


def client_local_time_iso() -> str:
    """Return client local time for IoT SirenStart (yyyyMMdd'T'HHmmss)."""
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")


def build_siren_start_iot_content(input_ref: str) -> dict[str, str]:
    """Build iotDeviceControl content for SirenStart."""
    return {input_ref: client_local_time_iso()}

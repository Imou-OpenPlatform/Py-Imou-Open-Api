"""Official LCOpenSDK picture decrypt (ctypes)."""

from __future__ import annotations


def is_tcm_ability(device_ability: str) -> bool:
    """Return True when deviceAbility lists the TCM token."""
    return any(part.strip() == "TCM" for part in device_ability.split(","))


def resolve_encrypt_key(
    *,
    is_tcm: bool,
    device_id: str,
    device_password: str | None,
) -> str | None:
    """Return the LCOpenSDK encrypt key, or None when TCM has no password."""
    if device_password:
        return device_password
    if is_tcm:
        return None
    return device_id

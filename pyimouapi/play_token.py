"""Decrypt a device-list play token into the picture login password.

The wire format is Base64(12-byte nonce || AES-256-GCM ciphertext and tag).
The 32-byte key is the hex string returned by getPlayTokenKey. Callers that
cannot decrypt fall back to the serial.
"""

from __future__ import annotations

import base64
import json
from typing import Any

_PASSWORD_KEYS = frozenset({"devloginpassword", "dev_login_password"})


def aes_key_from_play_token_key(play_token_key: str) -> bytes | None:
    """Decode a 64-character hex play-token key into 32 bytes."""
    text = "".join(play_token_key.split())
    try:
        key = bytes.fromhex(text)
    except ValueError:
        return None
    if len(key) != 32:
        return None
    return key


def decrypt_play_token(play_token: str, key: bytes) -> str | None:
    """Return the UTF-8 credential text, or None when the token will not open."""
    if not play_token or len(key) != 32:
        return None
    try:
        wire = base64.b64decode(play_token, validate=False)
    except Exception:
        return None
    if len(wire) <= 12:
        return None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        plain = AESGCM(key).decrypt(wire[:12], wire[12:], None)
    except Exception:
        return None
    try:
        return plain.decode("utf-8")
    except UnicodeDecodeError:
        return None


def dev_login_password(plaintext: str) -> str | None:
    """Read the device login password out of a decrypted play token."""
    text = plaintext.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        found = _password_in(parsed)
        if found:
            return found
    return None


def login_password_from_play_token(
    *,
    play_token: str,
    play_token_key: str,
) -> str | None:
    """Decrypt ``play_token`` with a getPlayTokenKey value and return the password."""
    if not play_token or not play_token_key:
        return None
    key = aes_key_from_play_token_key(play_token_key)
    if key is None:
        return None
    plain = decrypt_play_token(play_token, key)
    if plain is None:
        return None
    return dev_login_password(plain)


def _password_in(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                str(key).lower() in _PASSWORD_KEYS
                and isinstance(item, str)
                and item.strip()
            ):
                return item.strip()
            found = _password_in(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _password_in(item)
            if found:
                return found
    return None

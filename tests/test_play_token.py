"""Play token decryption and credential parsing."""

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pyimouapi.play_token import (
    aes_key_from_play_token_key,
    decrypt_play_token,
    login_password_from_play_token,
)


def _seal(key: bytes, plaintext: str) -> str:
    nonce = b"0123456789ab"
    body = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + body).decode("ascii")


def test_login_password_round_trip() -> None:
    raw = os.urandom(32)
    key_hex = raw.hex()
    assert aes_key_from_play_token_key(key_hex) == raw
    token = _seal(raw, json.dumps({"devLoginPassword": "door-42"}))
    assert (
        login_password_from_play_token(play_token=token, play_token_key=key_hex)
        == "door-42"
    )


def test_wrong_key_does_not_open_the_token() -> None:
    token = _seal(os.urandom(32), json.dumps({"devLoginPassword": "door-42"}))
    assert (
        login_password_from_play_token(
            play_token=token, play_token_key=os.urandom(32).hex()
        )
        is None
    )


def test_short_key_is_rejected() -> None:
    assert aes_key_from_play_token_key("abcd") is None


def test_sixteen_byte_key_does_not_open_play_token_v2() -> None:
    """The shorter key from the same response is not the key for playTokenV2."""
    real = os.urandom(32)
    token = _seal(real, json.dumps({"devLoginPassword": "door-42"}))
    short = os.urandom(16).hex()
    assert aes_key_from_play_token_key(short) is None
    assert (
        login_password_from_play_token(play_token=token, play_token_key=short) is None
    )


def test_short_wire_is_rejected() -> None:
    key = os.urandom(32)
    assert decrypt_play_token(base64.b64encode(b"short").decode(), key) is None

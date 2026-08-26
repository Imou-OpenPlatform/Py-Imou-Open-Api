"""TCM detection and encrypt-key resolution for LCOpenSDK picture decrypt."""

import ctypes
import hashlib
from pathlib import Path
from unittest.mock import MagicMock

from pyimouapi.ha_device import ImouHaDeviceManager
from pyimouapi.pic_decode import (
    LCOpenPicDecoder,
    PicDecodeError,
    is_tcm_ability,
    resolve_encrypt_key,
    serial_aes_key,
)


def test_build_device_copies_device_ability() -> None:
    src = MagicMock()
    src.device_id = "SN1"
    src.device_name = "Cam"
    src.brand = "Imou"
    src.device_model = "IPC"
    src.device_version = "1"
    src.product_id = None
    src.parent_product_id = None
    src.parent_device_id = None
    src.is_ipc = True
    src.device_ability = "WLAN,TCM"
    ha = ImouHaDeviceManager.build_device(src)
    assert ha.device_ability == "WLAN,TCM"


def test_is_tcm_ability_token() -> None:
    assert is_tcm_ability("TCM") is True
    assert is_tcm_ability("Foo, TCM, Bar") is True
    assert is_tcm_ability("tcm") is False
    assert is_tcm_ability("TCMX") is False
    assert is_tcm_ability("") is False
    assert is_tcm_ability("  TCM  ") is True


def test_resolve_encrypt_key() -> None:
    assert (
        resolve_encrypt_key(is_tcm=True, device_id="SN1", device_password="pw") == "pw"
    )
    assert (
        resolve_encrypt_key(is_tcm=True, device_id="SN1", device_password=None) is None
    )
    assert resolve_encrypt_key(is_tcm=True, device_id="SN1", device_password="") is None
    assert (
        resolve_encrypt_key(is_tcm=False, device_id="SN1", device_password="pw") == "pw"
    )
    assert (
        resolve_encrypt_key(is_tcm=False, device_id="SN1", device_password=None)
        == "SN1"
    )


def test_load_missing_libs_raises(tmp_path: Path) -> None:
    decoder = LCOpenPicDecoder(tmp_path)
    try:
        decoder.load()
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_serial_aes_key_is_md5_hex() -> None:
    assert serial_aes_key("SN1") == hashlib.md5(b"SN1").hexdigest()


def _decoder_with_stub_decrypt(
    jpeg: bytes, code: int = 0, codes: list[int] | None = None
) -> tuple[LCOpenPicDecoder, list]:
    """Return a decoder whose CDecrypter symbols are recorded, not called."""
    calls: list = []
    decoder = LCOpenPicDecoder(Path("/nonexistent"))
    decoder._loaded = True
    sdk = MagicMock()

    def _decrypt(obj, data, length, aes_key, device_id, password, dest, dest_len):
        calls.append((data, length, aes_key, device_id, password))
        this_code = codes[len(calls) - 1] if codes else code
        if this_code == 0:
            ctypes.memmove(dest, jpeg, len(jpeg))
            dest_len._obj.value = len(jpeg)
        return this_code

    sdk.__getitem__ = None
    attrs = {
        "_ZN5Dahua8LCCommon10CDecrypterC1ENS0_11RuleVersionE": MagicMock(),
        "_ZN5Dahua8LCCommon10CDecrypterD1Ev": MagicMock(),
        "_ZN5Dahua8LCCommon10CDecrypter22decryptDataWithoutHeadEPKciS3_S3_S3_PcRi": (
            MagicMock(side_effect=_decrypt)
        ),
    }
    sdk.configure_mock(**attrs)
    decoder._sdk = sdk
    return decoder, calls


def test_decrypt_bytes_tcm_passes_serial_and_password() -> None:
    jpeg = b"\xff\xd8tcm"
    decoder, calls = _decoder_with_stub_decrypt(jpeg)

    result = decoder.decrypt_bytes(
        b"DHAVciphertext", device_id="SN1", encrypt_key="pw", use_tcm=True
    )

    assert result == jpeg
    data, length, aes_key, device_id, password = calls[0]
    assert (data, length) == (b"DHAVciphertext", len(b"DHAVciphertext"))
    assert (aes_key, device_id, password) == (b"", b"SN1", b"pw")


def test_decrypt_bytes_non_tcm_uses_serial_aes_key() -> None:
    jpeg = b"\xff\xd8plain"
    decoder, calls = _decoder_with_stub_decrypt(jpeg)

    result = decoder.decrypt_bytes(
        b"DHAVciphertext", device_id="SN1", encrypt_key="SN1", use_tcm=False
    )

    assert result == jpeg
    _data, _length, aes_key, device_id, password = calls[0]
    assert aes_key == serial_aes_key("SN1").encode()
    assert (device_id, password) == (b"", b"")


def test_decrypt_bytes_error_code_raises() -> None:
    decoder, _calls = _decoder_with_stub_decrypt(b"", code=2)
    try:
        decoder.decrypt_bytes(b"DHAV", device_id="SN1", encrypt_key="bad", use_tcm=True)
    except PicDecodeError as err:
        assert err.code == 2
    else:
        raise AssertionError("expected PicDecodeError")


def test_decrypt_bytes_empty_data_raises() -> None:
    decoder, _calls = _decoder_with_stub_decrypt(b"")
    try:
        decoder.decrypt_bytes(b"", device_id="SN1", encrypt_key="pw", use_tcm=True)
    except PicDecodeError as err:
        assert err.code == 1
    else:
        raise AssertionError("expected PicDecodeError")


def test_decrypt_bytes_non_tcm_retries_with_password_key() -> None:
    """A serial-keyed picture that rejects the AES key is retried as a password."""
    jpeg = b"\xff\xd8retry"
    decoder, calls = _decoder_with_stub_decrypt(jpeg, codes=[2, 0])

    result = decoder.decrypt_bytes(
        b"DHAV", device_id="SN1", encrypt_key="pw", use_tcm=False
    )

    assert result == jpeg
    assert [c[2:] for c in calls] == [
        (serial_aes_key("SN1").encode(), b"", b""),
        (b"", b"SN1", b"pw"),
    ]


def test_decrypt_bytes_not_loaded_raises() -> None:
    decoder = LCOpenPicDecoder(Path("/nonexistent"))
    try:
        decoder.decrypt_bytes(
            b"DHAV", device_id="SN1", encrypt_key="SN1", use_tcm=False
        )
    except PicDecodeError as err:
        assert err.code == 99
        assert err.message == "not loaded"
    else:
        raise AssertionError("expected PicDecodeError")

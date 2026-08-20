"""TCM detection and encrypt-key resolution for LCOpenSDK picture decrypt."""

import ctypes
from pathlib import Path
from unittest.mock import MagicMock

from pyimouapi.ha_device import ImouHaDeviceManager
from pyimouapi.pic_decode import (
    LCOpenPicDecoder,
    PicDecodeError,
    is_tcm_ability,
    resolve_encrypt_key,
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


def test_decrypt_picture_non_tcm_returns_jpeg() -> None:
    jpeg = b"\xff\xd8fakejpeg"
    decoder = LCOpenPicDecoder(Path("/nonexistent"))
    decoder._loaded = True
    decoder._sdk = MagicMock()

    def _decrypt(pic_url, key, sn, dest, dest_len, token):
        n = len(jpeg)
        ctypes.memmove(dest, jpeg, n)
        dest_len._obj.value = n
        return 0

    decoder._sdk.DecryptPicture.side_effect = _decrypt
    assert (
        decoder.decrypt_picture(
            pic_url="https://cdn.example/p",
            encrypt_key="SN1",
            device_id="SN1",
            token="tok",
            use_tcm=False,
        )
        == jpeg
    )
    decoder._sdk.DecryptPictureEx.assert_not_called()


def test_decrypt_picture_tcm_uses_ex() -> None:
    jpeg = b"\xff\xd8x"
    decoder = LCOpenPicDecoder(Path("/nonexistent"))
    decoder._loaded = True
    decoder._sdk = MagicMock()

    def _decrypt_ex(pic_url, key, sn, dest, dest_len, token):
        n = len(jpeg)
        ctypes.memmove(dest, jpeg, n)
        dest_len._obj.value = n
        return 0

    decoder._sdk.DecryptPictureEx.side_effect = _decrypt_ex
    assert (
        decoder.decrypt_picture(
            pic_url="https://cdn.example/p",
            encrypt_key="pw",
            device_id="SN1",
            token="",
            use_tcm=True,
        )
        == jpeg
    )
    decoder._sdk.DecryptPicture.assert_not_called()


def test_decrypt_picture_key_error_raises() -> None:
    decoder = LCOpenPicDecoder(Path("/nonexistent"))
    decoder._loaded = True
    decoder._sdk = MagicMock()
    decoder._sdk.DecryptPicture.return_value = 2
    try:
        decoder.decrypt_picture(
            pic_url="https://cdn.example/p",
            encrypt_key="bad",
            device_id="SN1",
            token="",
            use_tcm=False,
        )
    except PicDecodeError as err:
        assert err.code == 2
    else:
        raise AssertionError("expected PicDecodeError")


def test_load_missing_libs_raises(tmp_path: Path) -> None:
    decoder = LCOpenPicDecoder(tmp_path)
    try:
        decoder.load()
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_init_open_api_not_loaded_raises() -> None:
    decoder = LCOpenPicDecoder(Path("/nonexistent"))
    try:
        decoder.init_open_api("openapi.example", 443, "id", "secret")
    except PicDecodeError as err:
        assert err.code == 99
        assert err.message == "not loaded"
    else:
        raise AssertionError("expected PicDecodeError")


def test_resolve_ca_path_prefers_native_pem(tmp_path: Path) -> None:
    pem = tmp_path / "cacert.pem"
    pem.write_text("dummy-ca")
    decoder = LCOpenPicDecoder(tmp_path)
    assert decoder._resolve_ca_path(None) == str(pem).encode()
    assert decoder._resolve_ca_path("/explicit.pem") == b"/explicit.pem"


def test_decrypt_picture_not_loaded_raises() -> None:
    decoder = LCOpenPicDecoder(Path("/nonexistent"))
    try:
        decoder.decrypt_picture(
            pic_url="https://cdn.example/p",
            encrypt_key="SN1",
            device_id="SN1",
            token="",
            use_tcm=False,
        )
    except PicDecodeError as err:
        assert err.code == 99
        assert err.message == "not loaded"
    else:
        raise AssertionError("expected PicDecodeError")

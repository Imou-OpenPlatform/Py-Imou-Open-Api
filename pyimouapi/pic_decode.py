"""Official LCOpenSDK picture decrypt (ctypes)."""

from __future__ import annotations

import ctypes
from pathlib import Path


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


class PicDecodeError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class LCOpenPicDecoder:
    def __init__(self, native_dir: Path) -> None:
        self.native_dir = native_dir
        self._loaded = False
        self._sdk: ctypes.CDLL | None = None
        self._client: ctypes.CDLL | None = None

    def load(self) -> None:
        if self._loaded:
            return
        client_path = self.native_dir / "libLCOpenApiClient.so"
        sdk_path = self.native_dir / "libLCOpenSDK.so"
        if not client_path.exists() or not sdk_path.exists():
            raise FileNotFoundError(
                f"LCOpenSDK native libs not found in {self.native_dir}"
            )
        self._client = ctypes.CDLL(str(client_path), mode=ctypes.RTLD_GLOBAL)
        self._sdk = ctypes.CDLL(str(sdk_path))

        self._sdk.initOpenApi.argtypes = (
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        )
        self._sdk.initOpenApi.restype = None

        decrypt_args = (
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_char_p,
        )
        self._sdk.DecryptPicture.argtypes = decrypt_args
        self._sdk.DecryptPicture.restype = ctypes.c_int
        self._sdk.DecryptPictureEx.argtypes = decrypt_args
        self._sdk.DecryptPictureEx.restype = ctypes.c_int

        self._loaded = True

    def _require_sdk(self) -> ctypes.CDLL:
        if not self._loaded or self._sdk is None:
            raise PicDecodeError(99, "not loaded")
        return self._sdk

    def _resolve_ca_path(self, ca_path: str | None) -> bytes:
        if ca_path:
            return ca_path.encode()
        native_ca = self.native_dir / "cacert.pem"
        if native_ca.is_file():
            return str(native_ca).encode()
        try:
            import certifi

            return certifi.where().encode()
        except ImportError:
            return b""

    def init_open_api(
        self,
        host: str,
        port: int,
        app_id: str,
        app_secret: str,
        ca_path: str | None = None,
    ) -> None:
        sdk = self._require_sdk()
        sdk.initOpenApi(
            host.encode(),
            port,
            self._resolve_ca_path(ca_path),
            app_id.encode(),
            app_secret.encode(),
        )

    def decrypt_picture(
        self,
        *,
        pic_url: str,
        encrypt_key: str,
        device_id: str,
        token: str,
        use_tcm: bool,
    ) -> bytes:
        sdk = self._require_sdk()

        buf = ctypes.create_string_buffer(20 * 1024 * 1024)
        dest_len = ctypes.c_int(len(buf))
        args = (
            pic_url.encode(),
            encrypt_key.encode(),
            device_id.encode(),
            buf,
            ctypes.byref(dest_len),
            token.encode(),
        )

        decrypt = sdk.DecryptPictureEx if use_tcm else sdk.DecryptPicture
        code = decrypt(*args)

        if code == 5:
            buf = ctypes.create_string_buffer(40 * 1024 * 1024)
            dest_len = ctypes.c_int(len(buf))
            args = (
                pic_url.encode(),
                encrypt_key.encode(),
                device_id.encode(),
                buf,
                ctypes.byref(dest_len),
                token.encode(),
            )
            code = decrypt(*args)

        if code == 0:
            raw = buf.raw[: dest_len.value]
            if not raw.startswith(b"\xff\xd8"):
                raise PicDecodeError(99, "not jpeg")
            return raw

        raise PicDecodeError(code, f"sdk {code}")

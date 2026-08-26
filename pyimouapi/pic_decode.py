"""Official LCOpenSDK picture decrypt (ctypes).

The SDK also exports ``DecryptPicture`` / ``DecryptPictureEx``, which download
the picture themselves after an ``/openapi/strongDidCheck`` round trip. That
downloader truncates on some alarm CDNs, and a short body fails the decrypt with
code 1 on a picture that is perfectly decryptable. This module therefore binds
only the decrypt half, ``CDecrypter``, and leaves the download to the caller: no
access token, no ``initOpenApi``, and no CA bundle are involved.

``native_dir`` must be a directory the integration controls. Both ``.so`` files
are loaded into the current process, and the client library is opened with
``RTLD_GLOBAL`` so the SDK can resolve OpenSSL symbols from it — that injects
those symbols into the process. ``load()`` and ``decrypt_bytes()`` are blocking
and must run in an executor, not on the event loop.
"""

from __future__ import annotations

import ctypes
import hashlib
from pathlib import Path

CLIENT_LIB = "libLCOpenApiClient.so"
SDK_LIB = "libLCOpenSDK.so"

# libLCOpenSDK.so resolves its OpenSSL symbols (OCSP_response_status and
# friends) out of libLCOpenApiClient.so, so both have to be loaded, the client
# one globally, even though every symbol used here lives in the SDK.
_SYM_CTOR = "_ZN5Dahua8LCCommon10CDecrypterC1ENS0_11RuleVersionE"
_SYM_DTOR = "_ZN5Dahua8LCCommon10CDecrypterD1Ev"
_SYM_DECRYPT = (
    "_ZN5Dahua8LCCommon10CDecrypter22decryptDataWithoutHeadEPKciS3_S3_S3_PcRi"
)

# The rule version DecryptPicture and DecryptPictureEx both construct with.
_RULE_VERSION = 1

# CDecrypter is stack allocated by the SDK within 20 bytes; this is slack.
_DECRYPTER_SIZE = 256

_CODE_WRONG_KEY = 2
_CODE_BUFFER_TOO_SMALL = 5


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


def serial_aes_key(device_id: str) -> str:
    """Return the AES key a non-TCM picture is encrypted with.

    DecryptPicture derives it from the serial with the SDK-internal
    ``getAesKey``, which copies at most 127 bytes of the serial and renders
    its MD5 as hex.
    """
    return hashlib.md5(device_id.encode()[:127]).hexdigest()


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
        client_path = self.native_dir / CLIENT_LIB
        sdk_path = self.native_dir / SDK_LIB
        if not client_path.exists() or not sdk_path.exists():
            raise FileNotFoundError(
                f"LCOpenSDK native libs not found in {self.native_dir}"
            )
        self._client = ctypes.CDLL(str(client_path), mode=ctypes.RTLD_GLOBAL)
        self._sdk = ctypes.CDLL(str(sdk_path))

        ctor = getattr(self._sdk, _SYM_CTOR)
        ctor.argtypes = (ctypes.c_void_p, ctypes.c_int)
        ctor.restype = None
        dtor = getattr(self._sdk, _SYM_DTOR)
        dtor.argtypes = (ctypes.c_void_p,)
        dtor.restype = None
        decrypt_data = getattr(self._sdk, _SYM_DECRYPT)
        decrypt_data.argtypes = (
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_int),
        )
        decrypt_data.restype = ctypes.c_int

        self._loaded = True

    def _require_sdk(self) -> ctypes.CDLL:
        if not self._loaded or self._sdk is None:
            raise PicDecodeError(99, "not loaded")
        return self._sdk

    def _decrypt_data(
        self,
        data: bytes,
        *,
        aes_key: bytes,
        device_id: bytes,
        device_password: bytes,
        dest_size: int,
    ) -> tuple[int, bytes]:
        sdk = self._require_sdk()
        ctor = getattr(sdk, _SYM_CTOR)
        dtor = getattr(sdk, _SYM_DTOR)
        decrypt_data = getattr(sdk, _SYM_DECRYPT)

        decrypter = ctypes.create_string_buffer(_DECRYPTER_SIZE)
        ctor(decrypter, _RULE_VERSION)
        try:
            dest = ctypes.create_string_buffer(dest_size)
            dest_len = ctypes.c_int(dest_size)
            code = decrypt_data(
                decrypter,
                data,
                len(data),
                aes_key,
                device_id,
                device_password,
                dest,
                ctypes.byref(dest_len),
            )
            if code != 0:
                return code, b""
            return 0, dest.raw[: dest_len.value]
        finally:
            dtor(decrypter)

    def _key_candidates(
        self, *, device_id: str, encrypt_key: str, use_tcm: bool
    ) -> list[tuple[bytes, bytes, bytes]]:
        """Return (aes_key, device_id, password) triples to try, in order.

        TCM pictures are keyed by serial plus device password. Others use an
        AES key the SDK derives from the serial; the extra candidates cover a
        serial that was passed where a password belongs.
        """
        if use_tcm:
            return [(b"", device_id.encode(), encrypt_key.encode())]
        candidates = [(serial_aes_key(device_id).encode(), b"", b"")]
        if encrypt_key and encrypt_key != device_id:
            candidates.append((b"", device_id.encode(), encrypt_key.encode()))
        return candidates

    def decrypt_bytes(
        self,
        data: bytes,
        *,
        device_id: str,
        encrypt_key: str,
        use_tcm: bool,
    ) -> bytes:
        """Decrypt an alarm picture the caller already downloaded."""
        if not data:
            raise PicDecodeError(1, "empty picture data")

        dest_size = max(len(data) * 2, 1024 * 1024)
        candidates = self._key_candidates(
            device_id=device_id, encrypt_key=encrypt_key, use_tcm=use_tcm
        )
        code = 99
        raw = b""
        for aes_key, did, password in candidates:
            code, raw = self._decrypt_data(
                data,
                aes_key=aes_key,
                device_id=did,
                device_password=password,
                dest_size=dest_size,
            )
            if code == _CODE_BUFFER_TOO_SMALL:
                code, raw = self._decrypt_data(
                    data,
                    aes_key=aes_key,
                    device_id=did,
                    device_password=password,
                    dest_size=dest_size * 4,
                )
            if code == 0:
                break
            if code != _CODE_WRONG_KEY:
                break

        if code != 0:
            raise PicDecodeError(code, f"sdk {code}")
        if not raw.startswith(b"\xff\xd8"):
            raise PicDecodeError(99, "not jpeg")
        return raw

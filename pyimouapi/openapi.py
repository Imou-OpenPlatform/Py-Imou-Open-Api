from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import logging
import secrets
import time
import uuid
from collections.abc import Iterable
from typing import Any, Literal
from urllib.parse import urlparse, urlsplit

import aiohttp

from .const import (
    API_ENDPOINT_ACCESS_TOKEN,
    API_ENDPOINT_GET_MESSAGE_CALLBACK,
    API_ENDPOINT_GET_PLAY_TOKEN_KEY,
    API_ENDPOINT_SET_MESSAGE_CALLBACK,
    ERROR_CODE_INVALID_APP,
    ERROR_CODE_INVALID_SIGN,
    ERROR_CODE_SUCCESS,
    ERROR_CODE_TOKEN_OVERDUE,
    PARAM_ACCESS_TOKEN,
    PARAM_APP_ID,
    PARAM_CODE,
    PARAM_CURRENT_DOMAIN,
    PARAM_DATA,
    PARAM_DEVICE_ID,
    PARAM_ID,
    PARAM_MSG,
    PARAM_NONCE,
    PARAM_PARAMS,
    PARAM_RESULT,
    PARAM_SIGN,
    PARAM_SYSTEM,
    PARAM_TIME,
    PARAM_TOKEN,
    PARAM_VER,
)
from .exceptions import (
    ConnectFailedException,
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

CONNECTION_LIMIT = 10
DOWNLOAD_MAX_BYTES = 8 * 1024 * 1024
REQUEST_TIMEOUT = 60
REQUEST_ATTEMPT_TIMEOUT = 30

REDACTED = "***"
_SECRET_RESPONSE_FIELDS = frozenset(
    {
        PARAM_ACCESS_TOKEN,
        "playToken",
        "playTokenV2",
        "playTokenKey",
        "playTokenKeyV2",
    }
)
_URL_FIELDS = frozenset({"url", "hls", "flv", "flvhd", "callbackurl"})


def _safe_hostname(hostname: str) -> str | None:
    """Validate a hostname before including it in a log message."""
    if not hostname or len(hostname) > 253 or "%" in hostname:
        return None
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError:
            return None
        candidate = ascii_hostname.rstrip(".")
        if not candidate or len(candidate) > 253:
            return None
        labels = candidate.split(".")
        if len(labels) > 1 and all(label.isdigit() for label in labels):
            return None
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not all(character.isalnum() or character == "-" for character in label)
            for label in labels
        ):
            return None
        return ascii_hostname
    return f"[{hostname}]" if ":" in hostname else hostname


def _redacted_url(url: str) -> str:
    """Keep only a validated scheme, hostname, and port from a logged URL.

    Paths can contain webhook identifiers or signed stream names, so none of the
    path is retained. Userinfo, query parameters, and fragments are discarded as
    well. Malformed URLs reveal nothing rather than risking a partial leak.
    """
    if any(not character.isprintable() or character.isspace() for character in url):
        return REDACTED
    try:
        parsed = urlsplit(url)
        hostname = _safe_hostname(parsed.hostname or "")
        port = parsed.port
    except ValueError:
        return REDACTED
    if parsed.scheme not in {"http", "https"} or hostname is None or port == 0:
        return REDACTED
    authority = f"{hostname}:{port}" if port is not None else hostname
    return f"{parsed.scheme}://{authority}"


def _redacted_request(body: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a request body with its credentials and URLs masked.

    ``sign`` is an MD5 over the app secret together with the ``time`` and
    ``nonce`` printed beside it, so logging it in full is enough for a reader of
    the log to attack the secret offline. The app id is left alone: it names the
    account but cannot authenticate on its own.
    """
    redacted = _redacted_value(body)
    system = redacted.get(PARAM_SYSTEM)
    if isinstance(system, dict):
        system[PARAM_SIGN] = REDACTED
    params = redacted.get(PARAM_PARAMS)
    if isinstance(params, dict):
        if PARAM_TOKEN in params:
            params[PARAM_TOKEN] = REDACTED
        # bindDevice sends the device password in params.code.
        if "code" in params:
            params["code"] = REDACTED
    return redacted


def _redacted_value(value: Any) -> Any:
    """Recursively mask credentials and reduce URL fields to safe authorities."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if key in _SECRET_RESPONSE_FIELDS and isinstance(item, str) and item:
                redacted[key] = REDACTED
                continue
            normalized_key = key.lower() if isinstance(key, str) else ""
            if isinstance(item, str) and (
                normalized_key in _URL_FIELDS or normalized_key.endswith("url")
            ):
                redacted[key] = _redacted_url(item)
            else:
                redacted[key] = _redacted_value(item)
        return redacted
    if isinstance(value, list):
        return [_redacted_value(item) for item in value]
    return value


def _redacted_response(body: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a response body with secrets masked."""
    return _redacted_value(body)


class ImouOpenApiClient:
    """Async client for Imou Open Platform HTTP API."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        api_url: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._api_url = api_url
        self._access_token: str | None = None
        self._session = session
        self._owns_session = session is None
        self._session_lock = asyncio.Lock()
        self._token_lock = asyncio.Lock()

    async def _async_get_session(self) -> aiohttp.ClientSession:
        async with self._session_lock:
            if self._session is not None and not self._session.closed:
                return self._session
            if not self._owns_session:
                raise ConnectFailedException("http session is closed")
            self._session = aiohttp.ClientSession(
                headers={"Client-Type": "HomeAssistant"},
                # Requests are issued in batches per poll; cap them so a large
                # account cannot open a connection per device at once. The cap
                # is per host, not total: snapshots come from storage rather
                # than the API host, and a handful of slow downloads holding
                # every slot in one shared pool would queue API calls until
                # they hit their own deadline and report a connection failure.
                connector=aiohttp.TCPConnector(limit_per_host=CONNECTION_LIMIT),
            )
            return self._session

    async def async_download(self, url: str, timeout: int = 120) -> bytes:  # noqa: ASYNC109
        """GET a binary payload such as a device snapshot.

        The timeout is handed to aiohttp rather than wrapped in asyncio.timeout so
        it covers connecting and reading as one budget, which is what a caller
        downloading a snapshot over a slow link actually wants to bound.
        """
        session = await self._async_get_session()
        try:
            # Released via the context manager: an error status returns early, and
            # the pool is capped, so a held connection would stall later calls.
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    raise RequestFailedException(
                        f"request failed,status code {response.status}",
                        status_code=response.status,
                    )
                reader = getattr(response, "content", None)
                if reader is not None and hasattr(reader, "readany"):
                    # StreamReader.read(n) returns only the bytes already
                    # buffered, not the rest of the body. One call leaves a
                    # snapshot JPEG cut off, and the picture shows the top only.
                    chunks: list[bytes] = []
                    total = 0
                    while True:
                        block = await reader.readany()
                        if not block:
                            break
                        total += len(block)
                        if total > DOWNLOAD_MAX_BYTES:
                            raise RequestFailedException("download exceeded size limit")
                        chunks.append(block)
                    return b"".join(chunks)
                body = await response.read()
                if len(body) > DOWNLOAD_MAX_BYTES:
                    raise RequestFailedException("download exceeded size limit")
                return body
        except ImouException:
            raise
        except Exception as exception:
            # Reaching storage is its own network hop; report it the way a failed
            # API call is reported so callers have one family to catch.
            raise ConnectFailedException(f"connect failed,{exception}") from exception

    async def async_close(self) -> None:
        """Close the HTTP session this client created.

        A session passed in by the caller, such as Home Assistant's shared
        client, is left open.
        """
        async with self._session_lock:
            if not self._owns_session:
                return
            session = self._session
            self._session = None
            if session is not None and not session.closed:
                await session.close()

    @property
    def app_id(self) -> str:
        """Open Platform application id used to sign requests."""
        return self._app_id

    async def async_get_token(self) -> None:
        """Fetch and store accessToken within one overall request deadline."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._token_lock:
                    await self._async_fetch_token()
        except TimeoutError as exception:
            raise ConnectFailedException(
                "connect failed,request deadline exceeded"
            ) from exception

    def _has_usable_token(self, stale_token: str | None) -> bool:
        """Return True when a token is held and it is not the rejected one."""
        return self._access_token is not None and self._access_token != stale_token

    async def _async_ensure_token(self, stale_token: str | None = None) -> None:
        """Fetch an accessToken unless a usable one is already held.

        Concurrent callers coalesce into a single request: every waiter re-checks
        after acquiring the lock and returns early once someone else has
        refreshed. ``stale_token`` is the token the caller saw rejected, so a
        refresh only happens while that same token is still the current one.
        """
        if self._has_usable_token(stale_token):
            return
        async with self._token_lock:
            if self._has_usable_token(stale_token):
                return
            await self._async_fetch_token()

    async def _async_fetch_token(self) -> None:
        """Request accessToken and apply any regional host redirect."""
        response = await self._async_request_api(
            API_ENDPOINT_ACCESS_TOKEN, {}, refresh_on_expiry=False
        )
        self._access_token = response[PARAM_ACCESS_TOKEN]
        if PARAM_CURRENT_DOMAIN in response:
            raw = response[PARAM_CURRENT_DOMAIN]
            if "://" not in raw:
                raw = f"https://{raw}"
            parsed = urlparse(raw)
            if parsed.netloc:
                self._api_url = parsed.netloc

    async def async_request_api(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST to an API endpoint; returns the result data object.

        Token acquisition, an expired-token refresh, and the retried request all
        share one deadline instead of each receiving a fresh timeout budget.
        """
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                return await self._async_request_api(
                    endpoint, params, refresh_on_expiry=True
                )
        except TimeoutError as exception:
            raise ConnectFailedException(
                "connect failed,request deadline exceeded"
            ) from exception

    async def _async_request_api(
        self,
        endpoint: str,
        params: dict[str, Any] | None,
        *,
        refresh_on_expiry: bool,
    ) -> dict[str, Any]:
        payload = dict(params) if params else {}
        if endpoint != API_ENDPOINT_ACCESS_TOKEN:
            await self._async_ensure_token()
            payload[PARAM_TOKEN] = self._access_token
        token_used = payload.get(PARAM_TOKEN)
        timestamp = round(time.time())
        nonce = secrets.token_urlsafe()
        sign = hashlib.md5(
            f"time:{timestamp},nonce:{nonce},appSecret:{self._app_secret}".encode()
        ).hexdigest()
        request_id = str(uuid.uuid4())
        headers = {"Content-Type": "application/json"}
        body = {
            PARAM_SYSTEM: {
                PARAM_VER: "1.0",
                PARAM_SIGN: sign,
                PARAM_APP_ID: self._app_id,
                PARAM_TIME: timestamp,
                PARAM_NONCE: nonce,
            },
            PARAM_PARAMS: payload,
            PARAM_ID: request_id,
        }
        url = f"https://{self._api_url}{endpoint}"
        session = await self._async_get_session()
        try:
            async with asyncio.timeout(REQUEST_ATTEMPT_TIMEOUT):
                # Released by the context manager: the pool is capped, so a body
                # that dies mid-read must not strand its connection and starve
                # every poll that follows. Redirects are disabled so a 307/308
                # cannot replay this credential-bearing JSON body elsewhere.
                async with session.request(
                    "POST",
                    url,
                    json=body,
                    headers=headers,
                    allow_redirects=False,
                ) as response:
                    status = response.status
                    text = await response.text()
        except Exception as exception:
            raise ConnectFailedException(f"connect failed,{exception}") from exception
        # A 5xx is the far side being unable to serve, which reads to a user as
        # not getting through; a 4xx is this request being refused. Parsing the
        # body first used to report either as a connection failure, because an
        # error page is not JSON.
        if status >= 500:
            raise ConnectFailedException(
                f"connect failed,status code {status}", status_code=status
            )
        if status != 200:
            raise RequestFailedException(
                f"request failed,status code {status}", status_code=status
            )
        try:
            response_body = json.loads(text)
        except ValueError as exception:
            raise RequestFailedException(
                f"malformed response,{exception}", status_code=status
            ) from exception
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "url: %s request body: %s response: %s",
                _redacted_url(url),
                _redacted_request(body),
                _redacted_response(response_body),
            )
        result = (
            response_body.get(PARAM_RESULT) if isinstance(response_body, dict) else None
        )
        if not isinstance(result, dict) or PARAM_CODE not in result:
            raise RequestFailedException(
                "malformed response,missing result", status_code=status
            )
        result_code = str(result[PARAM_CODE])
        result_message = result.get(PARAM_MSG) or ""
        if result_code != ERROR_CODE_SUCCESS:
            msg = result_code + ":" + result_message
            if result_code in (ERROR_CODE_INVALID_SIGN, ERROR_CODE_INVALID_APP):
                raise InvalidAppIdOrSecretException(
                    msg, status_code=status, api_code=result_code
                )
            if result_code == ERROR_CODE_TOKEN_OVERDUE and refresh_on_expiry:
                await self._async_ensure_token(stale_token=token_used)
                return await self._async_request_api(
                    endpoint, params, refresh_on_expiry=False
                )
            raise RequestFailedException(msg, status_code=status, api_code=result_code)
        response_data = result.get(PARAM_DATA, {})
        if response_data is None:
            return {}
        if not isinstance(response_data, dict):
            raise RequestFailedException(
                "malformed response,data is not an object", status_code=status
            )
        return response_data

    async def async_set_message_callback(
        self,
        *,
        status: Literal["on", "off"],
        callback_url: str | None = None,
        callback_flag: str | Iterable[str] | None = None,
        base_push: str = "2",
    ) -> dict[str, Any]:
        """Register or unregister Imou Open Platform message callback."""
        params: dict[str, Any] = {
            "status": status,
            "basePush": base_push,
        }
        if status == "on":
            if callback_url is None:
                raise ValueError("callback_url is required when status is 'on'")
            params["callbackUrl"] = callback_url
            if callback_flag is None:
                params["callbackFlag"] = "alarm,deviceStatus"
            elif isinstance(callback_flag, str):
                params["callbackFlag"] = callback_flag
            else:
                params["callbackFlag"] = ",".join(callback_flag)
        return await self.async_request_api(API_ENDPOINT_SET_MESSAGE_CALLBACK, params)

    async def async_get_message_callback(self) -> dict[str, Any]:
        """Return the developer account message callback settings."""
        data = await self.async_request_api(API_ENDPOINT_GET_MESSAGE_CALLBACK, {})
        return data if isinstance(data, dict) else {}

    async def async_get_play_token_key(self, device_id: str) -> str | None:
        """Return the play-token key for one device, or None when the cloud omits it."""
        data = await self.async_request_api(
            API_ENDPOINT_GET_PLAY_TOKEN_KEY,
            {PARAM_DEVICE_ID: device_id},
        )
        if not isinstance(data, dict):
            return None
        # playTokenV2 opens with the 32-byte playTokenKeyV2. playTokenKey is
        # a shorter key and does not decrypt that token.
        for field in ("playTokenKeyV2", "playTokenKey"):
            raw = data.get(field)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return None

    @property
    def access_token(self) -> str | None:
        return self._access_token

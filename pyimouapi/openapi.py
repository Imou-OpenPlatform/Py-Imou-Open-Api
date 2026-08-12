import asyncio
import hashlib
import json
import logging
import secrets
import time
import uuid
from collections.abc import Iterable
from typing import Any, Literal
from urllib.parse import urlparse

import aiohttp

from .const import (
    API_ENDPOINT_ACCESS_TOKEN,
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
    InvalidAppIdOrSecretException,
    RequestFailedException,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

CONNECTION_LIMIT = 10


class ImouOpenApiClient:
    """Async client for Imou Open Platform HTTP API."""

    def __init__(self, app_id: str, app_secret: str, api_url: str) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._api_url = api_url
        self._access_token: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._token_lock = asyncio.Lock()

    async def _async_get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Client-Type": "HomeAssistant"},
                # Requests are issued in batches per poll; cap them so a large
                # account cannot open a connection per device at once.
                connector=aiohttp.TCPConnector(limit=CONNECTION_LIMIT),
            )
        return self._session

    async def async_download(self, url: str, timeout: int = 120) -> bytes:
        """GET a binary payload such as a device snapshot."""
        session = await self._async_get_session()
        response = await session.get(url, timeout=aiohttp.ClientTimeout(total=timeout))
        if response.status != 200:
            raise RequestFailedException(
                f"request failed,status code {response.status}"
            )
        return await response.read()

    async def async_close(self) -> None:
        """Close the HTTP session (call when done with the client)."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def async_get_token(self) -> None:
        """Fetch and store accessToken."""
        async with self._token_lock:
            await self._async_fetch_token()

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
        """POST to an API endpoint; returns the result data object."""
        return await self._async_request_api(endpoint, params, refresh_on_expiry=True)

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
            async with asyncio.timeout(30):
                response = await session.request(
                    "POST", url, json=body, headers=headers
                )
                response_body = json.loads(await response.text())
                _LOGGER.debug(
                    "url: %s request body: %s response: %s", url, body, response_body
                )
        except Exception as exception:
            raise ConnectFailedException(f"connect failed,{exception}") from exception
        if response.status != 200:
            raise RequestFailedException(
                f"request failed,status code {response.status}"
            )
        result_code = response_body[PARAM_RESULT][PARAM_CODE]
        result_message = response_body[PARAM_RESULT][PARAM_MSG]
        if result_code != ERROR_CODE_SUCCESS:
            msg = result_code + ":" + result_message
            if result_code in (ERROR_CODE_INVALID_SIGN, ERROR_CODE_INVALID_APP):
                raise InvalidAppIdOrSecretException(msg)
            if result_code == ERROR_CODE_TOKEN_OVERDUE and refresh_on_expiry:
                await self._async_ensure_token(stale_token=token_used)
                return await self._async_request_api(
                    endpoint, params, refresh_on_expiry=False
                )
            raise RequestFailedException(msg)
        response_data = response_body[PARAM_RESULT].get(PARAM_DATA, {})
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

    @property
    def access_token(self) -> str | None:
        return self._access_token

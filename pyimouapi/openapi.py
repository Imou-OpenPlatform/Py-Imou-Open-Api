import asyncio
import hashlib
import json
import logging
import secrets
import time
import uuid
from typing import Any

import aiohttp
from urllib.parse import urlparse

from .const import (
    API_ENDPOINT_ACCESS_TOKEN,
    ERROR_CODE_INVALID_APP,
    ERROR_CODE_INVALID_SIGN,
    ERROR_CODE_SUCCESS,
    ERROR_CODE_TOKEN_OVERDUE,
    PARAM_ACCESS_TOKEN,
    PARAM_SYSTEM,
    PARAM_VER,
    PARAM_SIGN,
    PARAM_APP_ID,
    PARAM_TIME,
    PARAM_NONCE,
    PARAM_PARAMS,
    PARAM_ID,
    PARAM_RESULT,
    PARAM_DATA,
    PARAM_CODE,
    PARAM_TOKEN,
    PARAM_MSG,
    PARAM_CURRENT_DOMAIN,
)
from .exceptions import (
    ConnectFailedException,
    RequestFailedException,
    InvalidAppIdOrSecretException,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class ImouOpenApiClient:
    """Async client for Imou Open Platform HTTP API."""

    def __init__(self, app_id: str, app_secret: str, api_url: str) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._api_url = api_url
        self._access_token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _async_get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Client-Type": "HomeAssistant"},
            )
        return self._session

    async def async_close(self) -> None:
        """Close the HTTP session (call when done with the client)."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def async_get_token(self) -> None:
        """Fetch and store accessToken."""
        response = await self.async_request_api(API_ENDPOINT_ACCESS_TOKEN, {})
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
        payload = dict(params) if params else {}
        if self._access_token is None and endpoint != API_ENDPOINT_ACCESS_TOKEN:
            await self.async_get_token()
        if endpoint != API_ENDPOINT_ACCESS_TOKEN:
            payload[PARAM_TOKEN] = self._access_token
        timestamp = round(time.time())
        nonce = secrets.token_urlsafe()
        sign = hashlib.md5(
            f"time:{timestamp},nonce:{nonce},appSecret:{self._app_secret}".encode(
                "utf-8"
            )
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
                response = await session.request("POST", url, json=body, headers=headers)
                response_body = json.loads(await response.text())
                _LOGGER.debug("url: %s request body: %s response: %s", url, body, response_body)
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
            if result_code == ERROR_CODE_TOKEN_OVERDUE:
                await self.async_get_token()
                return await self.async_request_api(endpoint, params)
            raise RequestFailedException(msg)
        response_data = (
            response_body[PARAM_RESULT][PARAM_DATA]
            if PARAM_DATA in response_body[PARAM_RESULT]
            else {}
        )
        return response_data

    @property
    def access_token(self) -> str | None:
        return self._access_token

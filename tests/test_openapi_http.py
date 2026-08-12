"""Tests for the ImouOpenApiClient HTTP layer: session reuse and token handling."""

import asyncio
import json
from typing import Any

import pytest
from pyimouapi.const import (
    API_ENDPOINT_ACCESS_TOKEN,
    ERROR_CODE_INVALID_APP,
    ERROR_CODE_INVALID_SIGN,
    ERROR_CODE_SUCCESS,
    ERROR_CODE_TOKEN_OVERDUE,
)
from pyimouapi.exceptions import (
    ConnectFailedException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
from pyimouapi.openapi import CONNECTION_LIMIT, ImouOpenApiClient

ENDPOINT = "/openapi/deviceBaseList"


def api_result(
    code: str = ERROR_CODE_SUCCESS,
    msg: str = "success",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an Imou Open Platform response envelope."""
    return {"result": {"code": code, "msg": msg, "data": {} if data is None else data}}


def token_result(token: str = "tok-1") -> dict[str, Any]:
    """Build an accessToken response envelope."""
    return api_result(data={"accessToken": token, "expireTime": 3600})


class FakeResponse:
    """Minimal aiohttp response stand-in."""

    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        """Initialize the response."""
        self.status = status
        self._payload = payload

    async def text(self) -> str:
        """Return the JSON body."""
        return json.dumps(self._payload)


class FakeBinaryResponse:
    """Minimal aiohttp response stand-in for binary downloads."""

    def __init__(self, status: int, payload: bytes) -> None:
        """Initialize the response."""
        self.status = status
        self._payload = payload

    async def read(self) -> bytes:
        """Return the body."""
        return self._payload


class FakeSession:
    """Records requests and replays queued responses."""

    def __init__(
        self,
        responses: list[Any],
        *,
        delay: float = 0,
        download_status: int = 200,
        download_payload: bytes = b"jpeg-bytes",
    ) -> None:
        """Initialize with a queue of responses or exceptions to raise."""
        self._responses = list(responses)
        self._delay = delay
        self._download_status = download_status
        self._download_payload = download_payload
        self.closed = False
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.downloads: list[str] = []
        self.close_count = 0

    async def get(self, url: str, *, timeout: Any = None) -> FakeBinaryResponse:
        """Return the configured binary payload."""
        self.downloads.append(url)
        return FakeBinaryResponse(self._download_status, self._download_payload)

    async def request(
        self, method: str, url: str, *, json: dict[str, Any], headers: dict[str, str]
    ) -> FakeResponse:
        """Return the next queued response."""
        self.requests.append((url, json))
        if self._delay:
            await asyncio.sleep(self._delay)
        if not self._responses:
            raise AssertionError(f"unexpected request to {url}")
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)

    async def close(self) -> None:
        """Mark the session closed."""
        self.close_count += 1
        self.closed = True


@pytest.fixture
def client() -> ImouOpenApiClient:
    """Return a client pointed at a fake host."""
    return ImouOpenApiClient("app_id", "app_secret", "api.example.com")


def install_session(
    client: ImouOpenApiClient, responses: list[Any], **kwargs: Any
) -> FakeSession:
    """Attach a fake session so no real HTTP is attempted."""
    session = FakeSession(responses, **kwargs)
    client._session = session
    return session


def endpoints_called(session: FakeSession) -> list[str]:
    """Return the request path of every call, in order."""
    return [url.split("api.example.com", 1)[1] for url, _ in session.requests]


@pytest.mark.asyncio
async def test_fetches_token_before_first_call(client: ImouOpenApiClient) -> None:
    """A request without a token fetches one first, then calls the endpoint."""
    session = install_session(client, [token_result(), api_result(data={"ok": True})])

    result = await client.async_request_api(ENDPOINT, {})

    assert result == {"ok": True}
    assert endpoints_called(session) == [API_ENDPOINT_ACCESS_TOKEN, ENDPOINT]
    assert client.access_token == "tok-1"


@pytest.mark.asyncio
async def test_reuses_token_and_session(client: ImouOpenApiClient) -> None:
    """Once a token is held, later calls neither refetch it nor rebuild the session."""
    session = install_session(
        client, [token_result(), api_result(), api_result(), api_result()]
    )

    for _ in range(3):
        await client.async_request_api(ENDPOINT, {})

    assert endpoints_called(session) == [API_ENDPOINT_ACCESS_TOKEN] + [ENDPOINT] * 3
    assert await client._async_get_session() is session


@pytest.mark.asyncio
async def test_token_is_fetched_once_under_concurrency(
    client: ImouOpenApiClient,
) -> None:
    """Concurrent first calls must not each trigger their own accessToken request."""
    session = install_session(
        client,
        [token_result(), api_result(), api_result(), api_result(), api_result()],
        delay=0.01,
    )

    await asyncio.gather(*(client.async_request_api(ENDPOINT, {}) for _ in range(4)))

    calls = endpoints_called(session)
    assert calls.count(API_ENDPOINT_ACCESS_TOKEN) == 1
    assert calls.count(ENDPOINT) == 4


@pytest.mark.asyncio
async def test_expired_token_is_refreshed_once_under_concurrency(
    client: ImouOpenApiClient,
) -> None:
    """A token expiring mid-flight is refreshed once, not once per in-flight call."""
    client._access_token = "stale"
    session = install_session(
        client,
        [
            api_result(code=ERROR_CODE_TOKEN_OVERDUE, msg="token overdue"),
            api_result(code=ERROR_CODE_TOKEN_OVERDUE, msg="token overdue"),
            token_result("tok-2"),
            api_result(),
            api_result(),
        ],
        delay=0.01,
    )

    await asyncio.gather(*(client.async_request_api(ENDPOINT, {}) for _ in range(2)))

    calls = endpoints_called(session)
    assert calls.count(API_ENDPOINT_ACCESS_TOKEN) == 1
    assert client.access_token == "tok-2"


@pytest.mark.asyncio
async def test_expired_token_retries_the_original_request(
    client: ImouOpenApiClient,
) -> None:
    """After refreshing, the original request is retried with the new token."""
    client._access_token = "stale"
    session = install_session(
        client,
        [
            api_result(code=ERROR_CODE_TOKEN_OVERDUE, msg="token overdue"),
            token_result("tok-2"),
            api_result(data={"ok": True}),
        ],
    )

    assert await client.async_request_api(ENDPOINT, {}) == {"ok": True}

    assert endpoints_called(session) == [
        ENDPOINT,
        API_ENDPOINT_ACCESS_TOKEN,
        ENDPOINT,
    ]
    assert session.requests[-1][1]["params"]["token"] == "tok-2"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [ERROR_CODE_INVALID_SIGN, ERROR_CODE_INVALID_APP])
async def test_invalid_credentials_raise(client: ImouOpenApiClient, code: str) -> None:
    """Signature / app errors surface as InvalidAppIdOrSecretException."""
    install_session(client, [api_result(code=code, msg="bad app")])

    with pytest.raises(InvalidAppIdOrSecretException):
        await client.async_get_token()


@pytest.mark.asyncio
async def test_other_error_code_raises_request_failed(
    client: ImouOpenApiClient,
) -> None:
    """Unmapped business error codes surface as RequestFailedException."""
    install_session(client, [token_result(), api_result(code="DV1007", msg="offline")])

    with pytest.raises(RequestFailedException, match="DV1007"):
        await client.async_request_api(ENDPOINT, {})


@pytest.mark.asyncio
async def test_transport_error_raises_connect_failed(
    client: ImouOpenApiClient,
) -> None:
    """Transport failures surface as ConnectFailedException."""
    install_session(client, [OSError("no route to host")])

    with pytest.raises(ConnectFailedException):
        await client.async_get_token()


@pytest.mark.asyncio
async def test_current_domain_updates_api_host(client: ImouOpenApiClient) -> None:
    """accessToken may redirect the client to a regional host."""
    install_session(
        client,
        [
            api_result(
                data={"accessToken": "tok-1", "currentDomain": "openapi-eu.example.com"}
            )
        ],
    )

    await client.async_get_token()

    assert client._api_url == "openapi-eu.example.com"


@pytest.mark.asyncio
async def test_download_uses_the_shared_session(client: ImouOpenApiClient) -> None:
    """Snapshots reuse the API session instead of building one per download."""
    session = install_session(client, [])

    assert await client.async_download("https://cdn.example.com/snap.jpg") == (
        b"jpeg-bytes"
    )
    await client.async_download("https://cdn.example.com/snap2.jpg")

    assert session.downloads == [
        "https://cdn.example.com/snap.jpg",
        "https://cdn.example.com/snap2.jpg",
    ]
    assert await client._async_get_session() is session


@pytest.mark.asyncio
async def test_download_raises_on_error_status(client: ImouOpenApiClient) -> None:
    """A non-200 download surfaces as RequestFailedException."""
    install_session(client, [], download_status=404)

    with pytest.raises(RequestFailedException, match="404"):
        await client.async_download("https://cdn.example.com/missing.jpg")


@pytest.mark.asyncio
async def test_session_caps_concurrent_connections() -> None:
    """Batched polls must not open one socket per device."""
    client = ImouOpenApiClient("app_id", "app_secret", "api.example.com")

    session = await client._async_get_session()
    try:
        assert session.connector is not None
        assert session.connector.limit == CONNECTION_LIMIT
    finally:
        await client.async_close()


@pytest.mark.asyncio
async def test_close_is_idempotent(client: ImouOpenApiClient) -> None:
    """Closing twice must not fail or double-close the session."""
    session = install_session(client, [])

    await client.async_close()
    await client.async_close()

    assert session.close_count == 1

"""Tests for the ImouOpenApiClient HTTP layer: session reuse and token handling."""

import asyncio
import json
import logging
from collections.abc import Generator
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
    """Minimal aiohttp response stand-in, released by its context manager."""

    def __init__(
        self,
        payload: dict[str, Any],
        status: int = 200,
        *,
        delay: float = 0,
        error: Exception | None = None,
        text_error: Exception | None = None,
    ) -> None:
        """Initialize the response."""
        self.status = status
        self._payload = payload
        self._delay = delay
        self._error = error
        self._text_error = text_error
        self.raw_text: str | None = None
        self.released = False

    async def __aenter__(self) -> "FakeResponse":
        """Issue the request, as aiohttp's request context manager does."""
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return self

    def __await__(self) -> Generator[Any, None, "FakeResponse"]:
        """Support bare ``await``, which aiohttp allows and which leaks."""
        return self.__aenter__().__await__()

    async def __aexit__(self, *exc_info: object) -> None:
        """Return the connection to the pool."""
        self.released = True

    async def text(self) -> str:
        """Return the JSON body, or the raw text the server actually sent."""
        if self._text_error is not None:
            raise self._text_error
        if self.raw_text is not None:
            return self.raw_text
        return json.dumps(self._payload)

    @classmethod
    def raw(cls, status: int, text: str) -> "FakeResponse":
        """Build a response whose body is not the JSON envelope, like a 502 page."""
        response = cls({}, status)
        response.raw_text = text
        return response


class FakeBinaryResponse:
    """Minimal aiohttp response stand-in for binary downloads."""

    def __init__(self, status: int, payload: bytes) -> None:
        """Initialize the response."""
        self.status = status
        self._payload = payload
        self.released = False

    async def __aenter__(self) -> "FakeBinaryResponse":
        """Enter the response context, as aiohttp's request context manager does."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Return the connection to the pool."""
        self.released = True

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
        text_error: Exception | None = None,
    ) -> None:
        """Initialize with a queue of responses or exceptions to raise."""
        self._responses = list(responses)
        self._delay = delay
        self._download_status = download_status
        self._download_payload = download_payload
        self._text_error = text_error
        self.closed = False
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.issued: list[FakeResponse] = []
        self.downloads: list[str] = []
        self.last_download: FakeBinaryResponse | None = None
        self.close_count = 0

    def get(self, url: str, *, timeout: Any = None) -> FakeBinaryResponse:
        """Return the configured binary payload as a response context manager."""
        self.downloads.append(url)
        self.last_download = FakeBinaryResponse(
            self._download_status, self._download_payload
        )
        return self.last_download

    def request(
        self, method: str, url: str, *, json: dict[str, Any], headers: dict[str, str]
    ) -> FakeResponse:
        """Return the next queued response as a request context manager."""
        self.requests.append((url, json))
        if not self._responses:
            raise AssertionError(f"unexpected request to {url}")
        result = self._responses.pop(0)
        if isinstance(result, FakeResponse):
            response = result
        else:
            failed = isinstance(result, Exception)
            response = FakeResponse(
                {} if failed else result,
                delay=self._delay,
                error=result if failed else None,
                text_error=self._text_error,
            )
        self.issued.append(response)
        return response

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
async def test_failed_download_releases_its_connection(
    client: ImouOpenApiClient,
) -> None:
    """The pool is capped, so expired snapshot URLs must not hold connections."""
    session = install_session(client, [], download_status=403)

    for _ in range(CONNECTION_LIMIT + 1):
        with pytest.raises(RequestFailedException):
            await client.async_download("https://cdn.example.com/expired.jpg")
        assert session.last_download is not None
        assert session.last_download.released is True


@pytest.mark.asyncio
async def test_session_caps_concurrent_connections() -> None:
    """Batched polls must not open one socket per device against a host.

    The cap is per host rather than total, so snapshots downloaded from
    storage cannot hold every slot and leave API calls queueing.
    """
    client = ImouOpenApiClient("app_id", "app_secret", "api.example.com")

    session = await client._async_get_session()
    try:
        assert session.connector is not None
        assert session.connector.limit_per_host == CONNECTION_LIMIT
        assert session.connector.limit > CONNECTION_LIMIT
    finally:
        await client.async_close()


@pytest.mark.asyncio
async def test_a_gateway_error_reads_as_not_getting_through(
    client: ImouOpenApiClient,
) -> None:
    """A 5xx names its status and tells the user the far side is unwell.

    Parsing the body first reported this as a JSON failure, which sends whoever
    reads the log looking in the wrong place. Calling it a request failure would
    be little better: nothing is wrong with the request, and the user's next
    step is to wait rather than to check their settings.
    """
    install_session(client, [FakeResponse.raw(502, "<html>Bad Gateway</html>")])

    with pytest.raises(ConnectFailedException, match="502"):
        await client.async_get_token()


@pytest.mark.asyncio
async def test_a_refused_request_names_its_status(client: ImouOpenApiClient) -> None:
    """A 4xx is this request being turned away, not a connection problem."""
    install_session(client, [FakeResponse.raw(403, "<html>Forbidden</html>")])

    with pytest.raises(RequestFailedException, match="403"):
        await client.async_get_token()


@pytest.mark.asyncio
async def test_unparseable_success_body_is_a_request_failure(
    client: ImouOpenApiClient,
) -> None:
    """A 200 carrying something other than the JSON envelope is the server's fault."""
    install_session(client, [FakeResponse.raw(200, "not json at all")])

    with pytest.raises(RequestFailedException, match="malformed"):
        await client.async_get_token()


@pytest.mark.asyncio
async def test_request_releases_its_connection_when_the_body_fails(
    client: ImouOpenApiClient,
) -> None:
    """A read that dies mid-body must not keep a connection checked out.

    The pool is capped, so connections stranded by a flaky network would leave
    every later poll waiting on a socket that is never coming back.
    """
    session = install_session(
        client,
        [token_result()] * (CONNECTION_LIMIT + 1),
        text_error=OSError("connection reset by peer"),
    )

    for _ in range(CONNECTION_LIMIT + 1):
        with pytest.raises(ConnectFailedException):
            await client.async_get_token()

    assert len(session.issued) == CONNECTION_LIMIT + 1
    assert all(response.released for response in session.issued)


@pytest.mark.asyncio
async def test_debug_log_keeps_credentials_out(
    client: ImouOpenApiClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Debug logs end up in bug reports, so they must not carry credentials.

    ``sign`` is an MD5 over the app secret and the ``time`` and ``nonce`` that
    are logged next to it, so leaking it hands over everything needed to attack
    the secret offline.
    """
    install_session(client, [token_result("tok-secret"), api_result(data={"ok": True})])

    with caplog.at_level(logging.DEBUG, logger="pyimouapi"):
        await client.async_request_api(ENDPOINT, {})

    assert "tok-secret" not in caplog.text
    assert "app_secret" not in caplog.text
    signs = [body["system"]["sign"] for _, body in client._session.requests]
    for sign in signs:
        assert sign not in caplog.text
    # Still useful for debugging: the endpoint and the outcome survive.
    assert ENDPOINT in caplog.text
    assert "'ok': True" in caplog.text


@pytest.mark.asyncio
async def test_close_is_idempotent(client: ImouOpenApiClient) -> None:
    """Closing twice must not fail or double-close the session."""
    session = install_session(client, [])

    await client.async_close()
    await client.async_close()

    assert session.close_count == 1

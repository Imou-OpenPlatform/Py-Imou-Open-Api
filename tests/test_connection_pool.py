"""Tests that slow downloads cannot starve calls to the API host.

Snapshots are fetched from storage, not from the API host, and a download is
allowed a far longer budget than a request. With a single total cap on the
shared pool, a handful of downloads held every slot and API calls queued until
they hit their own deadline and were reported as connection failures.
"""

import asyncio
import time

import pytest
from aiohttp import web
from pyimouapi import openapi
from pyimouapi.openapi import ImouOpenApiClient

POOL = 2
SLOW = 1.0


async def start_server(handler) -> tuple[web.AppRunner, str]:
    """Run an app on an ephemeral port and return its runner and base URL."""
    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    return runner, f"http://127.0.0.1:{port}/"


@pytest.mark.asyncio
async def test_slow_downloads_do_not_block_another_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saturating storage must leave the API host's own slots free."""
    monkeypatch.setattr(openapi, "CONNECTION_LIMIT", POOL)

    async def slow(request: web.Request) -> web.Response:
        await asyncio.sleep(SLOW)
        return web.Response(body=b"snapshot")

    async def fast(request: web.Request) -> web.Response:
        return web.Response(body=b"ok")

    storage, storage_url = await start_server(slow)
    api, api_url = await start_server(fast)
    client = ImouOpenApiClient("id", "secret", api_url)
    try:
        downloads = [
            asyncio.create_task(client.async_download(storage_url)) for _ in range(POOL)
        ]
        # Let them take their connections before asking for another host.
        await asyncio.sleep(0.1)

        started = time.monotonic()
        assert await client.async_download(api_url) == b"ok"
        waited = time.monotonic() - started

        assert waited < SLOW / 2, (
            f"the API host waited {waited:.2f}s behind the downloads, "
            "so they are sharing one pool of connections"
        )
        assert await asyncio.gather(*downloads) == [b"snapshot"] * POOL
    finally:
        await client.async_close()
        await storage.cleanup()
        await api.cleanup()


@pytest.mark.asyncio
async def test_one_host_is_still_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap still stops an account opening a connection per device."""
    monkeypatch.setattr(openapi, "CONNECTION_LIMIT", POOL)
    in_flight = 0
    peak = 0

    async def counted(request: web.Request) -> web.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return web.Response(body=b"ok")

    server, url = await start_server(counted)
    client = ImouOpenApiClient("id", "secret", url)
    try:
        await asyncio.gather(*(client.async_download(url) for _ in range(POOL * 3)))
        assert peak <= POOL
    finally:
        await client.async_close()
        await server.cleanup()

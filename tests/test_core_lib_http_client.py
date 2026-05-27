"""Unit tests for core_lib.http.BaseAsyncClient retry / success behavior."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from core_lib.http import BaseAsyncClient, HttpClientConfig


def _cfg(**overrides) -> HttpClientConfig:
    base = dict(
        base_url="https://api.example.test",
        source="test_src",
        rate_limit_per_sec=None,
        max_attempts=3,
        backoff_base_s=0.001,
        backoff_max_s=0.01,
    )
    base.update(overrides)
    return HttpClientConfig(**base)


def test_get_success_returns_response(httpx_mock):
    httpx_mock.add_response(
        url="https://api.example.test/hello", json={"ok": True}, status_code=200
    )

    async def go():
        async with BaseAsyncClient(_cfg()) as c:
            return await c.get("/hello")

    resp = asyncio.run(go())
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_retries_on_503_then_succeeds(httpx_mock):
    httpx_mock.add_response(url="https://api.example.test/flaky", status_code=503)
    httpx_mock.add_response(url="https://api.example.test/flaky", status_code=503)
    httpx_mock.add_response(
        url="https://api.example.test/flaky", status_code=200, json={"final": True}
    )

    async def go():
        async with BaseAsyncClient(_cfg()) as c:
            return await c.get("/flaky")

    resp = asyncio.run(go())
    assert resp.status_code == 200
    assert len(httpx_mock.get_requests()) == 3


def test_retries_exhausted_raises(httpx_mock):
    for _ in range(2):
        httpx_mock.add_response(url="https://api.example.test/always-fails", status_code=503)

    async def go():
        async with BaseAsyncClient(_cfg(max_attempts=2)) as c:
            await c.get("/always-fails")

    with pytest.raises(Exception):
        asyncio.run(go())
    assert len(httpx_mock.get_requests()) == 2


def test_4xx_not_retried_and_raises(httpx_mock):
    httpx_mock.add_response(url="https://api.example.test/missing", status_code=404)

    async def go():
        async with BaseAsyncClient(_cfg()) as c:
            await c.get("/missing")

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(go())
    assert len(httpx_mock.get_requests()) == 1  # no retries on 404


def test_429_is_retried(httpx_mock):
    httpx_mock.add_response(url="https://api.example.test/throttled", status_code=429)
    httpx_mock.add_response(url="https://api.example.test/throttled", status_code=200)

    async def go():
        async with BaseAsyncClient(_cfg()) as c:
            return await c.get("/throttled")

    resp = asyncio.run(go())
    assert resp.status_code == 200
    assert len(httpx_mock.get_requests()) == 2

"""Async HTTP base client with retries, token-bucket rate limiting, structured logs."""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)


@dataclass
class HttpClientConfig:
    base_url: str
    source: str
    timeout_s: float = 30.0
    max_attempts: int = 5
    backoff_base_s: float = 0.5
    backoff_max_s: float = 30.0
    rate_limit_per_sec: float | None = 5.0
    rate_limit_burst: int = 10
    default_headers: Mapping[str, str] = field(default_factory=dict)
    retry_on_status: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)


class _RetryableHTTPError(Exception):
    """Internal marker: a retryable response status was observed."""


class BaseAsyncClient:
    """
    Production-grade async HTTP client.

    Subclass per data source for source-specific URL builders, auth, parsing.

        class CensusClient(BaseAsyncClient):
            def __init__(self, api_key: str):
                super().__init__(HttpClientConfig(
                    base_url="https://api.census.gov",
                    source="census",
                    rate_limit_per_sec=10,
                ))
    """

    def __init__(self, config: HttpClientConfig):
        self._cfg = config
        self._client: httpx.AsyncClient | None = None
        if config.rate_limit_per_sec:
            self._limiter: AsyncLimiter | None = AsyncLimiter(
                max_rate=config.rate_limit_burst,
                time_period=config.rate_limit_burst / config.rate_limit_per_sec,
            )
        else:
            self._limiter = None

    async def __aenter__(self) -> "BaseAsyncClient":
        self._client = httpx.AsyncClient(
            base_url=self._cfg.base_url,
            timeout=self._cfg.timeout_s,
            headers=dict(self._cfg.default_headers),
            follow_redirects=True,
            http2=True,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @asynccontextmanager
    async def _slot(self) -> AsyncIterator[None]:
        if self._limiter is not None:
            async with self._limiter:
                yield
        else:
            yield

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("BaseAsyncClient must be used as an async context manager")

        request_id = uuid.uuid4().hex[:12]
        bound = logger.bind(
            source=self._cfg.source,
            request_id=request_id,
            method=method.upper(),
            url=url,
        )

        attempt = 0
        async for try_ctx in AsyncRetrying(
            stop=stop_after_attempt(self._cfg.max_attempts),
            wait=wait_exponential(multiplier=self._cfg.backoff_base_s, max=self._cfg.backoff_max_s)
            + wait_random(0, 0.5),
            retry=retry_if_exception_type((httpx.TransportError, _RetryableHTTPError)),
            reraise=True,
        ):
            with try_ctx:
                attempt += 1
                started = time.monotonic()
                async with self._slot():
                    resp = await self._client.request(
                        method, url, params=params, json=json, headers=headers
                    )
                elapsed_ms = int((time.monotonic() - started) * 1000)
                bound.bind(
                    attempt=attempt,
                    status=resp.status_code,
                    elapsed_ms=elapsed_ms,
                    content_length=len(resp.content),
                ).info("http_response")
                if resp.status_code in self._cfg.retry_on_status:
                    raise _RetryableHTTPError(f"retryable status {resp.status_code}")
                resp.raise_for_status()
                return resp
        raise RuntimeError("unreachable")  # pragma: no cover

    async def get(self, url: str, **kw) -> httpx.Response:
        return await self.request("GET", url, **kw)

    async def post(self, url: str, **kw) -> httpx.Response:
        return await self.request("POST", url, **kw)

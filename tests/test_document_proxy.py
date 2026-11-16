"""Offline tests for /api/document/proxy SSRF, streaming size, and XSS guards."""
from __future__ import annotations

import socket
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.routes import documents


_REAL_ASYNC_CLIENT = httpx.AsyncClient


@asynccontextmanager
async def _asgi_client(app: FastAPI):
    async with _REAL_ASYNC_CLIENT(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


class _FakeConn:
    def __init__(self, known: bool) -> None:
        self._known = known

    async def fetchval(self, _sql: str, _url: str):
        return 1 if self._known else None


class _FakePool:
    def __init__(self, known: bool) -> None:
        self._known = known

    @asynccontextmanager
    async def acquire(self):
        yield _FakeConn(self._known)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(documents.router, prefix="/api")
    return app


def _patch_dns(monkeypatch, mapping: dict[str, list[str]]) -> None:
    def _fake_getaddrinfo(host: str, port, **_kwargs):
        if host not in mapping:
            raise socket.gaierror(f"Unmocked host: {host}")
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))
            for ip in mapping[host]
        ]

    monkeypatch.setattr(documents.socket, "getaddrinfo", _fake_getaddrinfo)


def _patch_httpx(monkeypatch, handler) -> list[str]:
    requested_urls: list[str] = []
    transport = httpx.MockTransport(
        lambda req: (requested_urls.append(str(req.url)) or handler(req))
    )
    real_async_client = httpx.AsyncClient

    def _client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(documents.httpx, "AsyncClient", _client_factory)
    return requested_urls


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    async def _fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(documents.asyncio, "sleep", _fast_sleep)


@pytest.mark.asyncio
async def test_unknown_document_returns_404(monkeypatch):
    async def _fake_pool():
        return _FakePool(known=False)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://example.gov/unknown.pdf"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_valid_pdf_served_inline_with_nosniff(monkeypatch):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    _patch_dns(monkeypatch, {"portal.example.gov": ["93.184.216.34"]})
    _patch_httpx(
        monkeypatch,
        lambda _req: httpx.Response(
            200,
            content=b"%PDF-1.4\nhello",
            headers={"Content-Type": "application/pdf; charset=utf-8"},
        ),
    )

    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/agenda.pdf"})
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4\nhello"
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.headers["content-disposition"] == "inline"
    assert resp.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
@pytest.mark.parametrize("upstream_ct", ["text/html", "image/svg+xml", "application/xhtml+xml"])
async def test_unsafe_content_type_forced_to_attachment(monkeypatch, upstream_ct: str):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    _patch_dns(monkeypatch, {"portal.example.gov": ["93.184.216.34"]})
    _patch_httpx(
        monkeypatch,
        lambda _req: httpx.Response(
            200,
            content=b"<script>alert(1)</script>",
            headers={"Content-Type": upstream_ct},
        ),
    )

    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/page.html"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert resp.headers["content-disposition"] == "attachment"
    assert resp.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_oversized_content_length_returns_413_without_retry(monkeypatch):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    _patch_dns(monkeypatch, {"portal.example.gov": ["93.184.216.34"]})
    requested = _patch_httpx(
        monkeypatch,
        lambda _req: httpx.Response(
            200,
            content=b"small",
            headers={
                "Content-Type": "application/pdf",
                "Content-Length": str(documents._MAX_BYTES + 1),
            },
        ),
    )

    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/huge.pdf"})
    assert resp.status_code == 413
    assert len(requested) == 1


@pytest.mark.asyncio
async def test_oversized_stream_aborts_with_413(monkeypatch):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    monkeypatch.setattr(documents, "_MAX_BYTES", 1024)
    _patch_dns(monkeypatch, {"portal.example.gov": ["93.184.216.34"]})

    class _ChunkedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(10):
                yield b"x" * 256

    requested = _patch_httpx(
        monkeypatch,
        lambda _req: httpx.Response(
            200,
            stream=_ChunkedStream(),
            headers={"Content-Type": "application/pdf"},
        ),
    )

    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/stream.pdf"})
    assert resp.status_code == 413
    assert len(requested) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "redirect_target",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://internal.corp/secret.pdf",
        "file:///etc/passwd",
    ],
)
async def test_redirect_to_private_or_disallowed_target_blocked(monkeypatch, redirect_target: str):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    _patch_dns(
        monkeypatch,
        {
            "portal.example.gov": ["93.184.216.34"],
            "internal.corp": ["10.0.0.5"],
        },
    )
    requested = _patch_httpx(
        monkeypatch,
        lambda _req: httpx.Response(302, headers={"Location": redirect_target}),
    )

    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/redir.pdf"})
    assert resp.status_code == 403
    assert requested == ["https://portal.example.gov/redir.pdf"]


@pytest.mark.asyncio
async def test_redirect_to_public_host_succeeds(monkeypatch):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    _patch_dns(
        monkeypatch,
        {
            "portal.example.gov": ["93.184.216.34"],
            "cdn.example.gov": ["93.184.216.35"],
        },
    )

    def _handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "portal.example.gov":
            return httpx.Response(302, headers={"Location": "https://cdn.example.gov/final.pdf"})
        return httpx.Response(
            200,
            content=b"%PDF-1.7\nok",
            headers={"Content-Type": "application/pdf"},
        )

    _patch_httpx(monkeypatch, _handler)
    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/redir.pdf"})
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.7\nok"


@pytest.mark.asyncio
async def test_too_many_redirects_returns_502(monkeypatch):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    _patch_dns(monkeypatch, {"portal.example.gov": ["93.184.216.34"]})
    _patch_httpx(
        monkeypatch,
        lambda _req: httpx.Response(302, headers={"Location": "https://portal.example.gov/loop"}),
    )

    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/loop"})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_empty_200_retries_then_succeeds(monkeypatch):
    async def _fake_pool():
        return _FakePool(known=True)

    monkeypatch.setattr(documents, "get_db_pool", _fake_pool)
    _patch_dns(monkeypatch, {"portal.example.gov": ["93.184.216.34"]})
    calls = {"n": 0}

    def _handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, content=b"", headers={"Content-Type": "application/pdf"})
        return httpx.Response(200, content=b"%PDF-1.4\nwarmed", headers={"Content-Type": "application/pdf"})

    _patch_httpx(monkeypatch, _handler)
    async with _asgi_client(_make_app()) as client:
        resp = await client.get("/api/document/proxy", params={"url": "https://portal.example.gov/cold.pdf"})
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4\nwarmed"
    assert calls["n"] == 2

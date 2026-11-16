"""
PDF document proxy for inline rendering.

The frontend renders meeting agenda/minutes PDFs inline (react-pdf), which fetches
the file bytes client-side. Government document hosts (Legistar, Granicus, SuiteOne)
rarely send CORS headers, so a direct browser fetch fails. This endpoint proxies the
bytes through the API so, to the browser, the document is same-origin.

SSRF guard: only URLs that already exist in public.event_meeting_document.document_url
are proxied — the client cannot make the server fetch an arbitrary URL.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from loguru import logger
from opentelemetry import trace

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/document", tags=["document"])

tracer = trace.get_tracer(__name__)

# Upper bound on a proxied document. Meeting agenda/minutes PDFs are well under this;
# the cap stops a stray large upstream file from ballooning memory.
_MAX_BYTES = 50 * 1024 * 1024

_MAX_REDIRECTS = 5

# Only allow inline rendering for safe, non-scriptable document types.
# Anything else (e.g. text/html, image/svg+xml) is forced to attachment + octet-stream
# to prevent Same-Origin XSS.
_SAFE_INLINE_CONTENT_TYPES = frozenset({"application/pdf"})

# A browser-like User-Agent. Some government portals (notably SuiteOne/IIS) behave
# differently for non-browser agents; presenting a real browser UA is the reliable choice.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Granular timeouts. SuiteOne lazily materializes large (1–5 MB) PDFs server-side, so
# the *read* budget is generous; connect stays short so a dead host fails fast. The old
# flat 20s total timeout tripped on slow generation and surfaced as a 502.
_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=15.0, pool=10.0)

# SuiteOne portals answer the FIRST cold request for an agenda/minutes file with an
# empty 200 (or a stall) while the file is generated, then serve the real bytes on a
# retry. We retry transient failures (timeouts, 5xx) AND empty 200s a few times.
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_S = 1.0

# SSRF allow-list: a URL is proxyable only if it is a document we already serve.
_URL_KNOWN_SQL = """
    SELECT 1
    FROM event_meeting_document
    WHERE document_url = $1
    LIMIT 1
"""


class _BlockedTargetError(Exception):
    """Raised when a target or redirect URL points to a non-public or disallowed host."""


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True only when the IP address is globally routable."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_global
        and not ip.is_multicast
        and not ip.is_private
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_reserved
        and not ip.is_unspecified
    )


async def _validate_public_url(url: str) -> None:
    """Ensure ``url`` is an http(s) URL whose host resolves exclusively to public IPs."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise _BlockedTargetError("Disallowed URL scheme or missing host")

    host = parsed.hostname
    try:
        ip_literal = ipaddress.ip_address(host)
    except ValueError:
        ip_literal = None

    if ip_literal is not None:
        if not _is_public_ip(ip_literal):
            raise _BlockedTargetError(f"Non-public IP address: {host}")
        return

    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise httpx.ConnectError(f"Failed to resolve host {host}: {exc}") from exc

    if not infos:
        raise _BlockedTargetError(f"Host resolved to no addresses: {host}")

    for info in infos:
        raw_addr = info[4][0].split("%", 1)[0]
        try:
            resolved_ip = ipaddress.ip_address(raw_addr)
        except ValueError as exc:
            raise _BlockedTargetError(f"Invalid resolved IP {raw_addr}") from exc
        if not _is_public_ip(resolved_ip):
            raise _BlockedTargetError(f"Host {host} resolved to non-public IP {raw_addr}")


def _resolve_response_type(upstream_content_type: str | None) -> tuple[str, str]:
    """Return a safe ``(media_type, content_disposition)`` pair for the proxied response."""
    raw_ct = (upstream_content_type or "").split(";")[0].strip().lower()
    if raw_ct in _SAFE_INLINE_CONTENT_TYPES:
        return raw_ct, "inline"
    return "application/octet-stream", "attachment"


async def _stream_bounded_body(resp: httpx.Response) -> bytes:
    """Stream ``resp`` up to ``_MAX_BYTES``, aborting immediately if exceeded."""
    content_length = resp.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BYTES:
                raise HTTPException(status_code=413, detail="Document too large to display")
        except ValueError:
            pass

    buf = bytearray()
    async for chunk in resp.aiter_bytes():
        buf.extend(chunk)
        if len(buf) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail="Document too large to display")
    return bytes(buf)


@router.get("/proxy")
async def proxy_document(
    url: str = Query(..., description="Document URL to proxy (must be a known meeting document)"),
):
    """Stream a known meeting document through the API for same-origin rendering."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        known = await conn.fetchval(_URL_KNOWN_SQL, url)
    if not known:
        # Not a document we serve — refuse rather than fetch an arbitrary URL.
        raise HTTPException(status_code=404, detail="Unknown document")

    with tracer.start_as_current_span("document.proxy") as span:
        span.set_attribute("document.url", url)

        content: bytes | None = None
        upstream_content_type: str | None = None
        last_status: int | None = None
        last_error: Exception | None = None
        headers = {"User-Agent": _BROWSER_UA, "Accept": "application/pdf,*/*"}

        async with httpx.AsyncClient(
            follow_redirects=False, timeout=_TIMEOUT, headers=headers
        ) as client:
            for attempt in range(_RETRY_ATTEMPTS):
                current_url = url
                content = None
                last_status = None
                try:
                    for _ in range(_MAX_REDIRECTS + 1):
                        await _validate_public_url(current_url)
                        async with client.stream(
                            "GET", current_url, follow_redirects=False
                        ) as resp:
                            if resp.is_redirect:
                                location = resp.headers.get("location")
                                if not location:
                                    last_status = resp.status_code
                                    break
                                current_url = urljoin(current_url, location)
                                continue

                            last_status = resp.status_code
                            if resp.status_code != 200:
                                logger.warning(
                                    "Document proxy got {} for {} (attempt {}/{})",
                                    resp.status_code, current_url, attempt + 1, _RETRY_ATTEMPTS,
                                )
                                break

                            body = await _stream_bounded_body(resp)
                            if not body:
                                logger.warning(
                                    "Document proxy got 200 (0 bytes) for {} (attempt {}/{})",
                                    current_url, attempt + 1, _RETRY_ATTEMPTS,
                                )
                                content = b""
                                break

                            content = body
                            upstream_content_type = resp.headers.get("content-type")
                            break
                    else:
                        raise HTTPException(status_code=502, detail="Too many redirects")
                except _BlockedTargetError as exc:
                    span.set_attribute("upstream.blocked", True)
                    logger.warning("Document proxy blocked target {}: {}", current_url, exc)
                    raise HTTPException(status_code=403, detail="Document URL target is not allowed") from exc
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning(
                        "Document proxy fetch failed for {} (attempt {}/{}): {}",
                        url, attempt + 1, _RETRY_ATTEMPTS, exc,
                    )
                else:
                    if content:
                        break

                if attempt < _RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(_RETRY_BACKOFF_S * (attempt + 1))

        if content is None and last_status is None:
            # Every attempt raised (timeout / connection error).
            span.set_attribute("upstream.error", str(last_error))
            raise HTTPException(status_code=502, detail="Failed to fetch document") from last_error

        if last_status is not None and last_status != 200:
            span.set_attribute("upstream.status", last_status)
            raise HTTPException(status_code=502, detail=f"Upstream returned {last_status}")

        if not content:
            # 200 but no bytes after retries — the source portal no longer holds this
            # file (common for purged older-meeting agendas). Signal "gone", not a 502,
            # so the viewer shows an "open the original" state instead of an error.
            span.set_attribute("upstream.empty", True)
            logger.info("Document proxy: upstream served an empty document for {}", url)
            raise HTTPException(status_code=404, detail="Document not available from source")

        content_type, disposition = _resolve_response_type(upstream_content_type)
        span.set_attribute("document.content_type", content_type)

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )

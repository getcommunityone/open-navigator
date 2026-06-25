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

        resp: httpx.Response | None = None
        last_error: Exception | None = None
        headers = {"User-Agent": _BROWSER_UA, "Accept": "application/pdf,*/*"}

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_TIMEOUT, headers=headers
        ) as client:
            for attempt in range(_RETRY_ATTEMPTS):
                try:
                    resp = await client.get(url)
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning(
                        "Document proxy fetch failed for {} (attempt {}/{}): {}",
                        url, attempt + 1, _RETRY_ATTEMPTS, exc,
                    )
                    resp = None
                else:
                    # Success only when we get a 200 with a non-empty body. SuiteOne
                    # returns an empty 200 on a cold cache miss; a retry warms it.
                    if resp.status_code == 200 and resp.content:
                        break
                    logger.warning(
                        "Document proxy got {} ({} bytes) for {} (attempt {}/{})",
                        resp.status_code, len(resp.content), url, attempt + 1, _RETRY_ATTEMPTS,
                    )
                if attempt < _RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(_RETRY_BACKOFF_S * (attempt + 1))

        if resp is None:
            # Every attempt raised (timeout / connection error).
            span.set_attribute("upstream.error", str(last_error))
            raise HTTPException(status_code=502, detail="Failed to fetch document") from last_error

        if resp.status_code != 200:
            span.set_attribute("upstream.status", resp.status_code)
            raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}")

        content = resp.content
        if not content:
            # 200 but no bytes after retries — the source portal no longer holds this
            # file (common for purged older-meeting agendas). Signal "gone", not a 502,
            # so the viewer shows an "open the original" state instead of an error.
            span.set_attribute("upstream.empty", True)
            logger.info("Document proxy: upstream served an empty document for {}", url)
            raise HTTPException(status_code=404, detail="Document not available from source")

        if len(content) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail="Document too large to display")

        # Trust the upstream content-type when present; default to PDF (the common case).
        content_type = (resp.headers.get("content-type") or "application/pdf").split(";")[0].strip()
        if not content_type:
            content_type = "application/pdf"
        span.set_attribute("document.content_type", content_type)

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": "inline",
        },
    )

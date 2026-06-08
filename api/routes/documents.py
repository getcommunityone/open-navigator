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
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                resp = await client.get(url, headers={"User-Agent": "OpenNavigator/1.0"})
        except httpx.HTTPError as exc:
            logger.warning("Document proxy fetch failed for {}: {}", url, exc)
            raise HTTPException(status_code=502, detail="Failed to fetch document") from exc

        if resp.status_code != 200:
            span.set_attribute("upstream.status", resp.status_code)
            raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}")

        content = resp.content
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

"""Sitemaps and the server-rendered SPA shell (#1430).

- ``GET /sitemap.xml``: the sitemap index (the app's sitemap and the docs' sitemap).
- ``GET /sitemap-app.xml``: every public route and live story, with real ``lastmod`` dates (``api.seo``).
- ``GET /api/spa-shell``: the built ``index.html`` with the ``<head>`` meta of the page named by the
  ``X-Original-URI`` header (or ``?uri=``). nginx on the Hugging Face Space sends SPA page requests here
  (``.huggingface/nginx.conf``); the single-process deployment renders the same shell from its catch-all.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from opentelemetry import trace

from api import seo

router = APIRouter(tags=["seo"])
tracer = trace.get_tracer(__name__)

SPA_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"
# The shell must never be cached by a browser: it names the hashed bundles of the current deploy.
NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}
XML_CACHE = {"Cache-Control": "public, max-age=3600"}


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_index() -> Response:
    with tracer.start_as_current_span("seo.sitemap-index"):
        stories = await seo.load_stories()
        urls = seo.sitemap_urls(stories, seo.deployed_on(SPA_INDEX))
        dates = [u.lastmod for u in urls if u.lastmod]
        return Response(
            seo.build_sitemap_index(max(dates) if dates else None),
            media_type="application/xml",
            headers=XML_CACHE,
        )


@router.api_route("/sitemap-app.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_app() -> Response:
    with tracer.start_as_current_span("seo.sitemap-app") as span:
        stories = await seo.load_stories()
        urls = seo.sitemap_urls(stories, seo.deployed_on(SPA_INDEX))
        span.set_attribute("seo.sitemap.urls", len(urls))
        span.set_attribute("seo.stories_loaded", stories is not None)
        return Response(
            seo.build_urlset(urls), media_type="application/xml", headers=XML_CACHE
        )


async def spa_response(index_file: Path, uri: str) -> HTMLResponse:
    path, query = seo.parse_original_uri(uri)
    with tracer.start_as_current_span("seo.spa-shell") as span:
        span.set_attribute("seo.path", path)
        return HTMLResponse(
            await seo.render_spa_page(index_file, path, query), headers=NO_CACHE
        )


@router.api_route("/api/spa-shell", methods=["GET", "HEAD"], include_in_schema=False)
async def spa_shell(
    x_original_uri: str | None = Header(None),
    uri: str | None = Query(
        None,
        description="The page's path and query, when no X-Original-URI header is sent.",
    ),
) -> HTMLResponse:
    if not SPA_INDEX.is_file():
        raise HTTPException(
            status_code=404, detail="No built frontend in this deployment."
        )
    return await spa_response(SPA_INDEX, x_original_uri or uri or "/")

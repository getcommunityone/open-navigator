"""Fetch the official pages behind data center hearing leads, for dbt to verify (#955).

    python -m ingestion.data_centers.fetch_hearing_sources                 # every official lead
    python -m ingestion.data_centers.fetch_hearing_sources --lead wichita-ks-2026-12-03
    python -m ingestion.data_centers.fetch_hearing_sources --dry-run       # fetch, don't write

A *lead* (``seeds.data_center_hearing_lead``) is a claimed upcoming hearing from research
lists. Only a lead with an official government ``source_url`` can become a hearing the site
shows: this CLI fetches that page and stores its text in
``bronze.bronze_data_center_hearing_source``; the dbt model ``data_center_hearing`` then checks
that the page states the meeting date and a data center word, and keeps a quoted excerpt.
Nothing here decides what is true; it only records what each official page says.

Politeness: the descriptive User-Agent, robots.txt checks, per-host spacing and the
never-fetch ``BLOCKED_HOSTS`` list of ``community_events.PoliteFetcher``. One request per lead.
PDF agendas (CivicPlus AgendaCenter serves them) are turned into text with PyMuPDF.

Writes only to the local / dev warehouse: ``--database-url``, else ``NEON_DATABASE_URL_DEV``.
It never falls back to the production database.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import psycopg2
from loguru import logger

from ingestion.data_centers.community_events import (
    PoliteFetcher,
    looks_like_bot_challenge,
    main_content,
    strip_html,
)

TABLE = "bronze.bronze_data_center_hearing_source"
LEADS_SQL = """
    SELECT lead_id, source_url
    FROM seeds.data_center_hearing_lead
    WHERE source_kind = 'official' AND coalesce(source_url, '') <> ''
    ORDER BY meeting_date, lead_id
"""
DDL = f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
        lead_id      text PRIMARY KEY,
        source_url   text NOT NULL,
        final_url    text,
        fetched_at   timestamptz NOT NULL,
        http_status  integer,
        content_type text,
        page_text    text,
        error        text
    )
"""
UPSERT = f"""
    INSERT INTO {TABLE} (lead_id, source_url, final_url, fetched_at, http_status, content_type, page_text, error)
    VALUES (%(lead_id)s, %(source_url)s, %(final_url)s, %(fetched_at)s, %(http_status)s,
            %(content_type)s, %(page_text)s, %(error)s)
    ON CONFLICT (lead_id) DO UPDATE SET
        source_url = EXCLUDED.source_url, final_url = EXCLUDED.final_url,
        fetched_at = EXCLUDED.fetched_at, http_status = EXCLUDED.http_status,
        content_type = EXCLUDED.content_type, page_text = EXCLUDED.page_text, error = EXCLUDED.error
"""

# Query parameters that only track where a click came from (e.g. utm_source=chatgpt.com).
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


@dataclass
class SourcePage:
    lead_id: str
    source_url: str
    final_url: str | None
    fetched_at: datetime
    http_status: int | None
    content_type: str | None
    page_text: str | None
    error: str | None


# Page text kept per lead: far more than any agenda or notice page, small enough for ts_headline.
MAX_PAGE_CHARS = 1_000_000


def clean_url(url: str) -> str:
    """``url`` without tracking parameters (utm_*, fbclid, …). A URL that has none comes back
    exactly as given, so an official URL is never re-encoded for nothing."""
    url = url.strip()
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    query = [
        (k, v) for k, v in pairs if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
    ]
    if len(query) == len(pairs):
        return url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment))


def page_text(body: bytes, content_type: str, *, pdf_text: Callable[[bytes], str]) -> str:
    """Visible text of a fetched page: a PDF's extracted text, or an HTML page's main content."""
    if "pdf" in (content_type or "").lower() or body[:5] == b"%PDF-":
        return pdf_text(body)
    html_doc = body.decode("utf-8", errors="replace")
    return strip_html(main_content(html_doc)) or strip_html(html_doc)


def _pdf_text(body: bytes) -> str:
    from scrapers.suiteone.doctext import (
        extract_pdf_text,  # PyMuPDF; lazy so tests need no fitz
    )

    return extract_pdf_text(body)[0]


def fetch_source(
    fetcher: PoliteFetcher, lead_id: str, source_url: str, *, pdf_text: Callable[[bytes], str] = _pdf_text
) -> SourcePage:
    """Fetch one lead's official page. Every outcome is recorded, never raised."""
    url = clean_url(source_url)
    now = datetime.now(UTC)
    try:
        resp = fetcher.get(url)
    except PermissionError as err:  # robots.txt or the never-fetch list said no
        return SourcePage(lead_id, url, None, now, None, None, None, f"not fetched: {err}")
    except httpx.HTTPError as err:
        return SourcePage(lead_id, url, None, now, None, None, None, f"{type(err).__name__}: {err}")
    ctype = resp.headers.get("content-type", "")
    text: str | None = None
    error: str | None = None
    if resp.status_code >= 400:
        error = f"HTTP {resp.status_code}"
    elif "html" in ctype and looks_like_bot_challenge(resp.text):
        error = "bot challenge page, not the content"
    else:
        try:
            text = page_text(resp.content, ctype, pdf_text=pdf_text).replace("\x00", "")
        except Exception as err:  # noqa: BLE001 - a broken PDF is a recorded outcome, not a crash
            error = f"text extraction failed: {type(err).__name__}: {err}"
        if text is not None and not text.strip():
            is_pdf = "pdf" in ctype.lower() or resp.content[:5] == b"%PDF-"
            error = "PDF has no text layer (scanned?)" if is_pdf else "page has no visible text"
            text = None
        elif text is not None and len(text) > MAX_PAGE_CHARS:
            logger.warning("{}: page text {:,} chars, keeping the first {:,}", lead_id, len(text), MAX_PAGE_CHARS)
            text = text[:MAX_PAGE_CHARS]
    return SourcePage(lead_id, url, str(resp.url), now, resp.status_code, ctype or None, text, error)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lead", action="append", help="Only this lead_id (repeatable).")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report, but don't write.")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("NEON_DATABASE_URL_DEV"),
        help="Local / dev warehouse (default NEON_DATABASE_URL_DEV). Never production.",
    )
    args = parser.parse_args(argv)
    if not args.database_url:
        logger.error("Set NEON_DATABASE_URL_DEV or pass --database-url (the local / dev warehouse)")
        return 2

    with psycopg2.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(LEADS_SQL)
            leads = [(lid, url) for lid, url in cur.fetchall() if not args.lead or lid in args.lead]
        logger.info("{} official lead(s) to fetch", len(leads))
        fetcher = PoliteFetcher(min_interval=3.0)
        pages = [fetch_source(fetcher, lid, url) for lid, url in leads]
        for p in pages:
            chars = len(p.page_text or "")
            if p.error:
                logger.warning("{}: {} ({})", p.lead_id, p.error, p.source_url)
            else:
                logger.info("{}: HTTP {} {} {:,} chars", p.lead_id, p.http_status, p.content_type, chars)
        if args.dry_run:
            logger.info("dry run: nothing written")
            return 0
        with conn.cursor() as cur:
            cur.execute(DDL)
            for p in pages:
                cur.execute(UPSERT, p.__dict__)
        conn.commit()
    ok = sum(1 for p in pages if not p.error)
    logger.success("Stored {} page(s) in {} ({} fetched, {} with an error)", len(pages), TABLE, ok, len(pages) - ok)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

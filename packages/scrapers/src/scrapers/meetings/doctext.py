"""
Extract the text of crawled agenda/minutes PDFs into bronze (#392).

Selects the same documents ``staging.stg_scraped_meeting_documents`` publishes
(day-dated agenda/minutes PDFs from the nationwide homepage crawl, not SuiteOne
rows), reads each PDF from the crawl cache when the file is still on disk and
downloads it otherwise, extracts embedded text with PyMuPDF, and upserts into
``bronze.bronze_meeting_document_text``. Scanned PDFs with no embedded text are
recorded as ``empty_needs_ocr``; nothing is invented.

Usage:
    python -m scrapers.meetings.doctext --state AL [--jurisdiction-id birmingham_0107000]
        [--doc-types agenda,minutes] [--limit N] [--sleep 0.25] [--dry-run]

Already-extracted documents are skipped, so the command resumes where it stopped.
Text lands in ``event_meeting_document.content``, which is mirrored to Neon:
run ``hosting.neon.sync_public_to_neon --dry-run`` after a large state.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from loguru import logger

from scrapers.suiteone.doctext import _DDL, _TEXT_TABLE, _UA, _UPSERT, extract_pdf_text
from scrapers.suiteone.scrape import _resolve_dsn

SCRAPED_TABLES: tuple[str, ...] = (
    "bronze.bronze_events_meetings_counties_scraped",
    "bronze.bronze_events_meetings_municipalities_scraped",
    "bronze.bronze_events_meetings_school_districts_scraped",
)

# Keep in step with dbt_project/models/staging/stg_scraped_meeting_documents.sql.
_PUBLISHED_FILTER = """
    resource_kind = 'pdf'
    AND NULLIF(btrim(url), '') IS NOT NULL
    AND doc_type = ANY(%(doc_types)s)
    AND meeting_date IS NOT NULL
    AND NULLIF(btrim(meeting_date_source), '') IS NOT NULL
    AND meeting_date_source <> 'manifest_year_only'
    AND COALESCE(manifest_relative_path, '') NOT LIKE 'suiteone:%%'
    AND COALESCE(meeting_date_source, '') <> 'suiteone_listing'
"""


def build_select_sql(*, with_jurisdiction: bool) -> str:
    """SQL for the crawled documents in one state that still need text."""
    juris = "AND s.jurisdiction_id = %(jurisdiction_id)s" if with_jurisdiction else ""
    legs = [
        f"""
        SELECT s.jurisdiction_id, s.census_geoid, s.state_code, s.url, s.url_sha256,
               s.doc_type, s.meeting_date, s.local_path
        FROM {table} s
        WHERE s.state_code = %(state)s {juris}
          AND {_PUBLISHED_FILTER}
          AND NOT EXISTS (
              SELECT 1 FROM {_TEXT_TABLE} t
              WHERE t.jurisdiction_id = s.jurisdiction_id AND t.url_sha256 = s.url_sha256
          )"""
        for table in SCRAPED_TABLES
    ]
    return "\nUNION ALL\n".join(legs) + "\nORDER BY meeting_date DESC, jurisdiction_id, url_sha256"


@dataclass(frozen=True)
class CrawledDoc:
    jurisdiction_id: str
    census_geoid: str
    state_code: str
    url: str
    url_sha256: str
    doc_type: str
    meeting_date: date | None
    local_path: str | None


def local_pdf_bytes(local_path: str | None, repo_root: Path) -> bytes | None:
    """The cached PDF's bytes when the crawl's file is still on disk, else None."""
    if not local_path:
        return None
    p = Path(local_path)
    if not p.is_absolute():
        p = repo_root / p
    try:
        if p.is_file() and p.suffix.lower() == ".pdf":
            data = p.read_bytes()
            return data if data[:5].startswith(b"%PDF") else None
    except OSError:
        return None
    return None


def text_for(doc: CrawledDoc, client: httpx.Client, repo_root: Path) -> tuple[str, int | None, str]:
    """Return (text, page_count, extraction_method). Never raises for one bad PDF."""
    try:
        data = local_pdf_bytes(doc.local_path, repo_root)
        if data is None:
            resp = client.get(doc.url)
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "").lower()
            if "pdf" not in ctype and not resp.content[:5].startswith(b"%PDF"):
                return "", None, "not_pdf"
            data = resp.content
        text, pages = extract_pdf_text(data)
        return text, pages, ("pymupdf_text" if text else "empty_needs_ocr")
    except Exception as exc:  # noqa: BLE001 — one bad PDF must not abort the run
        logger.warning("Extract failed {} {}: {}", doc.jurisdiction_id, doc.url, exc)
        return "", None, "error"


def extract(
    state: str,
    *,
    doc_types: Sequence[str],
    dsn: str,
    repo_root: Path,
    jurisdiction_id: str | None = None,
    limit: int | None = None,
    sleep: float = 0.25,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Extract text for one state's crawled documents. Returns (processed, with_text)."""
    import psycopg2

    params = {"state": state, "doc_types": list(doc_types), "jurisdiction_id": jurisdiction_id}
    conn = psycopg2.connect(dsn)
    processed = with_text = 0
    try:
        with conn, conn.cursor() as cur:
            cur.execute(_DDL)  # idempotent; the NOT EXISTS needs the table even on a dry run
        with conn.cursor() as cur:
            cur.execute(build_select_sql(with_jurisdiction=bool(jurisdiction_id)), params)
            docs = [CrawledDoc(*row) for row in cur.fetchall()]
        if limit:
            docs = docs[:limit]
        logger.info("Crawled documents to extract for {}: {}", jurisdiction_id or state, len(docs))

        with httpx.Client(follow_redirects=True, timeout=45.0, headers={"User-Agent": _UA}) as client:
            for doc in docs:
                text, pages, method = text_for(doc, client, repo_root)
                processed += 1
                with_text += bool(text)
                if dry_run:
                    logger.info(
                        "  {:<7} {} {} pages={} chars={} ({})",
                        doc.doc_type, doc.meeting_date, doc.jurisdiction_id, pages, len(text), method,
                    )
                else:
                    with conn, conn.cursor() as cur:
                        cur.execute(_UPSERT, (
                            doc.jurisdiction_id, doc.census_geoid, doc.state_code, doc.url,
                            doc.url_sha256, doc.doc_type, doc.meeting_date, text or None,
                            len(text), len(text.split()), pages, method,
                        ))
                if sleep:
                    time.sleep(sleep)
        return processed, with_text
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Extract crawled agenda/minutes PDF text into bronze.")
    p.add_argument("--state", required=True, help="2-letter state code, e.g. AL")
    p.add_argument("--jurisdiction-id", default=None, help="limit to one jurisdiction, e.g. birmingham_0107000")
    p.add_argument("--doc-types", default="agenda,minutes", help="comma list: agenda,minutes")
    p.add_argument("--limit", type=int, default=None, help="cap documents this run")
    p.add_argument("--sleep", type=float, default=0.25, help="delay between documents (politeness)")
    p.add_argument("--repo-root", type=Path, default=Path.cwd(),
                   help="root that the crawl's relative local_path values resolve against (default: cwd)")
    p.add_argument("--dry-run", action="store_true", help="extract and log, write nothing")
    args = p.parse_args(argv)

    state = args.state.strip().upper()
    if len(state) != 2:
        p.error("--state must be a 2-letter code")
    doc_types = [d.strip() for d in args.doc_types.split(",") if d.strip()]
    processed, with_text = extract(
        state, doc_types=doc_types, dsn=_resolve_dsn(), repo_root=args.repo_root.resolve(),
        jurisdiction_id=args.jurisdiction_id, limit=args.limit, sleep=args.sleep, dry_run=args.dry_run,
    )
    logger.success(
        "Processed {} PDFs; extracted text from {} ({:.0f}%). Scanned ones are flagged 'empty_needs_ocr'.",
        processed, with_text, (100.0 * with_text / processed) if processed else 0.0,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

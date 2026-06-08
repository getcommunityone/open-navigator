"""
Extract the full TEXT of scraped SuiteOne agenda/minutes PDFs into bronze, so
the documents become full-text searchable and can feed the meeting analysis as
context (the official record carries dollar amounts / vote tallies / staff
recommendations the spoken transcript often only alludes to).

Downloads each agenda/minutes PDF (URLs already in bronze), extracts digital
text with PyMuPDF, and upserts into ``bronze.bronze_meeting_document_text``
(this module owns the DDL, mirroring the scraped-meetings loader). Scanned PDFs
with no embedded text are recorded with method ``empty_needs_ocr`` for a later
OCR pass — we do NOT fabricate content.

Usage:
    python -m scrapers.suiteone.doctext --jurisdiction-id tuscaloosa_0177256 \
        [--doc-types agenda,minutes] [--limit N] [--sleep 0.25] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from typing import Optional

import httpx
from loguru import logger

from scrapers.suiteone.scrape import _TABLE, _census_geoid, _resolve_dsn

_TEXT_TABLE = "bronze.bronze_meeting_document_text"
_UA = "Mozilla/5.0 (compatible; open-navigator/1.0; civic-data)"

_DDL = f"""
CREATE TABLE IF NOT EXISTS {_TEXT_TABLE} (
    id              bigserial PRIMARY KEY,
    jurisdiction_id text        NOT NULL,
    census_geoid    text        NOT NULL,
    state_code      char(2)     NOT NULL,
    url             text        NOT NULL,
    url_sha256      char(64)    NOT NULL,
    doc_type        text        NOT NULL,
    meeting_date    date,
    content         text,
    content_length  integer,
    word_count      integer,
    page_count      integer,
    extraction_method text      NOT NULL,
    extracted_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (jurisdiction_id, url_sha256)
);
"""

_SELECT = f"""
SELECT url, url_sha256, doc_type, meeting_date, census_geoid, state_code
FROM {_TABLE}
WHERE jurisdiction_id = %s
  AND meeting_date_source = 'suiteone_listing'
  AND resource_kind = 'pdf'
  AND doc_type = ANY(%s)
  AND url_sha256 NOT IN (SELECT url_sha256 FROM {_TEXT_TABLE} WHERE jurisdiction_id = %s)
ORDER BY meeting_date DESC NULLS LAST
"""

_UPSERT = f"""
INSERT INTO {_TEXT_TABLE} (
    jurisdiction_id, census_geoid, state_code, url, url_sha256, doc_type,
    meeting_date, content, content_length, word_count, page_count, extraction_method
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (jurisdiction_id, url_sha256) DO UPDATE SET
    content           = EXCLUDED.content,
    content_length    = EXCLUDED.content_length,
    word_count        = EXCLUDED.word_count,
    page_count        = EXCLUDED.page_count,
    extraction_method = EXCLUDED.extraction_method,
    extracted_at      = now()
"""


def extract_pdf_text(content: bytes) -> tuple[str, int]:
    """Return (text, page_count) from PDF bytes via PyMuPDF."""
    import fitz  # PyMuPDF — lazy import

    parts: list[str] = []
    with fitz.open(stream=content, filetype="pdf") as doc:
        page_count = doc.page_count
        for page in doc:
            parts.append(page.get_text("text"))
    # Postgres text columns reject NUL (0x00), which PDF extraction can emit.
    text = "\n".join(parts).replace("\x00", "").strip()
    return text, page_count


def extract(jurisdiction_id: str, *, doc_types: list[str], dsn: str,
            limit: Optional[int], sleep: float, dry_run: bool) -> tuple[int, int]:
    import psycopg2

    conn = psycopg2.connect(dsn)
    geoid = _census_geoid(jurisdiction_id)
    extracted = with_text = 0
    try:
        # Idempotent schema — created even on a dry run so the resumability
        # NOT IN subquery has a table to reference (creates nothing else).
        with conn, conn.cursor() as cur:
            cur.execute(_DDL)
        with conn.cursor() as cur:
            cur.execute(_SELECT, (jurisdiction_id, doc_types, jurisdiction_id))
            rows = cur.fetchall()
        if limit:
            rows = rows[:limit]
        logger.info("Documents to extract for {} ({}): {}", jurisdiction_id, ",".join(doc_types), len(rows))

        with httpx.Client(follow_redirects=True, timeout=45.0, headers={"User-Agent": _UA}) as client:
            for url, url_sha, doc_type, meeting_date, dgeoid, state_code in rows:
                text, pages, method = "", None, "error"
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    if "pdf" not in resp.headers.get("content-type", "").lower() and not resp.content[:5].startswith(b"%PDF"):
                        method = "not_pdf"
                    else:
                        text, pages = extract_pdf_text(resp.content)
                        method = "pymupdf_text" if text else "empty_needs_ocr"
                except Exception as exc:  # noqa: BLE001 — one bad PDF must not abort
                    logger.warning("Extract failed id-sha={} {}: {}", url_sha[:12], url, exc)

                if text:
                    with_text += 1
                extracted += 1
                if dry_run:
                    logger.info("  {:<7} {} pages={} chars={} ({})", doc_type, meeting_date, pages, len(text), method)
                else:
                    with conn, conn.cursor() as cur:
                        cur.execute(_UPSERT, (
                            jurisdiction_id, dgeoid or geoid, state_code, url,
                            hashlib.sha256(url.encode()).hexdigest() if not url_sha else url_sha,
                            doc_type, meeting_date, text or None,
                            len(text) if text else 0, len(text.split()) if text else 0, pages, method,
                        ))
                if sleep:
                    time.sleep(sleep)
        return extracted, with_text
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Extract agenda/minutes PDF text into bronze.")
    p.add_argument("--jurisdiction-id", required=True)
    p.add_argument("--doc-types", default="agenda,minutes", help="comma list: agenda,minutes")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sleep", type=float, default=0.25)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    doc_types = [d.strip() for d in args.doc_types.split(",") if d.strip()]
    extracted, with_text = extract(
        args.jurisdiction_id, doc_types=doc_types, dsn=_resolve_dsn(),
        limit=args.limit, sleep=args.sleep, dry_run=args.dry_run,
    )
    logger.success(
        "Processed {} PDFs; extracted text from {} ({:.0f}%). Empty/scanned flagged 'empty_needs_ocr'.",
        extracted, with_text, (100.0 * with_text / extracted) if extracted else 0.0,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Enrich scraped SuiteOne MINUTES rows with a real publish date, read from the
PDF's own metadata.

SuiteOne document URLs carry no date and the server returns no Last-Modified
header, but the minutes PDFs themselves embed a ``ModDate`` (when the document
was last saved/finalized) — a sound proxy for "minutes posted". We download each
minutes PDF, read ``ModDate`` (falling back to ``CreationDate``), and merge the
ISO dates into the bronze row's ``raw_resource`` jsonb. dbt then derives the
per-jurisdiction publish lag from these — we do NOT compute the lag here (that
is SQL-shaped transformation, which belongs in dbt).

CreationDate can predate the meeting (the clerk often starts the minutes from
the agenda template), so ``ModDate`` is preferred as the finalized/posted proxy.

Usage:
    python -m scrapers.suiteone.pubdates --jurisdiction-id tuscaloosa_0177256 \
        [--limit N] [--sleep 0.25] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from typing import Optional

import httpx
from loguru import logger

from scrapers.suiteone.scrape import _TABLE, _resolve_dsn

_PDF_DATE_RE = re.compile(r"D:(\d{8})")
_UA = "Mozilla/5.0 (compatible; open-navigator/1.0; civic-data)"


def parse_pdf_date(value: Optional[str]) -> Optional[date]:
    """PDF date string 'D:20251217111429-06'00'' -> date(2025,12,17)."""
    if not value:
        return None
    m = _PDF_DATE_RE.search(value)
    if not m:
        return None
    try:
        return date(int(m.group(1)[0:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8]))
    except ValueError:
        return None


def fetch_pdf_dates(url: str, client: httpx.Client) -> tuple[Optional[date], Optional[date]]:
    """Return (mod_date, creation_date) from a PDF's metadata, or (None, None)."""
    import fitz  # PyMuPDF — lazy import so the base package stays light

    resp = client.get(url)
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    if "pdf" not in ctype.lower() and not resp.content[:5].startswith(b"%PDF"):
        logger.warning("Not a PDF ({}) for {}", ctype, url)
        return None, None
    with fitz.open(stream=resp.content, filetype="pdf") as doc:
        meta = doc.metadata or {}
    return parse_pdf_date(meta.get("modDate")), parse_pdf_date(meta.get("creationDate"))


_SELECT = f"""
SELECT id, url, meeting_date
FROM {_TABLE}
WHERE jurisdiction_id = %s
  AND meeting_date_source = 'suiteone_listing'
  AND doc_type = 'minutes'
  AND (raw_resource->>'pubdate_checked_at') IS NULL
ORDER BY meeting_date DESC NULLS LAST
"""

_UPDATE = f"UPDATE {_TABLE} SET raw_resource = COALESCE(raw_resource,'{{}}'::jsonb) || %s::jsonb WHERE id = %s"


def enrich(jurisdiction_id: str, *, dsn: str, limit: Optional[int], sleep: float,
           dry_run: bool) -> tuple[int, int]:
    import psycopg2

    conn = psycopg2.connect(dsn)
    checked = found = 0
    try:
        with conn.cursor() as cur:
            cur.execute(_SELECT, (jurisdiction_id,))
            rows = cur.fetchall()
        if limit:
            rows = rows[:limit]
        logger.info("Minutes to enrich for {}: {}", jurisdiction_id, len(rows))

        headers = {"User-Agent": _UA}
        with httpx.Client(follow_redirects=True, timeout=30.0, headers=headers) as client:
            for row_id, url, meeting_date in rows:
                mod_d = cre_d = None
                try:
                    mod_d, cre_d = fetch_pdf_dates(url, client)
                except Exception as exc:  # noqa: BLE001 — one bad PDF must not abort the run
                    logger.warning("Fetch/parse failed for id={} {}: {}", row_id, url, exc)

                published = mod_d or cre_d
                source = "pdf_moddate" if mod_d else ("pdf_creationdate" if cre_d else None)
                if published:
                    found += 1
                patch = {
                    "pdf_moddate": mod_d.isoformat() if mod_d else None,
                    "pdf_creationdate": cre_d.isoformat() if cre_d else None,
                    "minutes_published_at": published.isoformat() if published else None,
                    "pubdate_source": source,
                    "pubdate_checked_at": "checked",  # marker so reruns skip resolved rows
                }
                checked += 1
                if dry_run:
                    logger.info("  id={} mtg={} -> published={} ({})", row_id, meeting_date, published, source)
                else:
                    with conn.cursor() as cur:
                        cur.execute(_UPDATE, (json.dumps(patch), row_id))
                    conn.commit()
                if sleep:
                    time.sleep(sleep)
        return checked, found
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Enrich SuiteOne minutes with PDF publish dates.")
    p.add_argument("--jurisdiction-id", required=True, help="e.g. tuscaloosa_0177256")
    p.add_argument("--limit", type=int, default=None, help="cap how many minutes PDFs to fetch")
    p.add_argument("--sleep", type=float, default=0.25, help="delay between requests (politeness)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    checked, found = enrich(
        args.jurisdiction_id,
        dsn=_resolve_dsn(),
        limit=args.limit,
        sleep=args.sleep,
        dry_run=args.dry_run,
    )
    logger.success(
        "Checked {} minutes PDFs; resolved a publish date for {} ({:.0f}%).",
        checked, found, (100.0 * found / checked) if checked else 0.0,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

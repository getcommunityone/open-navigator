"""
Scrape a SuiteOne Media meeting portal and land agenda/minutes documents into
``bronze.bronze_events_meetings_municipalities_scraped`` (the existing scraped
meetings table), keyed to a jurisdiction.

We store the document URL + the REAL meeting date parsed from the listing; we do
NOT download the PDFs here (Phase 0 only needs the links). ``local_path`` /
``file_bytes`` stay NULL — a later pass can download + extract text for FTS and
minutes-publish dates.

Usage:
    python -m scrapers.suiteone.scrape \
        --portal-url https://tuscaloosaal.suiteonemedia.com \
        --jurisdiction-id tuscaloosa_0177256 --state AL \
        [--homepage-url https://www.tuscaloosa.com] [--dry-run]

DSN resolution (dev only — never prod): NEON_DATABASE_URL_DEV ->
OPEN_NAVIGATOR_DATABASE_URL -> localhost:5433/open_navigator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from scrapers.suiteone.portal import MeetingDoc, scrape_portal, scrape_portal_history

_TABLE = "bronze.bronze_events_meetings_municipalities_scraped"


def _resolve_dsn() -> str:
    try:
        from dotenv import load_dotenv

        for parent in Path(__file__).resolve().parents:
            if (parent / ".env").exists():
                load_dotenv(parent / ".env")
                break
    except Exception:  # noqa: BLE001 — dotenv is optional
        pass
    return (
        os.getenv("NEON_DATABASE_URL_DEV", "").strip()
        or os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def _census_geoid(jurisdiction_id: str) -> str:
    """'tuscaloosa_0177256' -> '0177256' (the trailing FIPS geoid)."""
    tail = jurisdiction_id.rsplit("_", 1)[-1]
    if not tail.isdigit():
        raise ValueError(
            f"jurisdiction_id {jurisdiction_id!r} must end in a numeric census geoid"
        )
    return tail


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rows(docs: list[MeetingDoc], *, jurisdiction_id: str, state: str,
          geoid: str, homepage_url: str | None, scraped_at: datetime) -> list[tuple]:
    rows: list[tuple] = []
    for d in docs:
        rows.append(
            (
                jurisdiction_id,
                state.upper()[:2],
                geoid,
                homepage_url,
                scraped_at,
                f"suiteone:{jurisdiction_id}",  # manifest_relative_path marker
                "document",  # resource_category
                "pdf",  # resource_kind
                d.url,
                _sha256(d.url),
                None,  # local_path — not downloaded in Phase 0
                None,  # file_bytes
                d.doc_type,
                f"{d.doc_type} — {d.meeting_title}"[:500],  # anchor_or_link_text
                json.dumps(["suiteone"]),  # detected_stacks
                True,  # is_likely_meeting
                d.meeting_date,
                "suiteone_listing",  # meeting_date_source — REAL listing date
                d.meeting_title,
                json.dumps(d.raw),  # raw_resource
            )
        )
    return rows


_UPSERT = f"""
INSERT INTO {_TABLE} (
    jurisdiction_id, state_code, census_geoid, homepage_url, manifest_scraped_at,
    manifest_relative_path, resource_category, resource_kind, url, url_sha256,
    local_path, file_bytes, doc_type, anchor_or_link_text, detected_stacks,
    is_likely_meeting, meeting_date, meeting_date_source, meeting_title, raw_resource
) VALUES %s
ON CONFLICT (jurisdiction_id, url_sha256) DO UPDATE SET
    doc_type             = EXCLUDED.doc_type,
    anchor_or_link_text  = EXCLUDED.anchor_or_link_text,
    is_likely_meeting    = EXCLUDED.is_likely_meeting,
    meeting_date         = EXCLUDED.meeting_date,
    meeting_date_source  = EXCLUDED.meeting_date_source,
    meeting_title        = EXCLUDED.meeting_title,
    raw_resource         = EXCLUDED.raw_resource,
    manifest_scraped_at  = EXCLUDED.manifest_scraped_at,
    loaded_at            = CURRENT_TIMESTAMP
"""


def load_bronze(rows: list[tuple], dsn: str) -> int:
    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            execute_values(cur, _UPSERT, rows, page_size=200)
        return len(rows)
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape a SuiteOne meeting portal into bronze.")
    parser.add_argument("--portal-url", required=True, help="SuiteOne portal root, e.g. https://tuscaloosaal.suiteonemedia.com")
    parser.add_argument("--jurisdiction-id", required=True, help="e.g. tuscaloosa_0177256")
    parser.add_argument("--state", required=True, help="2-letter state code, e.g. AL")
    parser.add_argument("--homepage-url", default=None, help="canonical jurisdiction homepage")
    parser.add_argument(
        "--include-older",
        action="store_true",
        help="walk every body's 'Older Meetings..' history, not just the root listing",
    )
    parser.add_argument(
        "--since-year",
        type=int,
        default=None,
        help="with --include-older, keep only meetings in this calendar year or later "
        "(e.g. 2021 for the last ~5 years)",
    )
    parser.add_argument("--dry-run", action="store_true", help="parse + summarize, no DB write")
    args = parser.parse_args(argv)

    if args.include_older:
        docs = scrape_portal_history(args.portal_url, since_year=args.since_year)
    else:
        if args.since_year is not None:
            logger.warning("--since-year is ignored without --include-older")
        docs = scrape_portal(args.portal_url)
    if not docs:
        logger.warning("No agenda/minutes documents parsed — nothing to load.")
        return 1

    dated = sum(1 for d in docs if d.meeting_date)
    logger.info(
        "{} docs | {} with a real meeting date | bodies: {}",
        len(docs),
        dated,
        ", ".join(sorted({d.body_name for d in docs})[:8]),
    )

    if args.dry_run:
        for d in docs[:10]:
            logger.info("  {:<7} {} {}  {}", d.doc_type, str(d.meeting_date), d.body_name, d.url)
        logger.success("Dry run — {} rows NOT written.", len(docs))
        return 0

    rows = _rows(
        docs,
        jurisdiction_id=args.jurisdiction_id,
        state=args.state,
        geoid=_census_geoid(args.jurisdiction_id),
        homepage_url=args.homepage_url,
        scraped_at=datetime.now(timezone.utc),
    )
    n = load_bronze(rows, _resolve_dsn())
    logger.success("Upserted {} SuiteOne documents into {} for {}", n, _TABLE, args.jurisdiction_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())

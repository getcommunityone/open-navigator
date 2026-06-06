#!/usr/bin/env python3
"""Load scraped municipal council members into ``bronze.bronze_officials_scraped``.

Source: :mod:`scrapers.municipal.council_roster` (curated or live-scraped rows).
Target: ``NEON_DATABASE_URL_DEV`` (dev only — never prod), table
``bronze.bronze_officials_scraped``, which the dbt model ``stg_scraped__official``
shapes and ``public.contact_official`` unions in beside the OpenStates officials.

This fills the council gap: OpenStates carries Tuscaloosa's mayor but not its 7
district council members. Each row gets a deterministic synthetic OCD-style id
(``ocd-membership/scraped-<sha1>``) so it never collides with real OpenStates
ids and re-runs upsert in place (idempotent).

Run::

    python -m ingestion.municipal.load_council_officials --city tuscaloosa --dry-run
    python -m ingestion.municipal.load_council_officials --city tuscaloosa
    python -m ingestion.municipal.load_council_officials --city tuscaloosa --live
    python -m ingestion.municipal.load_council_officials --json roster.json --city tuscaloosa

Then rebuild the mart::

    dbt run --select stg_scraped__official contact_official
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import psycopg2
from dotenv import load_dotenv
from loguru import logger
from psycopg2.extras import execute_values

from scrapers.municipal.council_roster import CouncilMember, get_council

_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(_ROOT / ".env")

# Dev warehouse DSN precedence — mirrors ingestion.openstates.officials. Dev only.
_TARGET_ENV_CHAIN = (
    "NEON_DATABASE_URL_DEV",
    "NEON_DATABASE_URL",
    "OPEN_NAVIGATOR_DATABASE_URL",
    "DATABASE_URL",
)


def resolve_target_dsn() -> Optional[str]:
    for var in _TARGET_ENV_CHAIN:
        val = os.getenv(var, "").strip()
        if val:
            return val
    return None


def synthesize_membership_id(m: CouncilMember) -> str:
    """Deterministic scraped membership id from the natural key (idempotent)."""
    key = "|".join(
        (m.jurisdiction or "", m.full_name or "", m.district or "", m.title or "")
    ).lower()
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"ocd-membership/scraped-{digest}"


def shape_row(batch_id: str, m: CouncilMember) -> tuple[Any, ...]:
    """Positional tuple matching ``_INSERT_COLUMNS`` order."""
    return (
        batch_id,
        synthesize_membership_id(m),
        m.full_name or None,
        m.title or None,
        m.jurisdiction or None,
        (m.state_code or None),
        m.state or None,
        m.district or None,
        m.office or None,
        m.email or None,
        m.phone or None,
        m.photo_url or None,
    )


_INSERT_COLUMNS = (
    "sync_batch_id",
    "ocd_membership_id",
    "full_name",
    "title",
    "jurisdiction",
    "state_code",
    "state",
    "district",
    "office",
    "email",
    "phone",
    "photo_url",
)

_INSERT_TEMPLATE = "(%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

CREATE_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_officials_scraped (
    id                BIGSERIAL PRIMARY KEY,
    sync_batch_id     UUID NOT NULL,
    ocd_membership_id TEXT NOT NULL,
    full_name         TEXT,
    title             TEXT,
    jurisdiction      TEXT,
    state_code        CHAR(2),
    state             TEXT,
    district          TEXT,
    office            TEXT,
    email             TEXT,
    phone             TEXT,
    photo_url         TEXT,
    is_current        BOOLEAN NOT NULL DEFAULT TRUE,
    synced_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bronze_officials_scraped_membership
    ON bronze.bronze_officials_scraped (ocd_membership_id);
CREATE INDEX IF NOT EXISTS idx_bronze_officials_scraped_state
    ON bronze.bronze_officials_scraped (state_code);
"""


def ensure_target_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()


def upsert(conn, batch_id: str, members: list[CouncilMember]) -> int:
    if not members:
        return 0
    values = [shape_row(batch_id, m) for m in members]
    cols_sql = ", ".join(_INSERT_COLUMNS)
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"""
            INSERT INTO bronze.bronze_officials_scraped ({cols_sql})
            VALUES %s
            ON CONFLICT (ocd_membership_id) DO UPDATE SET
                sync_batch_id = EXCLUDED.sync_batch_id,
                full_name     = EXCLUDED.full_name,
                title         = EXCLUDED.title,
                jurisdiction  = EXCLUDED.jurisdiction,
                state_code    = EXCLUDED.state_code,
                state         = EXCLUDED.state,
                district      = EXCLUDED.district,
                office        = EXCLUDED.office,
                email         = EXCLUDED.email,
                phone         = EXCLUDED.phone,
                photo_url     = EXCLUDED.photo_url,
                is_current    = TRUE,
                synced_at     = CURRENT_TIMESTAMP
            """,
            values,
            template=_INSERT_TEMPLATE,
            page_size=200,
        )
    conn.commit()
    return len(values)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--city", default="tuscaloosa", help="City slug (default: tuscaloosa)")
    p.add_argument("--live", action="store_true", help="Scrape live page (else curated roster)")
    p.add_argument("--json", dest="json_path", default=None, help="Load roster from a JSON file")
    p.add_argument("--dry-run", action="store_true", help="Summarize without writing")
    args = p.parse_args(argv)

    members = get_council(args.city, live=args.live, json_path=args.json_path)
    logger.info("{}: {} council members to load", args.city, len(members))
    for m in members:
        logger.info("  {} — {} ({})", m.full_name, m.district or "?", m.title)

    if args.dry_run:
        logger.success("DRY RUN: would upsert {} rows into bronze.bronze_officials_scraped", len(members))
        return 0

    target = resolve_target_dsn()
    if not target:
        logger.error("no dev warehouse DSN set (tried {})", ", ".join(_TARGET_ENV_CHAIN))
        return 2

    batch_id = str(uuid.uuid4())
    start = time.monotonic()
    conn = psycopg2.connect(target)
    try:
        ensure_target_table(conn)
        written = upsert(conn, batch_id, members)
    finally:
        conn.close()
    logger.success(
        "upserted {} council members into bronze.bronze_officials_scraped in {:.1f}s (batch {})",
        written,
        time.monotonic() - start,
        batch_id,
    )
    logger.info("next: dbt run --select stg_scraped__official contact_official")
    return 0


if __name__ == "__main__":
    sys.exit(main())

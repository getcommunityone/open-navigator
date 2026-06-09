#!/usr/bin/env python3
"""
Sync the SLIM event_documents (transcript cues) from Local to Neon.

Why this loader exists
----------------------
On the civic-only, free-tier (~0.5 GB) Neon deployment, `public.event_documents`
CANNOT be rebuilt by `dbt run --target neon` because its upstreams are
deliberately absent there (event_documents <- events_text_search <- bronze
`bronze_event_youtube_transcript`, the 8.3 GB table excluded from the Neon sync).
So `event_documents` is excluded from the `neon_serving` dbt selector and is
instead COPIED here in a slimmed form:

  - `segments` (the timed transcript cues read by api/routes/meetings.py) is
    rebuilt as {"s": round(start, 1), "t": text} — the `duration` field and the
    long float precision are dropped. This is the ~235 MB the cue feature costs
    on Neon (vs ~559 MB for the full table).
  - `content` (full transcript ~125 MB) and `content_tsv` (FTS vector + GIN
    ~140 MB) are dropped: national document full-text search is disabled on the
    free tier. search_documents_pg simply returns empty (content_tsv IS NULL)
    rather than erroring. A 300-char `content_excerpt` is kept for any snippet.

Net effect: the cue feature (clickable video timestamps) works on Neon for the
analyzed meetings that have transcripts, within the 0.5 GB budget.

Usage::

    python -m hosting.neon.sync_event_documents_to_neon            # incremental upsert
    python -m hosting.neon.sync_event_documents_to_neon --full     # drop + recreate, then load
    python -m hosting.neon.sync_event_documents_to_neon --dry-run  # report sizes only

Prerequisites:
    - NEON_DATABASE_URL (or NEON_DATABASE_URL_DEV) in .env
    - Local warehouse at localhost:5433 (LOCAL_DATABASE_URL)
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

LOCAL_DB_URL = os.getenv(
    "LOCAL_DATABASE_URL",
    "postgresql://postgres:password@localhost:5433/open_navigator",
)
# Prefer the dev Neon branch when present (never target prod from this tool).
NEON_DB_URL = os.getenv("NEON_DATABASE_URL_DEV") or os.getenv("NEON_DATABASE_URL")

# Slim serving schema for public.event_documents on Neon. Mirrors the columns the
# API reads (api/routes/search_postgres.py:search_documents_pg + meetings.py),
# but `content` and `content_tsv` are present-yet-NULL so search degrades to
# empty instead of erroring, and there is NO content_tsv GIN index.
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.event_documents (
    event_document_id  BIGINT PRIMARY KEY,
    event_id           BIGINT,
    document_type      TEXT,
    document_source    TEXT,
    video_id           TEXT,
    content            TEXT,          -- always NULL on Neon (full text dropped)
    content_excerpt    TEXT,          -- LEFT(content, 300) for snippet display
    content_tsv        TSVECTOR,      -- always NULL on Neon (no FTS / no GIN)
    content_length     INTEGER,
    word_count         INTEGER,
    language           TEXT,
    is_auto_generated  BOOLEAN,
    segments           JSONB,         -- slim cues: [{"s": start, "t": text}, ...]
    event_title        TEXT,
    event_date         DATE,
    jurisdiction_name  TEXT,
    jurisdiction_type  TEXT,
    state_code         TEXT,
    state              TEXT,
    city               TEXT,
    video_url          TEXT,
    created_at         TIMESTAMP
)
"""

# btree indexes the API needs (video_id drives the meeting transcript lookup).
# No content_tsv GIN: content_tsv is NULL on Neon, FTS is intentionally off.
_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS event_documents_video_id_idx ON public.event_documents (video_id)",
    "CREATE INDEX IF NOT EXISTS event_documents_event_id_idx ON public.event_documents (event_id)",
    "CREATE INDEX IF NOT EXISTS event_documents_state_code_idx ON public.event_documents (state_code)",
]

# Columns we actually load (content + content_tsv are left to their NULL default).
_LOAD_COLUMNS = [
    "event_document_id", "event_id", "document_type", "document_source", "video_id",
    "content_excerpt", "content_length", "word_count", "language", "is_auto_generated",
    "segments", "event_title", "event_date", "jurisdiction_name", "jurisdiction_type",
    "state_code", "state", "city", "video_url", "created_at",
]
# publish_public_serving.sql materializes FROM gold.event_documents (content
# NULLed, segments pre-trimmed) — reading it here would yield a NULL
# content_excerpt and, when the local publish step hasn't run, zero rows. gold is
# the canonical full table (content + full segments) the publish macro itself
# reads, so we mirror it. See publish_public_serving.sql:157-173.
_SOURCE_SCHEMA = "gold"

# Analyzed-event scope (matches event.sql's `target.name == 'neon'` predicate and
# the API's EVENTS_REQUIRE_ANALYSIS=True): keep only docs whose video_id resolves
# to an analyzed meeting in event_meeting. Unanalyzed events are never shown
# (EVENTS_REQUIRE_ANALYSIS), so their transcripts are dead weight on Neon. This is
# the "analyzed-scoped" half of the civic-only/analyzed-scoped/cues-only plan —
# without it the slim copy ships all ~6.4k docs (~237 MB) and busts the 0.5 GB
# free tier; with it ~1.7k docs (~65-80 MB on disk).
_ANALYZED_SCOPE_SQL = f"""
WHERE NULLIF(TRIM(video_id), '') IN (
    SELECT DISTINCT NULLIF(TRIM(video_id), '')
    FROM {_SOURCE_SCHEMA}.event_meeting
    WHERE NULLIF(TRIM(video_id), '') IS NOT NULL
)
"""

# Server-side slim projection read from local public.event_documents. `segments`
# is emitted as ::text so psycopg2 round-trips it cleanly; it is re-cast to jsonb
# on INSERT (see _LOAD_PLACEHOLDERS).
_SELECT_SLIM_SQL = (
    """
SELECT
    event_document_id,
    event_id,
    document_type,
    document_source,
    video_id,
    LEFT(content, 300)                                   AS content_excerpt,
    content_length,
    word_count,
    language,
    is_auto_generated,
    CASE WHEN segments IS NULL THEN NULL ELSE (
        SELECT jsonb_agg(jsonb_build_object(
            's', round((elem->>'start')::numeric, 1),
            't', elem->>'text'
        ))
        FROM jsonb_array_elements(segments) AS elem
    ) END::text                                          AS segments,
    event_title,
    event_date,
    jurisdiction_name,
    jurisdiction_type,
    state_code,
    state,
    city,
    video_url,
    created_at
FROM """
    + f"{_SOURCE_SCHEMA}.event_documents\n"
    + _ANALYZED_SCOPE_SQL
)

# `segments` (index 10) is cast text -> jsonb; everything else is a plain bind.
_LOAD_PLACEHOLDERS = ", ".join(
    "%s::jsonb" if col == "segments" else "%s" for col in _LOAD_COLUMNS
)


def _projected_size(local_conn) -> tuple[int, str]:
    """Return (row_count, real_on_disk_size) of the slim projection, for dry-run.

    Materializes the slim rows into a TEMP table and reads pg_total_relation_size
    so the figure reflects TOAST compression (the on-disk reality on Neon), NOT
    the much larger uncompressed jsonb payload that pg_column_size would report.
    """
    with local_conn.cursor() as cur:
        cur.execute(
            """
            CREATE TEMP TABLE _ed_slim_probe AS
            SELECT
                event_document_id, event_id, video_id, video_url, event_title,
                jurisdiction_name, city, state, state_code, event_date,
                LEFT(content, 300) AS content_excerpt,
                CASE WHEN segments IS NULL THEN NULL ELSE (
                    SELECT jsonb_agg(jsonb_build_object(
                        's', round((elem->>'start')::numeric, 1),
                        't', elem->>'text'))
                    FROM jsonb_array_elements(segments) AS elem
                ) END AS segments
            FROM """
            + f"{_SOURCE_SCHEMA}.event_documents\n"
            + _ANALYZED_SCOPE_SQL
        )
        cur.execute(
            "SELECT count(*), pg_size_pretty(pg_total_relation_size('_ed_slim_probe')) "
            "FROM _ed_slim_probe"
        )
        rows, size = cur.fetchone()
        cur.execute("DROP TABLE _ed_slim_probe")
    return rows, size


def _ensure_table(neon_conn, full: bool) -> None:
    """Create the slim event_documents on Neon (drop first when --full).

    `public.event_documents` may pre-exist on Neon as a VIEW (a leftover from a
    dbt run before it was excluded from the neon_serving selector). A view blocks
    both `CREATE TABLE IF NOT EXISTS` (silent no-op) and `CREATE INDEX` ("not
    supported for views"), so we always drop a view of that name first, and on
    --full drop a table too. `relkind` distinguishes the two ('v' = view).
    """
    with neon_conn.cursor() as cur:
        cur.execute(
            "SELECT relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = 'event_documents'"
        )
        existing = cur.fetchone()
        relkind = existing[0] if existing else None

        if relkind == "v":
            logger.info("🗑️  public.event_documents exists as a VIEW on Neon — dropping it")
            cur.execute("DROP VIEW IF EXISTS public.event_documents CASCADE")
        elif full and relkind is not None:
            logger.info("🗑️  --full: dropping existing public.event_documents table on Neon")
            cur.execute("DROP TABLE IF EXISTS public.event_documents CASCADE")

        cur.execute(_CREATE_TABLE_SQL)
        for stmt in _INDEX_SQL:
            cur.execute(stmt)
    neon_conn.commit()


def sync(local_conn, neon_conn, batch_size: int = 1000) -> int:
    """Copy the slim event_documents rows local -> Neon. Returns rows loaded."""
    logger.info("📥 Reading slim event_documents from local warehouse...")
    with local_conn.cursor() as cur:
        cur.execute(_SELECT_SLIM_SQL)
        rows = cur.fetchall()
    total = len(rows)
    if total == 0:
        logger.warning("⏭️  No analyzed-scoped rows in local {}.event_documents — nothing to load", _SOURCE_SCHEMA)
        return 0
    logger.info("   {} rows fetched", f"{total:,}")

    cols = ", ".join(_LOAD_COLUMNS)
    update_set = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in _LOAD_COLUMNS if c != "event_document_id"
    )
    insert_sql = (
        f"INSERT INTO public.event_documents ({cols}) "
        f"VALUES ({_LOAD_PLACEHOLDERS}) "
        f"ON CONFLICT (event_document_id) DO UPDATE SET {update_set}"
    )

    logger.info("📤 Upserting to Neon (batch size {})...", batch_size)
    with neon_conn.cursor() as cur:
        execute_batch(cur, insert_sql, rows, page_size=batch_size)
    neon_conn.commit()

    with neon_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), pg_size_pretty(pg_total_relation_size('public.event_documents')) "
            "FROM public.event_documents"
        )
        neon_count, neon_size = cur.fetchone()
    logger.success("✅ Loaded {} rows — Neon event_documents now {} ({})",
                   f"{total:,}", f"{neon_count:,}", neon_size)
    return total


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync the slim (cues-only) event_documents from local to Neon.",
    )
    parser.add_argument("--full", action="store_true",
                        help="Drop and recreate the Neon table before loading")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Insert batch size (default 1000)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report projected row count / slim size and exit")
    args = parser.parse_args(argv)

    logger.info("📡 Connecting to local warehouse...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)

    if args.dry_run:
        rows, size = _projected_size(local_conn)
        logger.info("🔎 Dry run: {} rows -> slim table ~{} on disk (incl. TOAST, excl. 3 btree indexes)",
                    f"{rows:,}", size)
        local_conn.close()
        return 0

    if not NEON_DB_URL:
        logger.error("❌ NEON_DATABASE_URL_DEV / NEON_DATABASE_URL not set — cannot target Neon")
        local_conn.close()
        return 1

    logger.info("📡 Connecting to Neon...")
    neon_conn = psycopg2.connect(NEON_DB_URL)
    try:
        _ensure_table(neon_conn, full=args.full)
        sync(local_conn, neon_conn, batch_size=args.batch_size)
        return 0
    except Exception as exc:  # noqa: BLE001 — surface + rollback, non-zero exit
        logger.error("❌ event_documents sync failed: {}", exc)
        neon_conn.rollback()
        return 1
    finally:
        local_conn.close()
        neon_conn.close()


if __name__ == "__main__":
    sys.exit(main())

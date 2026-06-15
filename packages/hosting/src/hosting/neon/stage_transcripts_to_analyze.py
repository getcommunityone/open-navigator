#!/usr/bin/env python3
"""
Stage UNANALYZED transcript text from local → Neon for Databricks analysis.

Why this loader exists
----------------------
The `apps/agent-analysis-sync` DAB runs the civic-analysis prompts on Databricks
via `ai_query`, but the raw transcript text is NOT in Unity Catalog — the serving
layer carries analyzed *outputs* only (segments/content were dropped to keep
serving < 500 MB), and the full ~13.7 GB transcript view is deliberately absent
from Neon/UC. So this loader stages ONLY the transcripts that still need analysis
into a small Neon table the DAB then JDBC-reads into UC.

It is the upstream/input twin of :mod:`hosting.neon.sync_event_documents_to_neon`
(which ships analyzed docs for serving); here we ship UNANALYZED text for
processing. "Unanalyzed" = a transcript whose ``video_id`` has no row yet in
``gold.event_meeting`` (no analysis has produced a meeting for it).

Contract (matches the DAB's bronze ingest + README):
    public.transcript_to_analyze (video_id text PRIMARY KEY, transcript_text text)

Replace semantics: the table is a worklist, so each run TRUNCATEs and reloads the
current unanalyzed set (``--full`` drops + recreates instead). Bounded by launch
scope (default) and ``--limit`` so Neon stays small and the analysis run is cheap.

Usage::

    python -m hosting.neon.stage_transcripts_to_analyze --dry-run        # count + size only
    python -m hosting.neon.stage_transcripts_to_analyze --limit 200      # stage a test batch
    python -m hosting.neon.stage_transcripts_to_analyze                  # stage all (launch-scoped)
    python -m hosting.neon.stage_transcripts_to_analyze --no-launch-scope  # nationwide (paid tier)

Prerequisites:
    - NEON_DATABASE_URL_DEV (or NEON_DATABASE_URL) in .env  — never targets prod.
    - Local warehouse at localhost:5433 (LOCAL_DATABASE_URL) with gold.event_documents.
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

# Launch states mirror sync_event_documents_to_neon / publish_public_serving.sql.
LAUNCH_STATES = [
    s.strip().upper()
    for s in os.getenv("LAUNCH_STATES", "AL,GA,MA,WA").split(",")
    if s.strip()
]

# The text source is gold.event_documents.content (the cleaned full transcript the
# platform already uses), keyed by video_id. gold is the canonical full table.
_SOURCE_SCHEMA = "gold"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.transcript_to_analyze (
    video_id        TEXT PRIMARY KEY,
    transcript_text TEXT NOT NULL
)
"""


def _scope_where(launch_scope: bool) -> str:
    """UNANALYZED transcripts: real text, and video_id not yet in event_meeting.

    With ``launch_scope`` (default) also restrict to :data:`LAUNCH_STATES`, so the
    staged worklist matches the serving scope and stays small.
    """
    clauses = [
        "NULLIF(TRIM(video_id), '') IS NOT NULL",
        "NULLIF(TRIM(content), '') IS NOT NULL",
        f"""NULLIF(TRIM(video_id), '') NOT IN (
            SELECT DISTINCT NULLIF(TRIM(video_id), '')
            FROM {_SOURCE_SCHEMA}.event_meeting
            WHERE NULLIF(TRIM(video_id), '') IS NOT NULL
        )""",
    ]
    if launch_scope and LAUNCH_STATES:
        states = ", ".join("'" + s.replace("'", "''") + "'" for s in LAUNCH_STATES)
        clauses.append(f"state_code IN ({states})")
    return "WHERE " + " AND ".join(clauses)


def _select_sql(launch_scope: bool, limit: int) -> str:
    # DISTINCT ON keeps one row per video_id (event_documents can have multiple
    # docs per video); pick the longest content as the analysis body.
    limit_sql = f"\nLIMIT {limit}" if limit and limit > 0 else ""
    return (
        """
SELECT video_id, transcript_text FROM (
    SELECT DISTINCT ON (NULLIF(TRIM(video_id), ''))
        NULLIF(TRIM(video_id), '') AS video_id,
        content                    AS transcript_text
    FROM """
        + f"{_SOURCE_SCHEMA}.event_documents\n"
        + _scope_where(launch_scope)
        + "\n    ORDER BY NULLIF(TRIM(video_id), ''), length(content) DESC\n) q"
        + limit_sql
    )


def _dry_run(local_conn, launch_scope: bool, limit: int) -> tuple[int, str]:
    with local_conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE _stage_probe AS " + _select_sql(launch_scope, limit)
        )
        cur.execute("ANALYZE _stage_probe")
        cur.execute(
            "SELECT count(*), pg_size_pretty(pg_total_relation_size('_stage_probe')) "
            "FROM _stage_probe"
        )
        rows, size = cur.fetchone()
        cur.execute("DROP TABLE _stage_probe")
    return rows, size


def _ensure_table(neon_conn, full: bool) -> None:
    with neon_conn.cursor() as cur:
        cur.execute(
            "SELECT relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = 'transcript_to_analyze'"
        )
        existing = cur.fetchone()
        relkind = existing[0] if existing else None
        if relkind == "v":
            cur.execute("DROP VIEW IF EXISTS public.transcript_to_analyze CASCADE")
        elif full and relkind is not None:
            logger.info("🗑️  --full: dropping existing public.transcript_to_analyze on Neon")
            cur.execute("DROP TABLE IF EXISTS public.transcript_to_analyze CASCADE")
        cur.execute(_CREATE_TABLE_SQL)
    neon_conn.commit()


def stage(local_conn, neon_conn, launch_scope: bool, limit: int, batch_size: int = 500) -> int:
    """Replace the Neon worklist with the current unanalyzed set. Returns rows loaded."""
    scope_label = "launch-scoped" if launch_scope else "nationwide"
    logger.info("📥 Reading {} unanalyzed transcripts from local {}...", scope_label, _SOURCE_SCHEMA)
    with local_conn.cursor() as cur:
        cur.execute(_select_sql(launch_scope, limit))
        rows = cur.fetchall()
    total = len(rows)
    if total == 0:
        logger.warning("⏭️  No unanalyzed transcripts in scope — nothing to stage.")
        return 0
    logger.info("   {} transcripts fetched", f"{total:,}")

    # Worklist = full replace each run (TRUNCATE then insert). ON CONFLICT guards
    # the rare dup video_id across batches.
    with neon_conn.cursor() as cur:
        cur.execute("TRUNCATE public.transcript_to_analyze")
        execute_batch(
            cur,
            "INSERT INTO public.transcript_to_analyze (video_id, transcript_text) "
            "VALUES (%s, %s) ON CONFLICT (video_id) DO UPDATE SET transcript_text = EXCLUDED.transcript_text",
            rows,
            page_size=batch_size,
        )
    neon_conn.commit()

    with neon_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), pg_size_pretty(pg_total_relation_size('public.transcript_to_analyze')) "
            "FROM public.transcript_to_analyze"
        )
        neon_count, neon_size = cur.fetchone()
    logger.success("✅ Staged {} transcripts — Neon transcript_to_analyze now {} ({})",
                   f"{total:,}", f"{neon_count:,}", neon_size)
    return total


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage unanalyzed transcript text from local → Neon for Databricks analysis.",
    )
    parser.add_argument("--full", action="store_true",
                        help="Drop and recreate the Neon table before loading")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max transcripts to stage (0 = all in scope). Use a small value to test cost.")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Insert batch size (default 500)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report staged row count / on-disk size and exit")
    parser.add_argument("--no-launch-scope", action="store_true",
                        help="Stage nationwide (no state filter) — larger, paid-tier only")
    args = parser.parse_args(argv)
    launch_scope = not args.no_launch_scope

    logger.info("📡 Connecting to local warehouse...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)
    if launch_scope:
        logger.info("🎯 Launch scope ON — states {}", ", ".join(LAUNCH_STATES) or "(none)")
    else:
        logger.warning("🌍 Launch scope OFF — staging nationwide")

    if args.dry_run:
        rows, size = _dry_run(local_conn, launch_scope, args.limit)
        logger.info("🔎 Dry run: {} transcripts -> ~{} on disk", f"{rows:,}", size)
        local_conn.close()
        return 0

    if not NEON_DB_URL:
        logger.error("❌ NEON_DATABASE_URL_DEV / NEON_DATABASE_URL not set — cannot target Neon")
        local_conn.close()
        return 1

    logger.info("📡 Connecting to Neon (dev)...")
    neon_conn = psycopg2.connect(NEON_DB_URL)
    try:
        _ensure_table(neon_conn, full=args.full)
        stage(local_conn, neon_conn, launch_scope=launch_scope, limit=args.limit,
              batch_size=args.batch_size)
        return 0
    except Exception as exc:  # noqa: BLE001 — surface + rollback, non-zero exit
        logger.error("❌ transcript staging failed: {}", exc)
        neon_conn.rollback()
        return 1
    finally:
        local_conn.close()
        neon_conn.close()


if __name__ == "__main__":
    sys.exit(main())

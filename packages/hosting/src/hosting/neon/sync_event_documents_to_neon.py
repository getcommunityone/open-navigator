#!/usr/bin/env python3
"""
Sync event_documents (transcript cues + full-text search) from Local to Neon.

Why this loader exists
----------------------
On the civic-only, free-tier (~0.5 GB) Neon deployment, `public.event_documents`
CANNOT be rebuilt by `dbt run --target neon` because its upstreams are
deliberately absent there (event_documents <- events_text_search <- bronze
`bronze_event_youtube_transcript`, the 8.3 GB table excluded from the Neon sync).
So `event_documents` is excluded from the `neon_serving` dbt selector and is
instead COPIED here.

What ships (LAUNCH SCOPE — full-text search ON)
-----------------------------------------------
Transcript/document full-text search MUST work on the serving layer, so unlike
the older cues-only design this loader KEEPS the FTS columns:

  - `content` (full transcript) and `content_tsv` (the FTS vector) are copied
    verbatim, and a `content_tsv` GIN index is built. The document-search leg
    (api/routes/search_postgres.py:search_documents_pg) matches
    `content_tsv @@ plainto_tsquery(...)` and builds its match-evidence snippet
    via `ts_headline('english', content, ...)` — both need the real columns.
  - `segments` (the timed transcript cues read by api/routes/meetings.py) is
    rebuilt as {"s": round(start, 1), "t": text} — the `duration` field and the
    long float precision are dropped.
  - A 300-char `content_excerpt` is kept as the cheap display/snippet fallback.

Keeping full text is affordable ONLY because of the two-part scope:
  - ANALYZED scope: only docs whose video_id resolves to an analyzed meeting in
    `event_meeting` (matches event.sql's `target.name == 'neon'` predicate and
    the API's EVENTS_REQUIRE_ANALYSIS=True).
  - LAUNCH scope: only the launch states (:data:`LAUNCH_STATES`, default
    AL/GA/MA/WA), mirroring publish_public_serving.sql's `launch_states` var.

Together these cut the table from ~7.5 GB (nationwide) to ~4.3k docs / ~300 MB
on Neon (incl. the GIN index) — under the 0.5 GB cap with room for the rest of
the civic serving set. Disable launch scope with `--no-launch-scope` (analyzed
states nationwide) only on a larger paid tier; it will bust the free tier.

Usage::

    python -m hosting.neon.sync_event_documents_to_neon            # incremental upsert
    python -m hosting.neon.sync_event_documents_to_neon --full     # drop + recreate, then load
    python -m hosting.neon.sync_event_documents_to_neon --dry-run  # report sizes only
    python -m hosting.neon.sync_event_documents_to_neon --no-launch-scope  # analyzed nationwide (paid tier)

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

# Launch states: the product launches in 4 counties/states; the serving layer is
# filtered to them so full-text search can stay enabled within the free-tier cap.
# Mirrors publish_public_serving.sql's `launch_states` var (keep in sync).
# Override via the LAUNCH_STATES env var (comma-separated) for a different set.
LAUNCH_STATES = [
    s.strip().upper()
    for s in os.getenv("LAUNCH_STATES", "AL,GA,MA,WA").split(",")
    if s.strip()
]

# Serving schema for public.event_documents on Neon. content + content_tsv are
# POPULATED (full-text search is on) and carry a GIN index; see module docstring.
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.event_documents (
    event_document_id  BIGINT PRIMARY KEY,
    event_id           BIGINT,
    document_type      TEXT,
    document_source    TEXT,
    video_id           TEXT,
    content            TEXT,          -- full transcript (needed by ts_headline snippets)
    content_excerpt    TEXT,          -- LEFT(content, 300) display fallback
    content_tsv        TSVECTOR,      -- FTS vector (GIN-indexed below) — search ON
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

# Indexes the API needs. video_id drives the meeting transcript lookup; the GIN
# on content_tsv backs the document full-text search leg (search_documents_pg
# matches + ts_rank-sorts on content_tsv). Without the GIN that search seq-scans.
_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS event_documents_video_id_idx ON public.event_documents (video_id)",
    "CREATE INDEX IF NOT EXISTS event_documents_event_id_idx ON public.event_documents (event_id)",
    "CREATE INDEX IF NOT EXISTS event_documents_state_code_idx ON public.event_documents (state_code)",
    "CREATE INDEX IF NOT EXISTS event_documents_content_tsv_idx ON public.event_documents USING gin (content_tsv)",
]

# Columns we load. Order MUST match the SELECT projection and the placeholders.
_LOAD_COLUMNS = [
    "event_document_id", "event_id", "document_type", "document_source", "video_id",
    "content", "content_excerpt", "content_tsv",
    "content_length", "word_count", "language", "is_auto_generated",
    "segments", "event_title", "event_date", "jurisdiction_name", "jurisdiction_type",
    "state_code", "state", "city", "video_url", "created_at",
]
# Source the FULL warehouse copy from `gold`, NOT the `public` serving layer.
# gold is the canonical full table (content + content_tsv + full segments) that
# publish_public_serving.sql itself reads. Reading from public would yield the
# slim/NULLed serving copy. See publish_public_serving.sql.
_SOURCE_SCHEMA = "gold"


def _scope_where(launch_scope: bool) -> str:
    """Build the WHERE clause for the local read.

    Always analyzed-scoped (video_id in event_meeting). When ``launch_scope`` is
    on (the default for the free tier), also restricts to :data:`LAUNCH_STATES`.
    """
    clauses = [
        f"""NULLIF(TRIM(video_id), '') IN (
            SELECT DISTINCT NULLIF(TRIM(video_id), '')
            FROM {_SOURCE_SCHEMA}.event_meeting
            WHERE NULLIF(TRIM(video_id), '') IS NOT NULL
        )"""
    ]
    if launch_scope and LAUNCH_STATES:
        states = ", ".join("'" + s.replace("'", "''") + "'" for s in LAUNCH_STATES)
        clauses.append(f"state_code IN ({states})")
    return "WHERE " + " AND ".join(clauses)


def _select_slim_sql(launch_scope: bool) -> str:
    """Server-side projection read from local gold.event_documents.

    `content` + `content_tsv` are kept for full-text search; `content_tsv` is
    emitted as ::text and re-cast to tsvector on INSERT (faithful round-trip, so
    search behaviour matches local exactly). `segments` is emitted as ::text and
    re-cast to jsonb on INSERT. Column order matches :data:`_LOAD_COLUMNS`.
    """
    return (
        """
SELECT
    event_document_id,
    event_id,
    document_type,
    document_source,
    video_id,
    content,
    LEFT(content, 300)                                   AS content_excerpt,
    content_tsv::text                                    AS content_tsv,
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
        + _scope_where(launch_scope)
    )


# Placeholder per column: content_tsv -> ::tsvector, segments -> ::jsonb, rest plain.
def _placeholder(col: str) -> str:
    if col == "segments":
        return "%s::jsonb"
    if col == "content_tsv":
        return "%s::tsvector"
    return "%s"


_LOAD_PLACEHOLDERS = ", ".join(_placeholder(c) for c in _LOAD_COLUMNS)


def _projected_size(local_conn, launch_scope: bool) -> tuple[int, str]:
    """Return (row_count, real_on_disk_size) of the projection, for dry-run.

    Materializes the rows (incl. content + content_tsv + the GIN index) into a
    TEMP table and reads pg_total_relation_size so the figure reflects TOAST
    compression and the index — the on-disk reality on Neon.
    """
    with local_conn.cursor() as cur:
        cur.execute(
            """
            CREATE TEMP TABLE _ed_slim_probe AS
            SELECT
                event_document_id, event_id, video_id, video_url, event_title,
                jurisdiction_name, city, state, state_code, event_date,
                content,
                LEFT(content, 300) AS content_excerpt,
                content_tsv,
                CASE WHEN segments IS NULL THEN NULL ELSE (
                    SELECT jsonb_agg(jsonb_build_object(
                        's', round((elem->>'start')::numeric, 1),
                        't', elem->>'text'))
                    FROM jsonb_array_elements(segments) AS elem
                ) END AS segments
            FROM """
            + f"{_SOURCE_SCHEMA}.event_documents\n"
            + _scope_where(launch_scope)
        )
        cur.execute(
            "CREATE INDEX _ed_slim_probe_tsv ON _ed_slim_probe USING gin (content_tsv)"
        )
        cur.execute("ANALYZE _ed_slim_probe")
        cur.execute(
            "SELECT count(*), pg_size_pretty(pg_total_relation_size('_ed_slim_probe')) "
            "FROM _ed_slim_probe"
        )
        rows, size = cur.fetchone()
        cur.execute("DROP TABLE _ed_slim_probe")
    return rows, size


def _ensure_table(neon_conn, full: bool) -> None:
    """Create event_documents on Neon (drop first when --full).

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


def sync(local_conn, neon_conn, launch_scope: bool, batch_size: int = 1000) -> int:
    """Copy the event_documents rows local -> Neon. Returns rows loaded."""
    scope_label = "launch-scoped" if launch_scope else "analyzed-nationwide"
    logger.info("📥 Reading {} event_documents (with full text) from local warehouse...", scope_label)
    with local_conn.cursor() as cur:
        cur.execute(_select_slim_sql(launch_scope))
        rows = cur.fetchall()
    total = len(rows)
    if total == 0:
        logger.warning("⏭️  No {} rows in local {}.event_documents — nothing to load",
                       scope_label, _SOURCE_SCHEMA)
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
        description="Sync event_documents (transcripts + full-text search) from local to Neon.",
    )
    parser.add_argument("--full", action="store_true",
                        help="Drop and recreate the Neon table before loading")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Insert batch size (default 1000)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report projected row count / on-disk size and exit")
    parser.add_argument("--no-launch-scope", action="store_true",
                        help="Ship analyzed docs nationwide (no state filter) — "
                             "PAID TIER ONLY, busts the 0.5 GB free tier")
    args = parser.parse_args(argv)
    launch_scope = not args.no_launch_scope

    logger.info("📡 Connecting to local warehouse...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)

    if launch_scope:
        logger.info("🎯 Launch scope ON — states {}", ", ".join(LAUNCH_STATES) or "(none)")
    else:
        logger.warning("🌍 Launch scope OFF — shipping analyzed docs nationwide (paid tier)")

    if args.dry_run:
        rows, size = _projected_size(local_conn, launch_scope)
        logger.info("🔎 Dry run: {} rows -> table ~{} on disk (incl. TOAST + content_tsv GIN)",
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
        sync(local_conn, neon_conn, launch_scope=launch_scope, batch_size=args.batch_size)
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

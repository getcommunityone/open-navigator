#!/usr/bin/env python3
"""
Pull Databricks-computed analysis results (UC gold_*) → local warehouse inbound.

The downstream/output twin of :mod:`hosting.neon.stage_transcripts_to_analyze`.
The ``apps/agent-analysis-sync`` DAB runs the analysis prompts on Databricks and
writes two gold tables in Unity Catalog. This loader reads them back over the
Databricks SQL Statement Execution API (via ``databricks-sdk`` — already a dep,
no new connector) and lands them in a local ``analysis_inbound`` schema:

    analysis_inbound.meeting_analysis   (video_id PK)
    analysis_inbound.decision_analysis  (video_id, decision_id PK)

We land into a dedicated inbound schema rather than writing ``gold`` directly:
the final merge into ``gold.event_meeting`` / ``gold.event_decision`` reuses the
existing promote/dbt path (the canonical event_* derivation), which this loader
deliberately does not duplicate. See the agent-analysis-sync README → "Downstream".

Why not write UC serving tables instead: they're a read-only mirror — overwritten
from Neon daily by lakebase-serving-sync — so results must return to ``gold``,
the source of truth, and be re-served through the normal path.

Usage::

    python -m ingestion.databricks.pull_analysis_from_uc --dry-run   # row counts only
    python -m ingestion.databricks.pull_analysis_from_uc             # land both tables
    python -m ingestion.databricks.pull_analysis_from_uc --profile opennav-prod

Prerequisites:
    - A Databricks CLI/SDK profile (default ``opennav-prod``) in ~/.databrickscfg.
    - LOCAL_DATABASE_URL (localhost:5433) in .env.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Iterator, List, Sequence

import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# This repo's .env ships placeholder DATABRICKS_* values; load_dotenv() injects
# them and the SDK ranks env above --profile, pointing at a non-existent host.
# Drop any DATABRICKS_* var still holding a placeholder so the profile wins.
for _k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID"):
    _v = os.environ.get(_k, "")
    if "your-workspace" in _v or _v.startswith("your_") or _v.endswith("_here"):
        os.environ.pop(_k, None)
if not os.environ.get("DATABRICKS_HOST"):
    os.environ.pop("DATABRICKS_TOKEN", None)

LOCAL_DB_URL = os.getenv(
    "LOCAL_DATABASE_URL",
    "postgresql://postgres:password@localhost:5433/open_navigator",
)

DEFAULT_PROFILE = os.getenv("DATABRICKS_CONFIG_PROFILE", "opennav-prod")
DEFAULT_WAREHOUSE = os.getenv("DATABRICKS_WAREHOUSE_ID", "89382a58d0c1c6aa")
DEFAULT_CATALOG = os.getenv("UC_CATALOG", "dbw_opennav_prod_eastus_001")
DEFAULT_SCHEMA = os.getenv("UC_ANALYSIS_SCHEMA", "open_navigator_analysis")
INBOUND_SCHEMA = "analysis_inbound"

# (UC source table, local inbound table, ordered columns, PK columns, DDL)
MEETING_COLS = [
    "video_id", "meeting_summary", "agenda_summary", "session_info",
    "source_ai_model", "extracted_at",
]
DECISION_COLS = [
    "video_id", "decision_id", "headline", "decision_statement", "primary_theme",
    "outcome", "vote_tally", "human_element", "competing_views", "smart_brevity",
    "source_ai_model", "extracted_at",
]

_DDL = {
    "meeting_analysis": f"""
        CREATE TABLE IF NOT EXISTS {INBOUND_SCHEMA}.meeting_analysis (
            video_id        TEXT PRIMARY KEY,
            meeting_summary TEXT,
            agenda_summary  TEXT,
            session_info    TEXT,
            source_ai_model TEXT,
            extracted_at    TIMESTAMP
        )
    """,
    "decision_analysis": f"""
        CREATE TABLE IF NOT EXISTS {INBOUND_SCHEMA}.decision_analysis (
            video_id           TEXT,
            decision_id        TEXT,
            headline           TEXT,
            decision_statement TEXT,
            primary_theme      TEXT,
            outcome            TEXT,
            vote_tally         TEXT,
            human_element      TEXT,
            competing_views    TEXT,
            smart_brevity      TEXT,
            source_ai_model    TEXT,
            extracted_at       TIMESTAMP,
            PRIMARY KEY (video_id, decision_id)
        )
    """,
}


def _fetch_uc_rows(w, warehouse_id: str, catalog: str, schema: str, table: str,
                   cols: Sequence[str]) -> Iterator[List]:
    """Run a SELECT on the warehouse and yield rows across all result chunks.

    Uses INLINE / JSON_ARRAY disposition and paginates via the chunk links so a
    result larger than one chunk is fully read (launch-scoped sets are small, but
    don't assume one chunk).
    """
    from databricks.sdk.service.sql import Disposition, Format, StatementState

    select = f"SELECT {', '.join(cols)} FROM `{catalog}`.`{schema}`.`{table}`"
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=select,
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
        wait_timeout="50s",
    )
    # Poll until the statement leaves a non-terminal state.
    terminal = {StatementState.SUCCEEDED, StatementState.FAILED,
                StatementState.CANCELED, StatementState.CLOSED}
    while resp.status and resp.status.state not in terminal:
        time.sleep(2)
        resp = w.statement_execution.get_statement(resp.statement_id)
    if not resp.status or resp.status.state != StatementState.SUCCEEDED:
        detail = resp.status.error.message if resp.status and resp.status.error else "unknown"
        raise RuntimeError(f"UC query on {table} did not succeed: {detail}")

    result = resp.result
    while result is not None:
        for row in (result.data_array or []):
            yield row
        nxt = result.next_chunk_index
        if nxt is None:
            break
        result = w.statement_execution.get_statement_result_chunk_n(resp.statement_id, nxt)


def _upsert(local_conn, table: str, cols: Sequence[str], pk: Sequence[str],
            rows: List[List], batch_size: int = 500) -> int:
    placeholders = ", ".join(["%s"] * len(cols))
    non_pk = [c for c in cols if c not in pk]
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
    sql = (
        f"INSERT INTO {INBOUND_SCHEMA}.{table} ({', '.join(cols)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {update_set}"
    )
    with local_conn.cursor() as cur:
        execute_batch(cur, sql, rows, page_size=batch_size)
    local_conn.commit()
    return len(rows)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pull Databricks gold_* analysis results back into the local warehouse.",
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="Databricks CLI/SDK profile")
    parser.add_argument("--warehouse-id", default=DEFAULT_WAREHOUSE, help="SQL warehouse id")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="UC schema holding the gold_* tables")
    parser.add_argument("--dry-run", action="store_true", help="Report row counts and exit (no local writes)")
    args = parser.parse_args(argv)

    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        logger.error("❌ databricks-sdk not installed in this environment.")
        return 1

    logger.info("📡 Databricks profile '{}' | warehouse {} | {}.{}",
                args.profile, args.warehouse_id, args.catalog, args.schema)
    w = WorkspaceClient(profile=args.profile)

    targets = [
        ("gold_event_meeting_analysis", "meeting_analysis", MEETING_COLS, ["video_id"]),
        ("gold_event_decision_analysis", "decision_analysis", DECISION_COLS, ["video_id", "decision_id"]),
    ]

    # Pull first (cheap to fail before touching local).
    pulled = {}
    for uc_table, local_table, cols, _pk in targets:
        logger.info("📥 Reading {}.{}.{} ...", args.catalog, args.schema, uc_table)
        rows = list(_fetch_uc_rows(w, args.warehouse_id, args.catalog, args.schema, uc_table, cols))
        pulled[local_table] = rows
        logger.info("   {} rows", f"{len(rows):,}")

    if args.dry_run:
        for _uc, local_table, _c, _pk in targets:
            logger.info("🔎 Dry run: {} would receive {} rows", local_table, f"{len(pulled[local_table]):,}")
        return 0

    logger.info("📡 Connecting to local warehouse...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)
    try:
        with local_conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {INBOUND_SCHEMA}")
            for t in _DDL.values():
                cur.execute(t)
        local_conn.commit()

        for _uc, local_table, cols, pk in targets:
            n = _upsert(local_conn, local_table, cols, pk, pulled[local_table])
            logger.success("✅ {}.{}: upserted {} rows", INBOUND_SCHEMA, local_table, f"{n:,}")

        logger.info(
            "Next: merge {}.{{meeting_analysis,decision_analysis}} into gold via the "
            "existing promote/dbt path (these inbound tables are the handoff; the "
            "event_* derivation is NOT duplicated here).", INBOUND_SCHEMA)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("❌ pull failed: {}", exc)
        local_conn.rollback()
        return 1
    finally:
        local_conn.close()


if __name__ == "__main__":
    sys.exit(main())

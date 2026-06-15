#!/usr/bin/env python3
"""
Load UNANALYZED transcript text from local → a Unity Catalog Delta table.

One-time (or periodic) bootstrap so the ``apps/agent-analysis-sync`` analysis
pipeline is **fully Databricks-resident** at run time: the raw transcript text is
not in any Databricks catalog (the serving layer carries analyzed outputs only;
full-text search is served from Neon, not UC), and the unanalyzed transcripts
exist only in the local ``gold`` warehouse. This loader pushes them up to:

    {catalog}.{schema}.transcript_to_analyze   (video_id, transcript_text)
    {catalog}.{schema}.analysis_prompt          (prompt)   -- the active prompt

so the dbt job reads UC directly — no Neon, no local machine, no secret at run
time (judges just run the dbt job). The local machine is needed ONLY here, to
seed UC; run it again later to top up with more transcripts.

Mechanism: write a parquet locally → upload to a UC Volume (Files API) →
``MERGE`` into the Delta table on ``video_id`` (idempotent append; re-runnable).
The prompt is written via a parameterized statement (no 400-line SQL escaping).

"Unanalyzed" = a transcript (``gold.event_documents.content``) whose ``video_id``
has no row yet in ``gold.event_meeting``.

Usage::

    python -m ingestion.databricks.load_transcripts_to_uc --dry-run        # count only
    python -m ingestion.databricks.load_transcripts_to_uc --limit 150      # seed a batch
    python -m ingestion.databricks.load_transcripts_to_uc                  # seed all in scope

Prerequisites:
    - Databricks CLI/SDK profile (default ``opennav-prod``) in ~/.databrickscfg.
    - LOCAL_DATABASE_URL (localhost:5433) in .env.
    - A SQL warehouse (default the workspace one).
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from pathlib import Path
from typing import List

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# This repo's .env ships placeholder DATABRICKS_* values (your-workspace.cloud...,
# your_warehouse_id_here). load_dotenv() injects them into the environment, where
# the SDK ranks them ABOVE the --profile and our defaults — pointing requests at a
# non-existent host. Drop any DATABRICKS_* var that still holds a placeholder so
# the CLI profile / explicit defaults win.
for _k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID"):
    _v = os.environ.get(_k, "")
    if "your-workspace" in _v or _v.startswith("your_") or _v.endswith("_here"):
        os.environ.pop(_k, None)
# If the host placeholder was present, its token is a placeholder too — drop it.
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
DEFAULT_PROMPT = "prompts/policy_analysis_part_1.md"
VOLUME = "uploads"

LAUNCH_STATES = [
    s.strip().upper()
    for s in os.getenv("LAUNCH_STATES", "AL,GA,MA,WA").split(",")
    if s.strip()
]


def _select_sql(launch_scope: bool, limit: int) -> str:
    clauses = [
        "NULLIF(TRIM(video_id), '') IS NOT NULL",
        "NULLIF(TRIM(content), '') IS NOT NULL",
        """NULLIF(TRIM(video_id), '') NOT IN (
            SELECT DISTINCT NULLIF(TRIM(video_id), '')
            FROM gold.event_meeting WHERE NULLIF(TRIM(video_id), '') IS NOT NULL
        )""",
    ]
    if launch_scope and LAUNCH_STATES:
        states = ", ".join("'" + s.replace("'", "''") + "'" for s in LAUNCH_STATES)
        clauses.append(f"state_code IN ({states})")
    where = "WHERE " + " AND ".join(clauses)
    limit_sql = f"\nLIMIT {limit}" if limit and limit > 0 else ""
    return f"""
        SELECT video_id, transcript_text FROM (
            SELECT DISTINCT ON (NULLIF(TRIM(video_id), ''))
                NULLIF(TRIM(video_id), '') AS video_id,
                content                    AS transcript_text
            FROM gold.event_documents
            {where}
            ORDER BY NULLIF(TRIM(video_id), ''), length(content) DESC
        ) q{limit_sql}
    """


def _exec(w, warehouse_id: str, statement: str, parameters=None) -> None:
    """Run a SQL statement on the warehouse and wait for a terminal state."""
    from databricks.sdk.service.sql import StatementState

    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id, statement=statement, wait_timeout="50s",
        parameters=parameters,
    )
    terminal = {StatementState.SUCCEEDED, StatementState.FAILED,
                StatementState.CANCELED, StatementState.CLOSED}
    while resp.status and resp.status.state not in terminal:
        time.sleep(2)
        resp = w.statement_execution.get_statement(resp.statement_id)
    if not resp.status or resp.status.state != StatementState.SUCCEEDED:
        detail = resp.status.error.message if resp.status and resp.status.error else "unknown"
        raise RuntimeError(f"statement failed: {detail}\n  SQL: {statement[:120]}...")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load unanalyzed transcripts from local → a UC Delta table.",
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--warehouse-id", default=DEFAULT_WAREHOUSE)
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--limit", type=int, default=0, help="Max transcripts (0 = all in scope)")
    parser.add_argument("--prompt-path", default=DEFAULT_PROMPT)
    parser.add_argument("--no-launch-scope", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    launch_scope = not args.no_launch_scope

    logger.info("📡 Reading unanalyzed transcripts from local gold...")
    conn = psycopg2.connect(LOCAL_DB_URL)
    df = pd.read_sql(_select_sql(launch_scope, args.limit), conn)
    conn.close()
    logger.info("   {} transcripts ({} scope)", f"{len(df):,}",
                "launch" if launch_scope else "nationwide")
    if args.dry_run:
        logger.info("🔎 Dry run — would load {} transcripts to {}.{}.transcript_to_analyze",
                    f"{len(df):,}", args.catalog, args.schema)
        return 0
    if df.empty:
        logger.warning("⏭️  Nothing to load.")
        return 0

    prompt_text = Path(args.prompt_path).read_text(encoding="utf-8")

    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementParameterListItem
    except ImportError:
        logger.error("❌ databricks-sdk not installed.")
        return 1
    w = WorkspaceClient(profile=args.profile)
    cat, sch = args.catalog, args.schema
    fq = f"`{cat}`.`{sch}`"

    logger.info("🏗️  Ensuring schema + volume...")
    _exec(w, args.warehouse_id, f"CREATE SCHEMA IF NOT EXISTS {fq}")
    _exec(w, args.warehouse_id, f"CREATE VOLUME IF NOT EXISTS {fq}.`{VOLUME}`")

    # Write parquet locally, upload to the volume.
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    vol_path = f"/Volumes/{cat}/{sch}/{VOLUME}/transcript_to_analyze.parquet"
    logger.info("📤 Uploading parquet ({:,} bytes) -> {}", buf.getbuffer().nbytes, vol_path)
    w.files.upload(vol_path, buf, overwrite=True)

    # Create target + idempotent MERGE (append new video_ids; refresh text on match).
    logger.info("🔀 MERGE into {}.transcript_to_analyze ...", fq)
    _exec(w, args.warehouse_id,
          f"CREATE TABLE IF NOT EXISTS {fq}.transcript_to_analyze "
          f"(video_id STRING, transcript_text STRING) USING delta")
    _exec(w, args.warehouse_id, f"""
        MERGE INTO {fq}.transcript_to_analyze AS t
        USING (SELECT video_id, transcript_text
               FROM read_files('{vol_path}', format => 'parquet')) AS s
        ON t.video_id = s.video_id
        WHEN MATCHED THEN UPDATE SET t.transcript_text = s.transcript_text
        WHEN NOT MATCHED THEN INSERT (video_id, transcript_text) VALUES (s.video_id, s.transcript_text)
    """)

    # Prompt table (parameterized — no SQL escaping of the 400-line prompt).
    logger.info("📝 Writing analysis_prompt ({:,} chars)...", len(prompt_text))
    _exec(w, args.warehouse_id,
          f"CREATE OR REPLACE TABLE {fq}.analysis_prompt AS SELECT :p AS prompt",
          parameters=[StatementParameterListItem(name="p", value=prompt_text)])

    logger.success("✅ Loaded {} transcripts + prompt into {}.{} (Databricks-resident).",
                   f"{len(df):,}", cat, sch)
    return 0


if __name__ == "__main__":
    sys.exit(main())

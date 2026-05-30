#!/usr/bin/env python3
"""
Mirror `opencivicdata_jurisdiction` from the Open States Postgres database into
`bronze.bronze_jurisdictions_openstates`, then rebuild `int_jurisdictions` so each row gets
`open_states_jurisdiction_id` (the OCD jurisdiction id string) where we can derive a Census
GEOID from the linked division id (numeric `/place:` / `/county:` / school-district segment).

Steps:
    1. Apply DDL once: psql \"$DATABASE_URL\" -f \\
       packages/hosting/scripts/neon/migrations/014_create_bronze_jurisdictions_openstates.sql
    2. Ensure OPENSTATES_DATABASE_URL points at your Open States dump DB.
    3. Ensure NEON_DATABASE_URL_DEV or NEON_DATABASE_URL points at open_navigator (target bronze).
    4. Run this script with --migrate if the target table/migration does not exist yet.
    5. Refresh silver with dbt, or run the shell wrapper (recommended on Ubuntu/WSL):

       ./scripts/datasources/openstates/run_openstates_jurisdiction_mapping.sh --migrate

Usage:
    python3 scripts/datasources/openstates/map_openstates_jurisdiction_ids.py
    python3 scripts/datasources/openstates/map_openstates_jurisdiction_ids.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from loguru import logger
from psycopg2.extras import Json, execute_batch

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]

OPENSTATES_URL = os.getenv(
    "OPENSTATES_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/openstates",
)
TARGET_URL = (
    os.getenv("OPEN_NAVIGATOR_DATABASE_URL")
    or os.getenv("NEON_DATABASE_URL_DEV")
    or os.getenv("NEON_DATABASE_URL")
    or os.getenv("DATABASE_URL")
)

MIGRATION_PATH = PROJECT_ROOT / "packages/hosting/scripts/neon/migrations/014_create_bronze_jurisdictions_openstates.sql"

FETCH_SQL = """
    SELECT id, name, url, classification, division_id,
           latest_bill_update, latest_people_update,
           created_at, updated_at,
           extras
    FROM opencivicdata_jurisdiction
"""


def _run_migration(target_url: str) -> None:
    if not MIGRATION_PATH.is_file():
        raise FileNotFoundError(f"Migration not found: {MIGRATION_PATH}")
    logger.info("Applying bronze DDL from {}", MIGRATION_PATH)
    subprocess.run(
        ["psql", target_url, "-v", "ON_ERROR_STOP=1", "-f", str(MIGRATION_PATH)],
        check=True,
    )


def sync_bronze(*, dry_run: bool) -> int:
    if not TARGET_URL:
        raise SystemExit(
            "Set NEON_DATABASE_URL_DEV, NEON_DATABASE_URL, or DATABASE_URL for the open_navigator target."
        )

    logger.info("Reading jurisdictions from Open States DB")
    src = psycopg2.connect(OPENSTATES_URL)
    try:
        with src.cursor() as cur:
            cur.execute(FETCH_SQL)
            raw_rows = cur.fetchall()
    finally:
        src.close()

    # psycopg2 cannot bind a plain dict to JSONB without Json()
    rows = [
        (*r[:-1], Json(r[-1] if r[-1] is not None else {}))
        for r in raw_rows
    ]

    logger.info("Fetched {} opencivicdata_jurisdiction rows", len(rows))

    if dry_run:
        return len(rows)

    tgt = psycopg2.connect(TARGET_URL)
    try:
        with tgt.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'bronze'
                  AND table_name = 'bronze_jurisdictions_openstates'
                """
            )
            if cur.fetchone() is None:
                raise SystemExit(
                    "bronze.bronze_jurisdictions_openstates is missing; run this script with --migrate "
                    "or apply packages/hosting/scripts/neon/migrations/014_create_bronze_jurisdictions_openstates.sql"
                )
            cur.execute("TRUNCATE bronze.bronze_jurisdictions_openstates")
            execute_batch(
                cur,
                """
                INSERT INTO bronze.bronze_jurisdictions_openstates (
                    id, name, url, classification, division_id,
                    latest_bill_update, latest_people_update,
                    created_at, updated_at, extras, loaded_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                """,
                rows,
                page_size=500,
            )
        tgt.commit()
    finally:
        tgt.close()

    logger.success("Loaded bronze.bronze_jurisdictions_openstates ({} rows)", len(rows))
    logger.info("Run: cd dbt_project && dbt run -s int_jurisdictions")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--migrate",
        action="store_true",
        help=f"Run psql -f {MIGRATION_PATH.name} on the target before loading.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch count only; do not write.")
    args = parser.parse_args()

    if args.migrate and not args.dry_run:
        if not TARGET_URL:
            raise SystemExit("TARGET database URL unset; cannot apply --migrate.")
        _run_migration(TARGET_URL)

    sync_bronze(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

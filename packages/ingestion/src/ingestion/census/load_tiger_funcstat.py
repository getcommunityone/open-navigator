"""Load Census TIGER FUNCSTAT onto county and school-district bronze tables (#356).

Gazetteer CSVs for counties and school districts omit FUNCSTAT. TIGER/Line
carries it (county national file; school districts per-state UNSD). This CLI
adds ``funcstat VARCHAR(1)`` when missing and updates from cached CSVs under
``data/cache/census/tiger_funcstat/``.

Usage:
    python -m ingestion.census.load_tiger_funcstat
    python -m ingestion.census.load_tiger_funcstat --dry-run
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import text

from core_lib.db import async_session, resolve_target_database_url
from core_lib.logging import setup_logging
from core_lib.paths import repo_root

CACHE = repo_root(__file__) / "data" / "cache" / "census" / "tiger_funcstat"
COUNTY_CSV = CACHE / "county_funcstat_2024.csv"
SCHOOL_CSV = CACHE / "school_district_funcstat_2024.csv"

_ALTER_COUNTY = """
ALTER TABLE bronze.bronze_jurisdictions_counties
    ADD COLUMN IF NOT EXISTS funcstat VARCHAR(1)
"""
_ALTER_SCHOOL = """
ALTER TABLE bronze.bronze_jurisdictions_school_districts
    ADD COLUMN IF NOT EXISTS funcstat VARCHAR(1)
"""
_INDEX_COUNTY = """
CREATE INDEX IF NOT EXISTS idx_bjc_funcstat
    ON bronze.bronze_jurisdictions_counties(funcstat)
"""
_INDEX_SCHOOL = """
CREATE INDEX IF NOT EXISTS idx_bjsd_funcstat
    ON bronze.bronze_jurisdictions_school_districts(funcstat)
"""


async def _ensure_columns(session) -> None:
    await session.execute(text(_ALTER_COUNTY))
    await session.execute(text(_ALTER_SCHOOL))
    await session.execute(text(_INDEX_COUNTY))
    await session.execute(text(_INDEX_SCHOOL))
    await session.commit()


async def _apply_csv(
    session,
    *,
    table: str,
    csv_path: Path,
    dry_run: bool,
) -> int:
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Missing {csv_path}; build it from TIGER/Line (see #356 / load_tiger_funcstat docs)."
        )
    df = pd.read_csv(csv_path, dtype=str)
    if "GEOID" not in df.columns or "FUNCSTAT" not in df.columns:
        raise ValueError(f"{csv_path} must have GEOID and FUNCSTAT columns")
    rows = [
        {"geoid": str(r.GEOID).strip(), "funcstat": (str(r.FUNCSTAT).strip() or None)}
        for r in df.itertuples(index=False)
        if str(r.GEOID).strip()
    ]
    logger.info("{}: {:,} FUNCSTAT rows from {}", table, len(rows), csv_path.name)
    if dry_run:
        return len(rows)
    # Batch update
    updated = 0
    stmt = text(
        f"""
        UPDATE {table}
        SET funcstat = :funcstat
        WHERE geoid = :geoid
          AND funcstat IS DISTINCT FROM :funcstat
        """
    )
    for i in range(0, len(rows), 500):
        chunk = rows[i : i + 500]
        for row in chunk:
            result = await session.execute(stmt, row)
            updated += result.rowcount or 0
        await session.commit()
    logger.success("{}: updated {:,} rows", table, updated)
    return updated


async def run(*, dry_run: bool = False) -> None:
    setup_logging()
    logger.info("target={}", resolve_target_database_url().split("@")[-1])
    async with async_session() as session:
        if not dry_run:
            await _ensure_columns(session)
        await _apply_csv(
            session,
            table="bronze.bronze_jurisdictions_counties",
            csv_path=COUNTY_CSV,
            dry_run=dry_run,
        )
        await _apply_csv(
            session,
            table="bronze.bronze_jurisdictions_school_districts",
            csv_path=SCHOOL_CSV,
            dry_run=dry_run,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count CSV rows only; do not ALTER/UPDATE.",
    )
    args = parser.parse_args(argv)
    import asyncio

    asyncio.run(run(dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

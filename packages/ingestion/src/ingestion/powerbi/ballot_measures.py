#!/usr/bin/env python3
"""Power BI ballot-measures pipeline: land cached CSV RAW into bronze.

Ported from load_powerbi_ballot_measures_to_bronze.py to the core_lib
DataSourcePipeline contract, then dbt-slimmed: this loader lands the RAW Power BI
CSV row (every source column, verbatim) as ``raw_row`` JSONB plus a
``scrape_batch_id`` ONLY. Everything that used to happen in Python now lives in
dbt (see dbt_project/CONVENTIONS.md):

  * column-alias mapping (``_build_column_map`` / ``COLUMN_ALIASES``) and the
    year / percent / date / int parsing (``_coerce_*``) move to
    dbt_project/models/staging/stg_powerbi__ballot_measure.sql, which reads
    ``raw_row`` JSONB and reproduces those columns in SQL.
  * state / jurisdiction / OCD resolution — formerly a Python query AGAINST
    ``intermediate.int_jurisdictions`` (a layering inversion: the loader read a
    dbt model) — becomes a proper dbt JOIN in
    dbt_project/models/intermediate/int_powerbi__measure_with_jurisdiction.sql,
    which refs int_jurisdictions instead of querying it from Python.

The loader therefore no longer touches int_jurisdictions, no longer maps/parses
columns, and no longer carries a ``--backfill`` UPDATE-join path.

Reads the CSV produced by ``download_powerbi_ballot_measures.py`` and verifies
the post-load count against ``--expected-count`` (default 9670 — the headline
KPI on the source dashboard).

Usage:
    python -m scripts.datasources.powerbi_ballot_measures.ballot_measures_pipeline
    python scripts/datasources/powerbi_ballot_measures/ballot_measures_pipeline.py --truncate
    python scripts/datasources/powerbi_ballot_measures/ballot_measures_pipeline.py \\
        --file data/cache/ncls/ballot_measures_20260524T200000Z.csv \\
        --expected-count 9670

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

CACHE_DIR = _ROOT / "data" / "cache" / "ncls"

TABLE = "bronze.bronze_ballot_measures_powerbi"


# --- DDL (each statement as a SEPARATE text(); never multiple per text()) ----

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_ballot_measures_powerbi (
        id                  BIGSERIAL PRIMARY KEY,
        scrape_batch_id     UUID NOT NULL,
        raw_row             JSONB NOT NULL DEFAULT '{}'::JSONB,
        source_csv_path     TEXT,
        scraped_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        loaded_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_batch ON bronze.bronze_ballot_measures_powerbi (scrape_batch_id)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_ballot_measures_powerbi RESTART IDENTITY")

# Plain append-insert: the source table has a BIGSERIAL surrogate PK and no
# natural unique key, so there is no ON CONFLICT target (matches the original
# loader's append semantics; use --truncate for full reloads).
_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_ballot_measures_powerbi (
        scrape_batch_id, raw_row, source_csv_path
    ) VALUES (
        :scrape_batch_id, CAST(:raw_row AS JSONB), :source_csv_path
    )
    """
)


def find_latest_csv() -> Path:
    csvs = sorted(CACHE_DIR.glob("ballot_measures_*.csv"), reverse=True)
    if not csvs:
        raise FileNotFoundError(
            f"No CSV found in {CACHE_DIR}. Run download_powerbi_ballot_measures.py first."
        )
    return csvs[0]


class BallotMeasureRow(RawRow):
    """One Power BI ballot-measure row, validated before insert (RAW shape).

    Slimmed shape: only the scrape batch id plus the full raw CSV row as a
    JSONB object. Column-alias mapping, parsing, and state/jurisdiction/OCD
    resolution are all derived downstream in dbt from ``raw_row``.
    """

    scrape_batch_id: str
    raw_row: dict[str, Any] = Field(default_factory=dict)
    source_csv_path: str | None = None


class PowerbiBallotMeasuresPipeline(DataSourcePipeline[BallotMeasureRow]):
    source = "powerbi_ballot_measures"
    batch_size = 2_000
    row_schema = BallotMeasureRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or find_latest_csv()

        batch_id = str(uuid.uuid4())
        logger.info("Reading {}", path)
        logger.info("scrape_batch_id = {}", batch_id)

        df = pd.read_csv(path, dtype=str, low_memory=False, keep_default_na=False)
        df = df.replace({"": None})
        source_rows = len(df)
        logger.info("CSV: {:,} rows × {} cols. Columns: {}",
                    source_rows, len(df.columns), list(df.columns))

        if self._limit:
            df = df.head(self._limit)

        for idx, row in df.iterrows():
            # Land the full source row verbatim; dbt maps/parses columns and
            # resolves state/jurisdiction/OCD downstream from this JSONB object.
            raw_row = {k: (None if v is None else str(v)) for k, v in row.to_dict().items()}
            yield {
                "source": self.source,
                "source_version": batch_id,
                "natural_key": f"{batch_id}:{idx}",
                "scrape_batch_id": batch_id,
                "raw_row": raw_row,
                "source_csv_path": str(path),
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[BallotMeasureRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "scrape_batch_id": r.scrape_batch_id,
                "raw_row": json.dumps(r.raw_row),
                "source_csv_path": r.source_csv_path,
            }
            for r in rows
        ]
        await session.execute(_INSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached Power BI ballot-measures CSV RAW into bronze.bronze_ballot_measures_powerbi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", type=Path, help="CSV path (default: latest in data/cache/ncls/)")
    parser.add_argument("--limit", type=int, help="Limit rows (testing)")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument("--expected-count", type=int, default=9670,
                        help="Dashboard KPI card count for logging (default 9670).")
    parser.add_argument(
        "--strict-kpi",
        action="store_true",
        help="Exit with error if loaded row count is outside +/-5%% of --expected-count.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    logger.info("=" * 70)
    logger.info("Power BI Ballot Measures → {}", TABLE)
    logger.info("Cache directory: {}", CACHE_DIR.resolve())
    logger.info("=" * 70)

    await _prepare_target(args.truncate)
    pipeline = PowerbiBallotMeasuresPipeline(path=args.file, limit=args.limit)
    run = await pipeline.run()

    delta = run.loaded - args.expected_count
    tolerance = max(50, int(args.expected_count * 0.05))
    kpi_status = "OK" if abs(delta) <= tolerance else ("UNDER" if delta < 0 else "OVER")
    logger.info(
        "KPI check [{}]: loaded={:,}, dashboard KPI={:,}, Δ={:+} (tolerance ±{:,}). "
        "The table visual often has more rows than the KPI card (multiple topics per measure).",
        kpi_status, run.loaded, args.expected_count, delta, tolerance,
    )

    if args.strict_kpi and abs(delta) > tolerance:
        return 2
    return 0


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

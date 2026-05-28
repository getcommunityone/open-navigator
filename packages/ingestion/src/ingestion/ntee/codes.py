#!/usr/bin/env python3
"""NTEE codes pipeline: land raw IRS/NCCS taxonomy into bronze.bronze_ntee_codes.

The National Taxonomy of Exempt Entities (NTEE) codes classify tax-exempt
nonprofit organizations by their mission and activities.

Source-of-truth resolution order:
    1. Explicit ``--file`` argument.
    2. ``data/cache/ntee/causes_ntee_codes.{csv,parquet}`` (operator-managed).
    3. Vendored seed CSV (``seed_ntee_codes.csv``) — 26-row major-group subset,
       sufficient for local smoke tests but NOT the full 196-code production
       taxonomy. Drop the full file into the cache dir for production loads.

Provenance: IRS Publication 557 + NCCS (National Center for Charitable
Statistics). No upstream URL is hardcoded — NCCS does not publish the code
table as a stable downloadable file under their bulk-data manifest.

The hierarchical ``cause_breadcrumb`` (root > ... > leaf parent-chain path) is
derived downstream in dbt (``int_ntee__breadcrumb``) via a recursive CTE over
``parent_code``; the loader lands only the raw code rows.

Usage:
    python -m ingestion.ntee.codes
    python -m ingestion.ntee.codes --truncate
    python -m ingestion.ntee.codes --file data/cache/ntee/causes_ntee_codes.csv --limit 50

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/ntee")
VENDORED_CSV = Path(__file__).parent / "seed_ntee_codes.csv"


def resolve_source_path(explicit: Path | None = None) -> Path:
    """Pick the source file in explicit → cache → vendored precedence order.

    Operators bootstrap production by dropping the full 196-row taxonomy at
    ``data/cache/ntee/causes_ntee_codes.{parquet,csv}``. Tests and local dev
    fall through to the vendored 26-row seed CSV.
    """
    if explicit is not None:
        return explicit
    for candidate in (
        CACHE_DIR / "causes_ntee_codes.parquet",
        CACHE_DIR / "causes_ntee_codes.csv",
    ):
        if candidate.exists():
            return candidate
    return VENDORED_CSV


def _is_missing(val: Any) -> bool:
    """True for None / NaN / empty-string values."""
    if val is None:
        return True
    try:
        # pandas NaN check without forcing pandas at import time
        import math

        if isinstance(val, float) and math.isnan(val):
            return True
    except Exception:  # noqa: BLE001
        pass
    return str(val).strip() == ""


def _safe_str(val: Any, maxlen: int | None = None) -> str | None:
    if _is_missing(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _read_rows(path: Path) -> list[dict]:
    """Read raw rows from csv/parquet at ``path``."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".parquet":
        import pandas as pd

        return pd.read_parquet(path).to_dict(orient="records")
    raise ValueError(f"Unsupported NTEE source extension: {path.suffix}")


class NteeCodesRow(RawRow):
    """One NTEE classification code, validated before upsert.

    Lands the RAW code row only. The hierarchical `cause_breadcrumb` is derived
    downstream in dbt (int_ntee__breadcrumb) via a recursive CTE over parent_code.
    """

    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    description: str | None = None
    cause_type: str = Field(min_length=1, max_length=20)
    parent_code: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    code_source: str = Field(min_length=1, max_length=50)


# Migration: the legacy combined taxonomy lived at public.cause_ntee with both
# NTEE rows (cause_type='ntee') and EveryOrg rows (cause_type='everyorg').
# Split into two bronze tables per dbt CONVENTIONS.md.
#
# This migration block:
#   1. Creates the bronze schema.
#   2. If public.cause_ntee exists, copies its NTEE-typed rows into the new
#      bronze.bronze_ntee_codes table (best-effort; the EveryOrg rows move via
#      a separate one-off backfill operators can run from the YAML seed).
#   3. Drops public.cause_ntee at the end of a successful split. Operators who
#      want to keep the legacy table can comment out the DROP before running.
_MIGRATE_SQL = text(
    """
    DO $$
    BEGIN
        CREATE SCHEMA IF NOT EXISTS bronze;

        CREATE TABLE IF NOT EXISTS bronze.bronze_ntee_codes (
            code             VARCHAR(100) PRIMARY KEY,
            name             TEXT NOT NULL,
            description      TEXT,
            cause_type       VARCHAR(20) NOT NULL,
            parent_code      VARCHAR(100),
            category         VARCHAR(100),
            subcategory      VARCHAR(100),
            code_source      VARCHAR(50) NOT NULL,
            ingestion_date   TIMESTAMP DEFAULT NOW()
        );

        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'cause_ntee'
        ) THEN
            INSERT INTO bronze.bronze_ntee_codes
                (code, name, description, cause_type, parent_code,
                 category, subcategory, code_source, ingestion_date)
            SELECT
                code, name, description, cause_type, parent_code,
                category, subcategory, source, COALESCE(last_updated, NOW())
            FROM public.cause_ntee
            WHERE cause_type = 'ntee'
            ON CONFLICT (code) DO NOTHING;
        END IF;
    END
    $$;
    """
)

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_ntee_codes (
        code             VARCHAR(100) PRIMARY KEY,
        name             TEXT NOT NULL,
        description      TEXT,
        cause_type       VARCHAR(20) NOT NULL,
        parent_code      VARCHAR(100),
        category         VARCHAR(100),
        subcategory      VARCHAR(100),
        code_source      VARCHAR(50) NOT NULL,
        ingestion_date   TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bnc_type "
        "ON bronze.bronze_ntee_codes(cause_type)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bnc_name_search "
        "ON bronze.bronze_ntee_codes USING gin(to_tsvector('english', name))"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bnc_description_search "
        "ON bronze.bronze_ntee_codes USING gin(to_tsvector('english', description))"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_ntee_codes")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_ntee_codes
        (code, name, description, cause_type, parent_code,
         category, subcategory, code_source)
    VALUES
        (:code, :name, :description, :cause_type, :parent_code,
         :category, :subcategory, :code_source)
    ON CONFLICT (code) DO UPDATE SET
        name           = EXCLUDED.name,
        description    = EXCLUDED.description,
        parent_code    = EXCLUDED.parent_code,
        category       = EXCLUDED.category,
        subcategory    = EXCLUDED.subcategory,
        code_source    = EXCLUDED.code_source,
        ingestion_date = NOW()
    """
)


class NteeCodesPipeline(DataSourcePipeline[NteeCodesRow]):
    source = "ntee_codes"
    batch_size = 1_000
    row_schema = NteeCodesRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = resolve_source_path(self._path)
        rows = _read_rows(path)

        emitted = 0
        for row in rows:
            if self._limit is not None and emitted >= self._limit:
                return
            code = _safe_str(row.get("ntee_code"), 100)
            if not code:
                continue
            description = _safe_str(row.get("description"))
            parent_code = _safe_str(row.get("parent_code"), 100)
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": code,
                "code": code,
                "name": description or code,
                "description": description,
                "cause_type": "ntee",
                "parent_code": parent_code,
                "category": _safe_str(row.get("ntee_type"), 100),
                "subcategory": None,
                "code_source": "irs",
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[NteeCodesRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "code": r.code,
                "name": r.name,
                "description": r.description,
                "cause_type": r.cause_type,
                "parent_code": r.parent_code,
                "category": r.category,
                "subcategory": r.subcategory,
                "code_source": r.code_source,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_MIGRATE_SQL)
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load NTEE codes into bronze.bronze_ntee_codes"
    )
    parser.add_argument(
        "--file", type=Path,
        help="Source file (csv/parquet). Default: cache override or vendored seed CSV.",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = NteeCodesPipeline(path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

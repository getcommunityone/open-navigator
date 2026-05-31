#!/usr/bin/env python3
"""Load cached GivingTuesday 990 datamart CSVs into bronze.

Companion to ``ingestion.givingtuesday.download`` (which lands the curated
datamart CSVs in ``data/cache/giving_tuesday/``). This loads the two datamarts
that feed the nonprofit lineage:

    financials  ->  bronze.bronze_organizations_990_financials
                    (990CN120Fields: total revenue/expenses/assets, etc.)
    missions    ->  bronze.bronze_organizations_990_missions
                    (990Part1Missions: Part 1 mission statement text)

Each datamart holds one row per filing (i.e. multiple tax years per EIN); the
bronze tables preserve that grain with ``UNIQUE(ein, tax_year)``. Downstream dbt
staging (``stg_givingtuesday__*``) picks the latest filing per EIN before
joining into ``int_nonprofits_combined``.

The source CSVs are large (financials ~1.6 GB, missions ~1.1 GB), so rows are
read in chunks with only the needed columns projected, then batched-upserted via
the standard ``DataSourcePipeline`` contract.

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.

Usage:
    # 1. download first (see ingestion.givingtuesday.download)
    python -m ingestion.givingtuesday.download --match 990CN120Fields,Missions

    # 2. load into bronze
    python -m ingestion.givingtuesday.load --datamart all
    python -m ingestion.givingtuesday.load --datamart financials --truncate
    python -m ingestion.givingtuesday.load --datamart missions --file <path.csv> --limit 1000
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/giving_tuesday")
_CHUNK_ROWS = 100_000

# RawRow envelope fields that are not columns on the bronze tables.
_BASE_FIELDS = {"source", "source_version", "ingested_at", "natural_key"}


# --------------------------------------------------------------------------- #
# helpers (mirror ingestion.irs.bmf)
# --------------------------------------------------------------------------- #
def _safe_str(val: object, maxlen: int | None = None) -> str | None:
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    num = pd.to_numeric(val, errors="coerce")
    if pd.isna(num):
        return None
    return int(num)


def _ein(val: object) -> str | None:
    """Normalize EIN to 9 digits with leading zeros."""
    s = _safe_str(val)
    if s is None:
        return None
    s = s.replace("-", "")
    return s.zfill(9) if s.isdigit() else s


def _latest_cached(substr: str) -> Path:
    """Find the most recent cached datamart CSV whose name contains ``substr``."""
    files = sorted(CACHE_DIR.glob(f"*{substr}*.csv"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No cached datamart matching '*{substr}*.csv' in {CACHE_DIR}. "
            f"Download first: python -m ingestion.givingtuesday.download --match {substr}"
        )
    return files[0]


def _read_chunks(path: Path, columns: list[str]) -> AsyncIterator[dict]:
    """Yield row dicts from ``path``, projecting only the needed source columns."""
    header = pd.read_csv(path, dtype=str, nrows=0)
    present = [c for c in columns if c in header.columns]
    missing = set(columns) - set(present)
    if missing:
        raise ValueError(f"{path.name} missing expected columns: {sorted(missing)}")
    return pd.read_csv(path, dtype=str, usecols=present, chunksize=_CHUNK_ROWS)


# --------------------------------------------------------------------------- #
# financials datamart (990CN120Fields)
# --------------------------------------------------------------------------- #
class Form990FinancialsRow(RawRow):
    ein: str = Field(min_length=1, max_length=20)
    tax_year: int | None = None
    name: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    total_revenue: int | None = None
    total_expenses: int | None = None
    total_assets: int | None = None
    total_liabilities: int | None = None
    net_assets: int | None = None
    total_contributions: int | None = None
    program_service_revenue: int | None = None
    source_url: str | None = None


_FIN_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_990_financials (
        id SERIAL PRIMARY KEY,
        ein VARCHAR(20) NOT NULL,
        tax_year INTEGER,
        name TEXT,
        state_code VARCHAR(2),
        total_revenue BIGINT,
        total_expenses BIGINT,
        total_assets BIGINT,
        total_liabilities BIGINT,
        net_assets BIGINT,
        total_contributions BIGINT,
        program_service_revenue BIGINT,
        source_url TEXT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ein, tax_year)
    )
    """
)
_FIN_INDEXES = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990fin_ein ON bronze.bronze_organizations_990_financials(ein)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990fin_state ON bronze.bronze_organizations_990_financials(state_code)"),
)
_FIN_UPSERT = text(
    """
    INSERT INTO bronze.bronze_organizations_990_financials (
        ein, tax_year, name, state_code, total_revenue, total_expenses,
        total_assets, total_liabilities, net_assets, total_contributions,
        program_service_revenue, source_url
    ) VALUES (
        :ein, :tax_year, :name, :state_code, :total_revenue, :total_expenses,
        :total_assets, :total_liabilities, :net_assets, :total_contributions,
        :program_service_revenue, :source_url
    )
    ON CONFLICT (ein, tax_year) DO UPDATE SET
        name = EXCLUDED.name,
        state_code = EXCLUDED.state_code,
        total_revenue = EXCLUDED.total_revenue,
        total_expenses = EXCLUDED.total_expenses,
        total_assets = EXCLUDED.total_assets,
        total_liabilities = EXCLUDED.total_liabilities,
        net_assets = EXCLUDED.net_assets,
        total_contributions = EXCLUDED.total_contributions,
        program_service_revenue = EXCLUDED.program_service_revenue,
        source_url = EXCLUDED.source_url,
        loaded_at = CURRENT_TIMESTAMP
    """
)
# source CSV column -> meaning (see data_dictionary.xlsx "990 Basic Fields")
_FIN_SRC_COLS = [
    "FILEREIN", "TAXYEAR", "FILERNAME1", "FILERUSSTATE", "TOTREVCURYEA",
    "TOTEXPCURYEA", "TOASEOOYY", "TOLIEOOYY", "NAFBEOY", "TOTACASHCONT",
    "TOTPROSERREV", "URL",
]


class Form990FinancialsPipeline(DataSourcePipeline[Form990FinancialsRow]):
    source = "givingtuesday_990_financials"
    batch_size = 50_000
    row_schema = Form990FinancialsRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or _latest_cached("990CN120Fields")
        emitted = 0
        for chunk in _read_chunks(path, _FIN_SRC_COLS):
            for row in chunk.to_dict("records"):
                if self._limit is not None and emitted >= self._limit:
                    return
                ein = _ein(row.get("FILEREIN"))
                if not ein:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{ein}|{_safe_str(row.get('TAXYEAR')) or ''}",
                    "ein": ein,
                    "tax_year": _safe_int(row.get("TAXYEAR")),
                    "name": _safe_str(row.get("FILERNAME1")),
                    "state_code": _safe_str(row.get("FILERUSSTATE"), 2),
                    "total_revenue": _safe_int(row.get("TOTREVCURYEA")),
                    "total_expenses": _safe_int(row.get("TOTEXPCURYEA")),
                    "total_assets": _safe_int(row.get("TOASEOOYY")),
                    "total_liabilities": _safe_int(row.get("TOLIEOOYY")),
                    "net_assets": _safe_int(row.get("NAFBEOY")),
                    "total_contributions": _safe_int(row.get("TOTACASHCONT")),
                    "program_service_revenue": _safe_int(row.get("TOTPROSERREV")),
                    "source_url": _safe_str(row.get("URL")),
                }
                emitted += 1

    async def load_batch(self, session: AsyncSession, rows: list[Form990FinancialsRow], ctx: PipelineContext) -> None:
        await session.execute(_FIN_UPSERT, [r.model_dump(exclude=_BASE_FIELDS) for r in rows])


# --------------------------------------------------------------------------- #
# missions datamart (990Part1Missions)
# --------------------------------------------------------------------------- #
class Form990MissionRow(RawRow):
    ein: str = Field(min_length=1, max_length=20)
    tax_year: int | None = None
    name: str | None = None
    mission: str | None = None
    source_url: str | None = None


_MIS_DDL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_990_missions (
        id SERIAL PRIMARY KEY,
        ein VARCHAR(20) NOT NULL,
        tax_year INTEGER,
        name TEXT,
        mission TEXT,
        source_url TEXT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ein, tax_year)
    )
    """
)
_MIS_INDEXES = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_990mis_ein ON bronze.bronze_organizations_990_missions(ein)"),
)
_MIS_UPSERT = text(
    """
    INSERT INTO bronze.bronze_organizations_990_missions (
        ein, tax_year, name, mission, source_url
    ) VALUES (
        :ein, :tax_year, :name, :mission, :source_url
    )
    ON CONFLICT (ein, tax_year) DO UPDATE SET
        name = EXCLUDED.name,
        mission = EXCLUDED.mission,
        source_url = EXCLUDED.source_url,
        loaded_at = CURRENT_TIMESTAMP
    """
)
_MIS_SRC_COLS = ["FILEREIN", "TAXYEAR", "FILERNAME1", "MISSION", "URL"]


class Form990MissionPipeline(DataSourcePipeline[Form990MissionRow]):
    source = "givingtuesday_990_missions"
    batch_size = 50_000
    row_schema = Form990MissionRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or _latest_cached("990Part1Missions")
        emitted = 0
        for chunk in _read_chunks(path, _MIS_SRC_COLS):
            for row in chunk.to_dict("records"):
                if self._limit is not None and emitted >= self._limit:
                    return
                ein = _ein(row.get("FILEREIN"))
                if not ein:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{ein}|{_safe_str(row.get('TAXYEAR')) or ''}",
                    "ein": ein,
                    "tax_year": _safe_int(row.get("TAXYEAR")),
                    "name": _safe_str(row.get("FILERNAME1")),
                    "mission": _safe_str(row.get("MISSION")),
                    "source_url": _safe_str(row.get("URL")),
                }
                emitted += 1

    async def load_batch(self, session: AsyncSession, rows: list[Form990MissionRow], ctx: PipelineContext) -> None:
        await session.execute(_MIS_UPSERT, [r.model_dump(exclude=_BASE_FIELDS) for r in rows])


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
_DATAMARTS = {
    "financials": (Form990FinancialsPipeline, _FIN_DDL, _FIN_INDEXES,
                   "bronze.bronze_organizations_990_financials"),
    "missions": (Form990MissionPipeline, _MIS_DDL, _MIS_INDEXES,
                 "bronze.bronze_organizations_990_missions"),
}


async def _prepare_target(ddl, indexes, table: str, truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS bronze"))
        await session.execute(ddl)
        for idx in indexes:
            await session.execute(idx)
        if truncate:
            await session.execute(text(f"TRUNCATE TABLE {table}"))


async def _load_one(name: str, *, file: Path | None, limit: int | None, truncate: bool) -> None:
    pipeline_cls, ddl, indexes, table = _DATAMARTS[name]
    await _prepare_target(ddl, indexes, table, truncate)
    run = await pipeline_cls(path=file, limit=limit).run()
    from loguru import logger
    logger.success(
        f"{name}: loaded {run.loaded:,} rows into {table} "
        f"(extracted {run.extracted:,}, rejected {run.rejected:,})"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached GivingTuesday 990 datamarts into bronze",
    )
    parser.add_argument(
        "--datamart", choices=[*_DATAMARTS, "all"], default="all",
        help="Which datamart to load (default: all)",
    )
    parser.add_argument("--file", type=Path, help="Explicit CSV path (default: latest cached match)")
    parser.add_argument("--limit", type=int, help="Limit rows (for testing)")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    return parser


async def _run(args: argparse.Namespace) -> None:
    names = list(_DATAMARTS) if args.datamart == "all" else [args.datamart]
    for name in names:
        await _load_one(name, file=args.file, limit=args.limit, truncate=args.truncate)


def main() -> None:
    setup_logging()
    asyncio.run(_run(build_parser().parse_args()))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""HIFLD infrastructure locations pipeline: land cached parquet datasets into bronze (RAW).

Ported from load_hifld_to_postgres.py to the core_lib DataSourcePipeline
contract, then slimmed to ELT: this loader lands the RAW HIFLD records only.
The two transformations that used to live here in Python are now done
downstream in dbt (see dbt_project/CONVENTIONS.md):

  * Column-name normalization (the old FIELD_MAP / normalize_field_names) — HIFLD
    datasets use wildly inconsistent column names (NAME / FACNAME / SCHOOL_NAME,
    ADDRESS / STREET / LOCATION, LAT / Y, …). They are now preserved verbatim in
    the `raw_record` JSONB column and coalesced into canonical columns in
    stg_hifld__location.
  * organization_type classification (the old map_organization_type heuristic) —
    derived from `source_dataset` (and the raw TYPE field for law enforcement) via
    a CASE expression in stg_hifld__location.

HIFLD datasets (places of worship, schools, hospitals, emergency services,
government buildings, etc.) are cached as parquet files under data/cache/hifld/.
Each row becomes one bronze.bronze_locations record; every source field is kept
verbatim in `raw_record` JSONB.

Usage:
    python -m ingestion.hifld.locations
    python -m ingestion.hifld.locations --file data/cache/hifld/Hospitals.parquet

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded localhost:5433/open_navigator).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/hifld")

# Candidate raw column names (any case) that carry the source record id. The
# first one present is used to build the natural key; everything is also kept in
# raw_record so dbt can re-derive if needed.
_SOURCE_ID_CANDIDATES = ("FID", "ID", "OBJECTID", "FACILITY_ID")


def _read_parquet(path: Path) -> pd.DataFrame:
    """Read a HIFLD parquet, preferring geopandas if available + applicable."""
    try:
        import geopandas as gpd  # noqa: WPS433

        return gpd.read_parquet(path)
    except Exception:
        return pd.read_parquet(path)


def _truncate(val: Any, maxlen: int) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val)
    if not s or s.upper() == "NOT AVAILABLE":
        return None
    return s[:maxlen]


def _jsonable(val: Any) -> Any:
    """Coerce a single parquet cell into a JSON-serializable value (or None)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, pd.Timestamp):
        return str(val)
    return val


def _raw_source_id(row_dict: dict[str, Any]) -> str | None:
    """Pull the first available source-id candidate from the raw row (case-insensitive)."""
    upper = {str(k).upper(): v for k, v in row_dict.items()}
    for cand in _SOURCE_ID_CANDIDATES:
        if cand in upper:
            sid = _truncate(upper[cand], 100)
            if sid:
                return sid
    return None


class LocationRow(RawRow):
    """One RAW HIFLD infrastructure location, validated before insert.

    No derivation here: organization_type and the canonical name/address/state/…
    columns are computed downstream in stg_hifld__location. We land the
    originating dataset, a best-effort source id, and the full raw record.
    """

    source_id: str | None = Field(default=None, max_length=100)
    source_dataset: str = Field(min_length=1, max_length=200)
    raw_record: dict[str, Any] = Field(min_length=1)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")
_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_locations (
        id SERIAL PRIMARY KEY,
        source_id VARCHAR(100),
        source_dataset VARCHAR(200) NOT NULL,
        data_source VARCHAR(100) DEFAULT 'HIFLD',
        raw_record JSONB NOT NULL,
        loaded_at TIMESTAMP DEFAULT NOW(),
        CONSTRAINT uq_bronze_locations_source UNIQUE (source_dataset, source_id)
    )
    """
)
_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bronzeloc_source ON bronze.bronze_locations(source_dataset)"),
)
_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_locations (
        source_id, source_dataset, raw_record
    )
    VALUES (
        :source_id, :source_dataset, CAST(:raw_record AS jsonb)
    )
    ON CONFLICT ON CONSTRAINT uq_bronze_locations_source DO NOTHING
    """
)


class HifldLocationsPipeline(DataSourcePipeline[LocationRow]):
    source = "hifld"
    batch_size = 1_000
    row_schema = LocationRow

    def __init__(self, *, parquet_file: Path | None = None):
        self._parquet_file = parquet_file

    def _discover_files(self) -> list[Path]:
        if self._parquet_file is not None:
            if not self._parquet_file.exists():
                raise FileNotFoundError(f"File not found: {self._parquet_file}")
            return [self._parquet_file]
        if not CACHE_DIR.exists():
            raise FileNotFoundError(f"HIFLD cache dir not found: {CACHE_DIR}")
        files = sorted(CACHE_DIR.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"No parquet files in {CACHE_DIR}")
        return files

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        for parquet_file in self._discover_files():
            df = _read_parquet(parquet_file)
            if "geometry" in df.columns:
                df = df.drop(columns=["geometry"])
            dataset_name = parquet_file.stem
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                # Preserve every source field verbatim; coercion to canonical
                # columns + org_type classification happens in dbt.
                raw_record = {
                    str(k): _jsonable(v)
                    for k, v in row_dict.items()
                    if _jsonable(v) is not None
                }
                if not raw_record:
                    continue
                source_id = _raw_source_id(row_dict)
                yield {
                    "source": self.source,
                    "source_version": dataset_name,
                    "natural_key": f"{dataset_name}:{source_id or ''}",
                    "source_id": source_id,
                    "source_dataset": dataset_name,
                    "raw_record": raw_record,
                }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[LocationRow],
        ctx: PipelineContext,
    ) -> None:
        params = []
        for r in rows:
            params.append(
                {
                    "source_id": r.source_id,
                    "source_dataset": r.source_dataset,
                    "raw_record": json.dumps(r.raw_record),
                }
            )
        await session.execute(_INSERT_SQL, params)


async def _prepare_target() -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Land HIFLD infrastructure parquet datasets (RAW) into bronze.bronze_locations"
    )
    parser.add_argument("--file", type=Path, help="Specific parquet file (default: all in cache)")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target()
    pipeline = HifldLocationsPipeline(parquet_file=args.file)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

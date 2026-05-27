#!/usr/bin/env python3
"""NCCS Unified BMF pipeline: load cached CSV into bronze NCCS tables.

Ported from load_nccs_bulk.py to the core_lib DataSourcePipeline contract.

Data source: NCCS (National Center for Charitable Statistics) Unified BMF
(Business Master File), downloaded by scripts/datasources/nccs/download_nccs_bulk.py
into data/cache/nccs/unified-bmf/v1.2/ (a full file plus per-state shards).

Lands the raw history table only:
  * bronze.bronze_organizations_nonprofits_nccs_history  (all versions,
    UNIQUE(ein, org_year_last))

The "current / most-recent per EIN" view is derived downstream in dbt
(int_nccs__current_orgs), not computed in Python — see dbt_project/CONVENTIONS.md.

Usage:
    python -m scripts.datasources.nccs.bulk_pipeline
    python scripts/datasources/nccs/bulk_pipeline.py --truncate
    python scripts/datasources/nccs/bulk_pipeline.py --base-dir /mnt/d/nccs_data
    python scripts/datasources/nccs/bulk_pipeline.py --states CA,NY,TX --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.utils.calendar_year_util import calendar_year_label  # noqa: E402


BASE_DIR = Path("data/cache/nccs")

# Ordered list of bronze columns shared by both target tables.
COLUMNS = [
    "ein2", "ein", "ntee_irs", "ntee_nccs", "nteev2",
    "nccs_level_1", "nccs_level_2", "nccs_level_3",
    "f990_org_addr_city", "f990_org_addr_state", "f990_org_addr_zip", "f990_org_addr_street",
    "census_cbsa_fips", "census_cbsa_name", "census_block_fips", "census_urban_area",
    "census_state_abbr", "census_county_name", "org_addr_full", "org_addr_match",
    "latitude", "longitude", "geocoder_score", "geocoder_match",
    "bmf_subsection_code", "bmf_status_code", "bmf_pf_filing_req_code", "bmf_organization_code",
    "bmf_income_code", "bmf_group_exempt_num", "bmf_foundation_code", "bmf_filing_req_code",
    "bmf_deductibility_code", "bmf_classification_code", "bmf_asset_code", "bmf_affiliation_code",
    "org_ruling_date", "org_fiscal_year", "org_ruling_year", "org_year_first", "org_year_last",
    "org_year_count", "org_pers_ico", "org_name_sec", "org_name_current", "org_fiscal_period",
    "f990_total_revenue_recent", "f990_total_income_recent",
    "f990_total_assets_recent", "f990_total_expenses_recent",
]

# Calendar-year columns normalized to VARCHAR(4) via calendar_year_label.
_YEAR_COLUMNS = ("org_fiscal_year", "org_ruling_year", "org_year_first", "org_year_last")
# Integer columns (INTEGER / BIGINT).
_INT_COLUMNS = (
    "org_year_count",
    "f990_total_revenue_recent", "f990_total_income_recent",
    "f990_total_assets_recent", "f990_total_expenses_recent",
)
# Float columns (DOUBLE PRECISION).
_FLOAT_COLUMNS = ("latitude", "longitude", "geocoder_score")


def find_full_file(base_dir: Path) -> Path:
    """Return the path to the full Unified BMF CSV, raising if absent."""
    path = base_dir / "unified-bmf" / "v1.2" / "full" / "UNIFIED_BMF_V1.2.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"NCCS full file not found: {path}. Run download_nccs_bulk.py first."
        )
    return path


def find_state_files(base_dir: Path, states: list[str]) -> list[Path]:
    """Return the per-state CSV paths that exist for the requested states."""
    by_state = base_dir / "unified-bmf" / "v1.2" / "by-state"
    files: list[Path] = []
    for state in states:
        path = by_state / f"{state.strip().upper()}.csv"
        if path.exists():
            files.append(path)
    if not files:
        raise FileNotFoundError(
            f"No NCCS state files found in {by_state} for states={states}."
        )
    return files


def _clean_str(val: str | None) -> str | None:
    """Trim a raw CSV value; empty / NA-like strings become None."""
    if val is None:
        return None
    s = val.strip()
    if not s or s.lower() in ("nan", "none", "nat", "<na>"):
        return None
    return s


def _clean_int(val: str | None) -> int | None:
    s = _clean_str(val)
    if s is None:
        return None
    try:
        return int(float(s))
    except (ValueError, OverflowError):
        return None


def _clean_float(val: str | None) -> float | None:
    s = _clean_str(val)
    if s is None:
        return None
    try:
        return float(s)
    except (ValueError, OverflowError):
        return None


def clean_record(raw: dict) -> dict:
    """Normalize one raw CSV record (lowercased keys) into typed column values."""
    out: dict = {}
    for col in COLUMNS:
        val = raw.get(col)
        if col in _YEAR_COLUMNS:
            out[col] = calendar_year_label(val)
        elif col in _INT_COLUMNS:
            out[col] = _clean_int(val)
        elif col in _FLOAT_COLUMNS:
            out[col] = _clean_float(val)
        else:
            out[col] = _clean_str(val)
    return out


class NccsBulkRow(RawRow):
    """One NCCS Unified BMF organization row, validated before upsert."""

    ein2: str | None = Field(default=None, max_length=20)
    ein: str = Field(min_length=1, max_length=20)
    ntee_irs: str | None = Field(default=None, max_length=20)
    ntee_nccs: str | None = Field(default=None, max_length=20)
    nteev2: str | None = Field(default=None, max_length=20)
    nccs_level_1: str | None = Field(default=None, max_length=100)
    nccs_level_2: str | None = Field(default=None, max_length=100)
    nccs_level_3: str | None = Field(default=None, max_length=100)
    f990_org_addr_city: str | None = Field(default=None, max_length=100)
    f990_org_addr_state: str | None = Field(default=None, max_length=2)
    f990_org_addr_zip: str | None = Field(default=None, max_length=20)
    f990_org_addr_street: str | None = Field(default=None, max_length=255)
    census_cbsa_fips: str | None = Field(default=None, max_length=20)
    census_cbsa_name: str | None = Field(default=None, max_length=200)
    census_block_fips: str | None = Field(default=None, max_length=20)
    census_urban_area: str | None = Field(default=None, max_length=200)
    census_state_abbr: str | None = Field(default=None, max_length=2)
    census_county_name: str | None = Field(default=None, max_length=100)
    org_addr_full: str | None = None
    org_addr_match: str | None = Field(default=None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    geocoder_score: float | None = None
    geocoder_match: str | None = Field(default=None, max_length=100)
    bmf_subsection_code: str | None = Field(default=None, max_length=20)
    bmf_status_code: str | None = Field(default=None, max_length=20)
    bmf_pf_filing_req_code: str | None = Field(default=None, max_length=20)
    bmf_organization_code: str | None = Field(default=None, max_length=20)
    bmf_income_code: str | None = Field(default=None, max_length=20)
    bmf_group_exempt_num: str | None = Field(default=None, max_length=20)
    bmf_foundation_code: str | None = Field(default=None, max_length=20)
    bmf_filing_req_code: str | None = Field(default=None, max_length=20)
    bmf_deductibility_code: str | None = Field(default=None, max_length=20)
    bmf_classification_code: str | None = Field(default=None, max_length=20)
    bmf_asset_code: str | None = Field(default=None, max_length=20)
    bmf_affiliation_code: str | None = Field(default=None, max_length=20)
    org_ruling_date: str | None = Field(default=None, max_length=20)
    org_fiscal_year: str | None = Field(default=None, max_length=4)
    org_ruling_year: str | None = Field(default=None, max_length=4)
    org_year_first: str | None = Field(default=None, max_length=4)
    org_year_last: str | None = Field(default=None, max_length=4)
    org_year_count: int | None = None
    org_pers_ico: str | None = None
    org_name_sec: str | None = None
    org_name_current: str | None = None
    org_fiscal_period: str | None = Field(default=None, max_length=20)
    f990_total_revenue_recent: int | None = None
    f990_total_income_recent: int | None = None
    f990_total_assets_recent: int | None = None
    f990_total_expenses_recent: int | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_HISTORY_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_nonprofits_nccs_history (
        id SERIAL PRIMARY KEY,
        ein2 VARCHAR(20),
        ein VARCHAR(20) NOT NULL,
        ntee_irs VARCHAR(20),
        ntee_nccs VARCHAR(20),
        nteev2 VARCHAR(20),
        nccs_level_1 VARCHAR(100),
        nccs_level_2 VARCHAR(100),
        nccs_level_3 VARCHAR(100),
        f990_org_addr_city VARCHAR(100),
        f990_org_addr_state VARCHAR(2),
        f990_org_addr_zip VARCHAR(20),
        f990_org_addr_street VARCHAR(255),
        census_cbsa_fips VARCHAR(20),
        census_cbsa_name VARCHAR(200),
        census_block_fips VARCHAR(20),
        census_urban_area VARCHAR(200),
        census_state_abbr VARCHAR(2),
        census_county_name VARCHAR(100),
        org_addr_full TEXT,
        org_addr_match VARCHAR(200),
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        geocoder_score DOUBLE PRECISION,
        geocoder_match VARCHAR(100),
        bmf_subsection_code VARCHAR(20),
        bmf_status_code VARCHAR(20),
        bmf_pf_filing_req_code VARCHAR(20),
        bmf_organization_code VARCHAR(20),
        bmf_income_code VARCHAR(20),
        bmf_group_exempt_num VARCHAR(20),
        bmf_foundation_code VARCHAR(20),
        bmf_filing_req_code VARCHAR(20),
        bmf_deductibility_code VARCHAR(20),
        bmf_classification_code VARCHAR(20),
        bmf_asset_code VARCHAR(20),
        bmf_affiliation_code VARCHAR(20),
        org_ruling_date VARCHAR(20),
        org_fiscal_year VARCHAR(4),
        org_ruling_year VARCHAR(4),
        org_year_first VARCHAR(4),
        org_year_last VARCHAR(4),
        org_year_count INTEGER,
        org_pers_ico TEXT,
        org_name_sec TEXT,
        org_name_current TEXT,
        org_fiscal_period VARCHAR(20),
        f990_total_revenue_recent BIGINT,
        f990_total_income_recent BIGINT,
        f990_total_assets_recent BIGINT,
        f990_total_expenses_recent BIGINT,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ein, org_year_last)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_ein ON bronze.bronze_organizations_nonprofits_nccs_history(ein)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_year ON bronze.bronze_organizations_nonprofits_nccs_history(org_year_last)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_state ON bronze.bronze_organizations_nonprofits_nccs_history(f990_org_addr_state)"),
)

_TRUNCATE_HISTORY_SQL = text("TRUNCATE TABLE bronze.bronze_organizations_nonprofits_nccs_history")

_INSERT_COLUMNS = ", ".join(COLUMNS)
_INSERT_PLACEHOLDERS = ", ".join(f":{c}" for c in COLUMNS)

_UPSERT_HISTORY_SQL = text(
    f"""
    INSERT INTO bronze.bronze_organizations_nonprofits_nccs_history
        ({_INSERT_COLUMNS})
    VALUES
        ({_INSERT_PLACEHOLDERS})
    ON CONFLICT (ein, org_year_last) DO UPDATE SET
        org_name_current = EXCLUDED.org_name_current,
        f990_total_revenue_recent = EXCLUDED.f990_total_revenue_recent,
        f990_total_assets_recent = EXCLUDED.f990_total_assets_recent,
        loaded_at = CURRENT_TIMESTAMP
    """
)

class NccsBulkPipeline(DataSourcePipeline[NccsBulkRow]):
    source = "nccs_bulk"
    batch_size = 5_000
    row_schema = NccsBulkRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        base_dir: Path | None = None,
        states: list[str] | None = None,
        limit: int | None = None,
    ):
        self._path = path
        self._base_dir = base_dir or BASE_DIR
        self._states = states
        self._limit = limit

    def _discover_files(self) -> list[Path]:
        if self._path is not None:
            return [self._path]
        if self._states:
            return find_state_files(self._base_dir, self._states)
        return [find_full_file(self._base_dir)]

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        emitted = 0
        for path in self._discover_files():
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                reader.fieldnames = [
                    (h or "").strip().lower() for h in (reader.fieldnames or [])
                ]
                for raw in reader:
                    if self._limit is not None and emitted >= self._limit:
                        return
                    record = clean_record(raw)
                    ein = record.get("ein")
                    if not ein:
                        continue
                    yield {
                        "source": self.source,
                        "source_version": "unified-bmf-v1.2",
                        "natural_key": f"{ein}:{record.get('org_year_last') or ''}",
                        **record,
                    }
                    emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[NccsBulkRow],
        ctx: PipelineContext,
    ) -> None:
        # Land every version into history (deduped on (ein, org_year_last)).
        # The "current / most-recent per EIN" view is derived downstream in dbt
        # (int_nccs__current_orgs), not computed in Python here.
        history_params = [{c: getattr(r, c) for c in COLUMNS} for r in rows]
        await session.execute(_UPSERT_HISTORY_SQL, history_params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_HISTORY_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_HISTORY_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load NCCS Unified BMF CSV into bronze NCCS tables"
    )
    parser.add_argument(
        "--base-dir", type=Path, default=BASE_DIR,
        help="Base directory where NCCS data was downloaded (default: data/cache/nccs)",
    )
    parser.add_argument(
        "--states", type=str,
        help="Comma-separated state codes to load (e.g., CA,NY,TX); omit to load full file",
    )
    parser.add_argument("--limit", type=int, help="Load only the first N data rows")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE tables before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    states = [s for s in args.states.split(",")] if args.states else None
    pipeline = NccsBulkPipeline(base_dir=args.base_dir, states=states, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

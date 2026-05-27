#!/usr/bin/env python3
"""IRS Business Master File (EO-BMF) pipeline: load cached BMF extract into
bronze.bronze_organizations_nonprofits_irs.

Ported from load_irs_bmf.py to the core_lib DataSourcePipeline contract.

Data source: IRS Exempt Organizations Business Master File Extract (EO-BMF),
https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
Regional CSV files (eo1.csv .. eo4.csv) are downloaded and cached as parquet under
data/cache/irs_bmf/ (e.g. all_regions_combined.parquet, region*.parquet,
state_*.parquet). This provides all 1.9M+ U.S. tax-exempt organizations.

Usage:
    python -m ingestion.irs.bmf
    python -m ingestion.irs.bmf --truncate
    python -m ingestion.irs.bmf \\
        --file data/cache/irs_bmf/all_regions_combined.parquet --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
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


CACHE_DIR = Path("data/cache/irs_bmf")


def find_latest_parquet() -> Path:
    """Locate the most recent cached IRS BMF parquet extract.

    Prefers the combined all-regions file, then any cached parquet by recency.
    """
    combined = CACHE_DIR / "all_regions_combined.parquet"
    if combined.exists():
        return combined
    files = sorted(CACHE_DIR.glob("*.parquet"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No cached IRS BMF parquet found in {CACHE_DIR}. "
            "Download from "
            "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf "
            "first."
        )
    return files[0]


def _safe_str(val: object, maxlen: int | None = None) -> str | None:
    """Normalize a cell to a stripped string, or None when empty/NA."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _safe_int(val: object) -> int | None:
    """Convert a financial amount cell to a nullable integer (BIGINT).

    Mirrors the original pandas pd.to_numeric(..., errors='coerce').astype('Int64')
    behaviour: non-numeric / missing values become NULL.
    """
    if val is None:
        return None
    num = pd.to_numeric(val, errors="coerce")
    if pd.isna(num):
        return None
    return int(num)


class IrsBmfRow(RawRow):
    """One IRS EO-BMF organization row, validated before upsert."""

    ein: str = Field(min_length=1, max_length=20)
    name: str | None = None
    ico: str | None = Field(default=None, max_length=100)
    street: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state_code: str | None = Field(default=None, max_length=2)
    zip_code: str | None = Field(default=None, max_length=20)
    group_exemption: str | None = Field(default=None, max_length=20)
    subsection: str | None = Field(default=None, max_length=20)
    affiliation: str | None = Field(default=None, max_length=20)
    classification: str | None = Field(default=None, max_length=20)
    ruling: str | None = Field(default=None, max_length=20)
    deductibility: str | None = Field(default=None, max_length=50)
    foundation: str | None = Field(default=None, max_length=20)
    activity: str | None = Field(default=None, max_length=200)
    organization: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=20)
    tax_period: str | None = Field(default=None, max_length=20)
    asset_cd: str | None = Field(default=None, max_length=20)
    income_cd: str | None = Field(default=None, max_length=20)
    filing_req_cd: str | None = Field(default=None, max_length=20)
    pf_filing_req_cd: str | None = Field(default=None, max_length=20)
    acct_pd: str | None = Field(default=None, max_length=20)
    asset_amt: int | None = None
    income_amt: int | None = None
    revenue_amt: int | None = None
    ntee_cd: str | None = Field(default=None, max_length=20)
    sort_name: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=20)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_nonprofits_irs (
        id SERIAL PRIMARY KEY,
        ein VARCHAR(20) NOT NULL,
        name TEXT,
        ico VARCHAR(100),
        street VARCHAR(255),
        city VARCHAR(100),
        state_code VARCHAR(2),
        zip_code VARCHAR(20),
        group_exemption VARCHAR(20),
        subsection VARCHAR(20),
        affiliation VARCHAR(20),
        classification VARCHAR(20),
        ruling VARCHAR(20),
        deductibility VARCHAR(50),
        foundation VARCHAR(20),
        activity VARCHAR(200),
        organization VARCHAR(20),
        status VARCHAR(20),
        tax_period VARCHAR(20),
        asset_cd VARCHAR(20),
        income_cd VARCHAR(20),
        filing_req_cd VARCHAR(20),
        pf_filing_req_cd VARCHAR(20),
        acct_pd VARCHAR(20),
        asset_amt BIGINT,
        income_amt BIGINT,
        revenue_amt BIGINT,
        ntee_cd VARCHAR(20),
        sort_name VARCHAR(255),
        country VARCHAR(20),
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        UNIQUE(ein)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bronze_irs_state "
        "ON bronze.bronze_organizations_nonprofits_irs(state_code)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bronze_irs_city  "
        "ON bronze.bronze_organizations_nonprofits_irs(city, state_code)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bronze_irs_ntee  "
        "ON bronze.bronze_organizations_nonprofits_irs(ntee_cd)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bronze_irs_name  "
        "ON bronze.bronze_organizations_nonprofits_irs "
        "USING gin(to_tsvector('english', name))"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_organizations_nonprofits_irs")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_organizations_nonprofits_irs (
        ein, name, ico, street, city, state_code, zip_code,
        group_exemption, subsection, affiliation, classification,
        ruling, deductibility, foundation, activity, organization,
        status, tax_period, asset_cd, income_cd, filing_req_cd,
        pf_filing_req_cd, acct_pd, asset_amt, income_amt, revenue_amt,
        ntee_cd, sort_name, country
    ) VALUES (
        :ein, :name, :ico, :street, :city, :state_code, :zip_code,
        :group_exemption, :subsection, :affiliation, :classification,
        :ruling, :deductibility, :foundation, :activity, :organization,
        :status, :tax_period, :asset_cd, :income_cd, :filing_req_cd,
        :pf_filing_req_cd, :acct_pd, :asset_amt, :income_amt, :revenue_amt,
        :ntee_cd, :sort_name, :country
    )
    ON CONFLICT (ein) DO UPDATE SET
        name = EXCLUDED.name,
        city = EXCLUDED.city,
        state_code = EXCLUDED.state_code,
        ntee_cd = EXCLUDED.ntee_cd,
        asset_amt = EXCLUDED.asset_amt,
        income_amt = EXCLUDED.income_amt,
        revenue_amt = EXCLUDED.revenue_amt,
        loaded_at = CURRENT_TIMESTAMP
    """
)


def _read_frame(path: Path) -> pd.DataFrame:
    """Load the cached IRS BMF extract as a DataFrame with lower-cased columns."""
    if path.suffix == ".csv":
        df = pd.read_csv(path, dtype=str)
    else:
        df = pd.read_parquet(path)
    df.columns = df.columns.str.lower()
    return df


class IrsBmfPipeline(DataSourcePipeline[IrsBmfRow]):
    source = "irs_bmf"
    batch_size = 50_000
    row_schema = IrsBmfRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or find_latest_parquet()
        df = _read_frame(path)
        emitted = 0
        for row in df.to_dict("records"):
            if self._limit is not None and emitted >= self._limit:
                return
            ein = _safe_str(row.get("ein"), 20)
            if not ein:
                continue
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": ein,
                "ein": ein,
                "name": _safe_str(row.get("name")),
                "ico": _safe_str(row.get("ico"), 100),
                "street": _safe_str(row.get("street"), 255),
                "city": _safe_str(row.get("city"), 100),
                "state_code": _safe_str(row.get("state"), 2),
                "zip_code": _safe_str(row.get("zip"), 20),
                "group_exemption": _safe_str(row.get("group"), 20),
                "subsection": _safe_str(row.get("subsection"), 20),
                "affiliation": _safe_str(row.get("affiliation"), 20),
                "classification": _safe_str(row.get("classification"), 20),
                "ruling": _safe_str(row.get("ruling"), 20),
                "deductibility": _safe_str(row.get("deductibility"), 50),
                "foundation": _safe_str(row.get("foundation"), 20),
                "activity": _safe_str(row.get("activity"), 200),
                "organization": _safe_str(row.get("organization"), 20),
                "status": _safe_str(row.get("status"), 20),
                "tax_period": _safe_str(row.get("tax_period"), 20),
                "asset_cd": _safe_str(row.get("asset_cd"), 20),
                "income_cd": _safe_str(row.get("income_cd"), 20),
                "filing_req_cd": _safe_str(row.get("filing_req_cd"), 20),
                "pf_filing_req_cd": _safe_str(row.get("pf_filing_req_cd"), 20),
                "acct_pd": _safe_str(row.get("acct_pd"), 20),
                "asset_amt": _safe_int(row.get("asset_amt")),
                "income_amt": _safe_int(row.get("income_amt")),
                "revenue_amt": _safe_int(row.get("revenue_amt")),
                "ntee_cd": _safe_str(row.get("ntee_cd"), 20),
                "sort_name": _safe_str(row.get("sort_name"), 255),
                "country": _safe_str(row.get("country"), 20),
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[IrsBmfRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "ein": r.ein,
                "name": r.name,
                "ico": r.ico,
                "street": r.street,
                "city": r.city,
                "state_code": r.state_code,
                "zip_code": r.zip_code,
                "group_exemption": r.group_exemption,
                "subsection": r.subsection,
                "affiliation": r.affiliation,
                "classification": r.classification,
                "ruling": r.ruling,
                "deductibility": r.deductibility,
                "foundation": r.foundation,
                "activity": r.activity,
                "organization": r.organization,
                "status": r.status,
                "tax_period": r.tax_period,
                "asset_cd": r.asset_cd,
                "income_cd": r.income_cd,
                "filing_req_cd": r.filing_req_cd,
                "pf_filing_req_cd": r.pf_filing_req_cd,
                "acct_pd": r.acct_pd,
                "asset_amt": r.asset_amt,
                "income_amt": r.income_amt,
                "revenue_amt": r.revenue_amt,
                "ntee_cd": r.ntee_cd,
                "sort_name": r.sort_name,
                "country": r.country,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


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
        description=(
            "Load cached IRS EO-BMF extract into "
            "bronze.bronze_organizations_nonprofits_irs"
        )
    )
    parser.add_argument(
        "--file", type=Path,
        help="Path to cached parquet/csv (default: latest in data/cache/irs_bmf/)",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = IrsBmfPipeline(path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

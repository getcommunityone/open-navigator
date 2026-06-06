#!/usr/bin/env python3
"""HUD ZIP-to-County crosswalk pipeline: load cached xlsx into
bronze.bronze_jurisdictions_zip_county.

Ported from load_zip_county.py to the core_lib DataSourcePipeline contract.

Data source: HUD USPS ZIP Code Crosswalk Files (quarterly),
https://www.huduser.gov/portal/datasets/usps_crosswalk.html, cached at
data/cache/hud/ZIP_COUNTY_<MMYYYY>.xlsx.

Usage:
    python -m ingestion.hud.zip_county
    python -m ingestion.hud.zip_county --truncate
    python -m ingestion.hud.zip_county \\
        --file data/cache/hud/ZIP_COUNTY_122025.xlsx --limit 500

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/hud")
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def find_latest_xlsx() -> Path:
    files = sorted(CACHE_DIR.glob("ZIP_COUNTY_*.xlsx"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No HUD ZIP_COUNTY xlsx found in {CACHE_DIR}. "
            "Download from https://www.huduser.gov/portal/datasets/usps_crosswalk.html"
        )
    return files[0]


def _safe_decimal(val: str | None) -> Decimal | None:
    if val is None or val.strip() == "":
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return None


def _safe_str(val: str | None, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = val.strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def parse_xlsx(path: Path, limit: int | None = None) -> list[dict]:
    """Parse the HUD crosswalk xlsx into normalized field dicts (no envelope)."""
    with zipfile.ZipFile(path) as z:
        shared = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = [si.find(".//s:t", NS).text for si in shared.findall("s:si", NS)]
        ws = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    def cell_value(c):
        t = c.get("t")
        v = c.find("s:v", NS)
        if v is None:
            return None
        return strings[int(v.text)] if t == "s" else v.text

    data_rows = ws.findall(".//s:row", NS)[1:]  # skip header
    if limit is not None:
        data_rows = data_rows[:limit]

    records: list[dict] = []
    for row in data_rows:
        cells = [cell_value(c) for c in row.findall("s:c", NS)]
        while len(cells) < 8:
            cells.append(None)
        zip_code = _safe_str(cells[0], 5)
        county = _safe_str(cells[1], 5)
        if not zip_code or not county:
            continue
        records.append({
            "zip": zip_code,
            "county": county,
            "usps_zip_pref_city": _safe_str(cells[2], 100),
            "usps_zip_pref_state": _safe_str(cells[3], 2),
            "res_ratio": _safe_decimal(cells[4]),
            "bus_ratio": _safe_decimal(cells[5]),
            "oth_ratio": _safe_decimal(cells[6]),
            "tot_ratio": _safe_decimal(cells[7]),
        })
    return records


class ZipCountyRow(RawRow):
    """One HUD ZIP-county crosswalk row, validated before upsert."""

    zip: str = Field(min_length=1, max_length=5)
    county: str = Field(min_length=1, max_length=5)
    usps_zip_pref_city: str | None = Field(default=None, max_length=100)
    usps_zip_pref_state: str | None = Field(default=None, max_length=2)
    res_ratio: Decimal | None = None
    bus_ratio: Decimal | None = None
    oth_ratio: Decimal | None = None
    tot_ratio: Decimal | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_zip_county (
        zip                  CHAR(5)        NOT NULL,
        county               CHAR(5)        NOT NULL,
        usps_zip_pref_city   VARCHAR(100),
        usps_zip_pref_state  CHAR(2),
        res_ratio            NUMERIC(20, 17),
        bus_ratio            NUMERIC(20, 17),
        oth_ratio            NUMERIC(20, 17),
        tot_ratio            NUMERIC(20, 17),
        ingestion_date       TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (zip, county)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bzc_zip    ON bronze.bronze_jurisdictions_zip_county(zip)"),
    text("CREATE INDEX IF NOT EXISTS idx_bzc_county ON bronze.bronze_jurisdictions_zip_county(county)"),
    text("CREATE INDEX IF NOT EXISTS idx_bzc_state  ON bronze.bronze_jurisdictions_zip_county(usps_zip_pref_state)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_jurisdictions_zip_county")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_jurisdictions_zip_county
        (zip, county, usps_zip_pref_city, usps_zip_pref_state,
         res_ratio, bus_ratio, oth_ratio, tot_ratio)
    VALUES
        (:zip, :county, :usps_zip_pref_city, :usps_zip_pref_state,
         :res_ratio, :bus_ratio, :oth_ratio, :tot_ratio)
    ON CONFLICT (zip, county) DO UPDATE SET
        usps_zip_pref_city  = EXCLUDED.usps_zip_pref_city,
        usps_zip_pref_state = EXCLUDED.usps_zip_pref_state,
        res_ratio           = EXCLUDED.res_ratio,
        bus_ratio           = EXCLUDED.bus_ratio,
        oth_ratio           = EXCLUDED.oth_ratio,
        tot_ratio           = EXCLUDED.tot_ratio,
        ingestion_date      = NOW()
    """
)


class HudZipCountyPipeline(DataSourcePipeline[ZipCountyRow]):
    source = "hud_zip_county"
    batch_size = 2_000
    row_schema = ZipCountyRow

    def __init__(
        self,
        *,
        xlsx_path: Path | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ):
        self._xlsx_path = xlsx_path
        self._limit = limit
        self._dry_run = dry_run

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._xlsx_path or find_latest_xlsx()
        for rec in parse_xlsx(path, limit=self._limit):
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": f"{rec['zip']}:{rec['county']}",
                **rec,
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[ZipCountyRow],
        ctx: PipelineContext,
    ) -> None:
        if self._dry_run:
            return
        params = [
            {
                "zip": r.zip,
                "county": r.county,
                "usps_zip_pref_city": r.usps_zip_pref_city,
                "usps_zip_pref_state": r.usps_zip_pref_state,
                "res_ratio": r.res_ratio,
                "bus_ratio": r.bus_ratio,
                "oth_ratio": r.oth_ratio,
                "tot_ratio": r.tot_ratio,
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
        description="Load HUD ZIP-to-County crosswalk into bronze.bronze_jurisdictions_zip_county"
    )
    parser.add_argument("--file", type=Path, help="Path to xlsx (default: latest in data/cache/hud/)")
    parser.add_argument("--limit", type=int, help="Load only the first N data rows")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and validate rows but do not touch the database",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    if not args.dry_run:
        await _prepare_target(args.truncate)
    pipeline = HudZipCountyPipeline(
        xlsx_path=args.file, limit=args.limit, dry_run=args.dry_run
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

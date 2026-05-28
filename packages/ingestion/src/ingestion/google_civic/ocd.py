#!/usr/bin/env python3
"""OpenCivicData jurisdictions pipeline: load cached identifier CSVs into
bronze.bronze_jurisdiction_ocd.

Ported from load_ocd_into_postgres.py to the core_lib DataSourcePipeline
contract.

Data source: OpenCivicData identifiers (opencivicdata/ocd-division-ids),
cached at data/cache/opencivicdata/identifiers/:
  - country-us.csv               (counties / places / school districts)
  - country-us/state-*-local_gov.csv  (places / counties / council districts / wards)

Usage:
    python -m ingestion.google_civic.ocd
    python -m ingestion.google_civic.ocd --truncate
    python -m ingestion.google_civic.ocd \\
        --path data/cache/opencivicdata --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 connect on a passed --database-url).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/opencivicdata")

_STATES = "ALABAMAALASKAARUZONAARKANSASCALIFORNIACOLORADOCONNECTICUTDELAWAREFLORIAGEORGIAHAWAIIIDAHOIS" \
          "LLINOISINDIANAIOWACAN"


def find_cache_dir() -> Path:
    """Return the OCD cache dir, raising if it is missing."""
    if not CACHE_DIR.exists():
        raise FileNotFoundError(
            f"OCD cache not found at {CACHE_DIR}. "
            "Run the OpenCivicData download step first."
        )
    return CACHE_DIR


def parse_country_row(ocd_id: str, name: str) -> dict | None:
    """Parse a country-us.csv (ocd_id, name) pair into a normalized field dict.

    Returns None for rows that should be skipped. Logic preserved verbatim from
    the original loader.
    """
    if not ocd_id or not name:
        return None

    # Extract state code
    if "state:" not in ocd_id:
        return None

    # Parse OCD ID to extract components
    state_code = None
    jtype = None
    parent_ocd = None

    for part in ocd_id.split("/"):
        if "state:" in part:
            state_code = part.split(":")[1].upper()
        elif "county:" in part:
            jtype = "county"
        elif "place:" in part:
            jtype = "place"
        elif "school_district:" in part:
            jtype = "school_district"
            # Extract parent county if present
            if "county:" in ocd_id:
                parts = ocd_id.split("county:")
                if len(parts) > 1:
                    county_part = parts[1].split("/")[0]
                    parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/county:{county_part}"

    if not state_code or not jtype:
        return None

    return {
        "ocd_id": ocd_id.strip(),
        "state_code": state_code,
        "jurisdiction_type": jtype,
        "name": name.strip(),
        "parent_ocd_id": parent_ocd,
    }


def parse_local_gov_row(ocd_id: str, name: str, state_code: str) -> dict | None:
    """Parse a state-*-local_gov.csv (ocd_id, name) pair into a normalized field
    dict.

    Returns None for rows that should be skipped. Logic preserved verbatim from
    the original loader.
    """
    if not ocd_id or not name:
        return None

    # Parse jurisdiction type
    jtype = None
    parent_ocd = None

    if "place:" in ocd_id:
        jtype = "place"
    elif "county:" in ocd_id:
        jtype = "county"
    elif "council_district:" in ocd_id:
        jtype = "council_district"
        # Extract parent place
        if "place:" in ocd_id:
            parts = ocd_id.split("place:")
            if len(parts) > 1:
                place_part = parts[1].split("/")[0]
                parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/place:{place_part}"
    elif "ward:" in ocd_id:
        jtype = "ward"
        if "place:" in ocd_id:
            parts = ocd_id.split("place:")
            if len(parts) > 1:
                place_part = parts[1].split("/")[0]
                parent_ocd = f"ocd-division/country:us/state:{state_code.lower()}/place:{place_part}"

    if not jtype:
        return None

    return {
        "ocd_id": ocd_id.strip(),
        "state_code": state_code,
        "jurisdiction_type": jtype,
        "name": name.strip(),
        "parent_ocd_id": parent_ocd,
    }


class JurisdictionOcdRow(RawRow):
    """One OpenCivicData jurisdiction row, validated before upsert."""

    ocd_id: str = Field(min_length=1)
    state_code: str = Field(min_length=1)
    jurisdiction_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    parent_ocd_id: str | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_ocd (
        ocd_id              TEXT PRIMARY KEY,
        state_code          TEXT NOT NULL,
        jurisdiction_type   TEXT NOT NULL,
        name                TEXT NOT NULL,
        parent_ocd_id       TEXT,
        ingestion_date      TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bjo_state_code ON bronze.bronze_jurisdiction_ocd(state_code)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjo_type       ON bronze.bronze_jurisdiction_ocd(jurisdiction_type)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjo_parent     ON bronze.bronze_jurisdiction_ocd(parent_ocd_id)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_jurisdiction_ocd")

# Preserves ON CONFLICT (ocd_id) DO NOTHING from the original loader.
_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_jurisdiction_ocd
        (ocd_id, state_code, jurisdiction_type, name, parent_ocd_id)
    VALUES
        (:ocd_id, :state_code, :jurisdiction_type, :name, :parent_ocd_id)
    ON CONFLICT (ocd_id) DO NOTHING
    """
)


class JurisdictionPilotOcdPipeline(DataSourcePipeline[JurisdictionOcdRow]):
    source = "jurisdiction_pilot_ocd"
    batch_size = 2_000
    row_schema = JurisdictionOcdRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        cache_dir = self._path or find_cache_dir()
        emitted = 0

        # Load from country-us.csv (counties and base jurisdictions)
        country_csv = cache_dir / "identifiers" / "country-us.csv"
        if country_csv.exists():
            with open(country_csv, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for ocd_id, name in reader:
                    if self._limit is not None and emitted >= self._limit:
                        return
                    rec = parse_country_row(ocd_id, name)
                    if rec is None:
                        continue
                    yield {
                        "source": self.source,
                        "source_version": "country-us",
                        "natural_key": rec["ocd_id"],
                        **rec,
                    }
                    emitted += 1

        # Load from state-specific local_gov.csv (municipalities, districts)
        identifiers_dir = cache_dir / "identifiers" / "country-us"
        if identifiers_dir.exists():
            for state_csv in sorted(identifiers_dir.glob("state-*-local_gov.csv")):
                state_code = state_csv.name.split("-")[1].upper()
                with open(state_csv, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for ocd_id, name in reader:
                        if self._limit is not None and emitted >= self._limit:
                            return
                        rec = parse_local_gov_row(ocd_id, name, state_code)
                        if rec is None:
                            continue
                        yield {
                            "source": self.source,
                            "source_version": state_csv.stem,
                            "natural_key": rec["ocd_id"],
                            **rec,
                        }
                        emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[JurisdictionOcdRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "ocd_id": r.ocd_id,
                "state_code": r.state_code,
                "jurisdiction_type": r.jurisdiction_type,
                "name": r.name,
                "parent_ocd_id": r.parent_ocd_id,
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
        description="Load OpenCivicData jurisdictions into bronze.bronze_jurisdiction_ocd"
    )
    parser.add_argument(
        "--path", type=Path,
        help="Path to OCD cache dir (default: data/cache/opencivicdata/)",
    )
    parser.add_argument("--limit", type=int, help="Load only the first N rows")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = JurisdictionPilotOcdPipeline(path=args.path, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

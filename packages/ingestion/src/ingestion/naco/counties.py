#!/usr/bin/env python3
"""NACo counties pipeline: land cached NACo county JSON RAW into bronze.

Ported from load_naco_to_bronze.py to the core_lib DataSourcePipeline contract,
then dbt-slimmed: this loader lands the RAW NACo county JSON object plus the
natural-key columns ONLY. The multi-alias coalescing / digit-stripping /
numeric-extraction derivation (formerly ``parse_county``) now lives in dbt:
    dbt_project/models/staging/stg_naco__county.sql
which reads ``raw_json`` JSONB and reproduces those columns in SQL.
See dbt_project/CONVENTIONS.md.

Run scrape_naco_counties.py first to populate the cache
(data/cache/naco/naco_counties_<STATE>_<YYYYMMDD>.json).

Tables created (DDL preserved from the legacy loader):
    bronze.bronze_jurisdictions_counties_naco   - one row per county (NACo County Explorer), RAW shape
    bronze.bronze_jurisdictions_officials_naco  - one row per county official

This pipeline ingests the counties table; the officials table DDL is preserved
and ensured here so the legacy schema stays intact (officials parsing is left
intact / separable per the task scope).

Legacy rename: migrations/015_rename_bronze_naco_jurisdictions.sql from bronze_naco_*.

Usage:
    python -m scripts.datasources.naco.counties_pipeline
    python scripts/datasources/naco/counties_pipeline.py --states AL,GA
    python scripts/datasources/naco/counties_pipeline.py --date 20260510
    python scripts/datasources/naco/counties_pipeline.py --truncate

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 / localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/naco")

BRONZE_NACO_COUNTIES = "bronze.bronze_jurisdictions_counties_naco"
BRONZE_NACO_OFFICIALS = "bronze.bronze_jurisdictions_officials_naco"


# --- Pure helpers (tiny coercers; preserved from the legacy loader) -----------
#
# NOTE: the heavy derivation (``parse_county``, ``_population_from_naco_display``,
# ``_naco_profile_county_block`` and the alias-coalescing it drove) has been moved
# OUT of this loader and into dbt: dbt_project/models/staging/stg_naco__county.sql
# now reads ``raw_json`` JSONB and reproduces those columns in SQL. The helpers
# below remain only because the still-Python ``parse_officials`` path uses them.


def _str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _int(val: Any) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _float(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def natural_key_for(raw: dict[str, Any]) -> tuple[str, str] | None:
    """Return ``(state_code, county_name)`` for a raw county dict, or None.

    Only the minimal alias-coalescing needed to build the bronze natural key
    (state_code + county_name). All other derivation lives in dbt. Rows that
    lack either key component are dropped here exactly as ``parse_county`` did.
    """
    county_name = _str(
        raw.get("name") or raw.get("county_name") or raw.get("countyName"), 255
    )
    state_code = _str(
        raw.get("state") or raw.get("state_code") or raw.get("stateCode"), 2
    )
    if not county_name or not state_code:
        return None
    return state_code.upper(), county_name


def parse_officials(raw: dict[str, Any]) -> list[tuple]:
    """Extract official rows from a county detail JSON dict."""
    county_name = _str(
        raw.get("name") or raw.get("county_name") or raw.get("countyName"), 255
    )
    state_code = _str(
        raw.get("state") or raw.get("state_code") or raw.get("stateCode"), 2
    )
    fips_code = _str(raw.get("fips") or raw.get("fips_code") or raw.get("geoid"), 5)

    officials_raw = (
        raw.get("officials")
        or raw.get("contacts")
        or raw.get("staff")
        or []
    )
    rows = []
    for off in officials_raw:
        name = _str(off.get("name") or off.get("officialName") or off.get("fullName"), 255)
        title = _str(off.get("title") or off.get("position") or off.get("role"), 255)
        if not name:
            continue
        rows.append((
            state_code.upper() if state_code else None,
            county_name,
            fips_code,
            name,
            title,
            _str(off.get("email"), 255),
            _str(off.get("phone") or off.get("phoneNumber"), 50),
            json.dumps(off),
        ))
    return rows


def find_cache_files(date_str: str | None, states: list[str] | None) -> list[Path]:
    """Locate county JSON cache files matching date + state filters."""
    pattern = "naco_counties_*.json"
    all_files = sorted(CACHE_DIR.glob(pattern))

    if date_str:
        all_files = [f for f in all_files if date_str in f.name]

    if states:
        all_files = [
            f for f in all_files
            if any(f.name.startswith(f"naco_counties_{s}_") for s in states)
        ]

    return all_files


def find_officials_cache_files(date_str: str | None) -> list[Path]:
    officials_dir = CACHE_DIR / "officials"
    if not officials_dir.exists():
        return []
    pattern = "naco_officials_*.json"
    files = sorted(officials_dir.glob(pattern))
    if date_str:
        files = [f for f in files if date_str in f.name]
    return files


# --- Row schema ---------------------------------------------------------------


class CountyRow(RawRow):
    """One RAW NACo county row, validated before upsert into the counties table.

    Slimmed shape: only the natural-key components (state_code + county_name)
    plus the full raw NACo county JSON object. Everything else
    (naco_id / fips_code / website / phone / email / population / area /
    county_seat) is now derived downstream in dbt from ``raw_json``.
    """

    county_name: str = Field(min_length=1, max_length=255)
    state_code: str = Field(min_length=1, max_length=2)
    raw_json: dict[str, Any] = Field(default_factory=dict)


# --- DDL (one statement per text(); preserved from the legacy loader) ---------

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_COUNTIES_SQL = text(
    f"""
    CREATE TABLE IF NOT EXISTS {BRONZE_NACO_COUNTIES} (
        state_code          VARCHAR(2)   NOT NULL,
        county_name         VARCHAR(255) NOT NULL,
        raw_json            JSONB        NOT NULL,
        ingestion_date      TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (state_code, county_name)
    )
    """
)

_CREATE_OFFICIALS_SQL = text(
    f"""
    CREATE TABLE IF NOT EXISTS {BRONZE_NACO_OFFICIALS} (
        id                  SERIAL PRIMARY KEY,
        state_code          VARCHAR(2),
        county_name         VARCHAR(255),
        fips_code           VARCHAR(5),
        official_name       VARCHAR(255),
        title               VARCHAR(255),
        email               VARCHAR(255),
        phone               VARCHAR(50),
        raw_json            JSONB,
        ingestion_date      TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(f"CREATE INDEX IF NOT EXISTS idx_bjcnc_state ON {BRONZE_NACO_COUNTIES}(state_code)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_bjcno_state  ON {BRONZE_NACO_OFFICIALS}(state_code)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_bjcno_fips   ON {BRONZE_NACO_OFFICIALS}(fips_code)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_bjcno_county ON {BRONZE_NACO_OFFICIALS}(state_code, county_name)"),
)

_TRUNCATE_SQL = text(f"TRUNCATE TABLE {BRONZE_NACO_COUNTIES}")

_UPSERT_SQL = text(
    f"""
    INSERT INTO {BRONZE_NACO_COUNTIES}
        (state_code, county_name, raw_json)
    VALUES
        (:state_code, :county_name, CAST(:raw_json AS jsonb))
    ON CONFLICT (state_code, county_name) DO UPDATE SET
        raw_json       = EXCLUDED.raw_json,
        ingestion_date = NOW()
    """
)


class NacoCountiesPipeline(DataSourcePipeline[CountyRow]):
    source = "naco_counties"
    batch_size = 2_000
    row_schema = CountyRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        date_str: str | None = None,
        states: list[str] | None = None,
        limit: int | None = None,
    ):
        self._path = path
        self._date_str = date_str
        self._states = states
        self._limit = limit

    def _discover(self) -> list[Path]:
        if self._path is not None:
            return [self._path]
        files = find_cache_files(self._date_str, self._states)
        if not files:
            raise FileNotFoundError(
                f"No NACo cache files found in {CACHE_DIR} for "
                f"date={self._date_str}, states={self._states}. "
                "Run scrape_naco_counties.py first."
            )
        return files

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        emitted = 0
        for cache_file in self._discover():
            raw_list = json.loads(cache_file.read_text())
            for raw in raw_list:
                if self._limit is not None and emitted >= self._limit:
                    return
                if not isinstance(raw, dict):
                    continue
                if raw.get("_fallback"):
                    # Raw HTML fallback - no structured data to parse yet
                    continue
                key = natural_key_for(raw)
                if key is None:
                    # No usable state_code + county_name -> cannot key the row.
                    continue
                state_code, county_name = key
                yield {
                    "source": self.source,
                    "source_version": cache_file.stem,
                    "natural_key": f"{state_code}:{county_name}",
                    "county_name": county_name,
                    "state_code": state_code,
                    # Land the full raw NACo county object verbatim; dbt derives
                    # all enrichment columns from this JSONB downstream.
                    "raw_json": raw,
                }
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CountyRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "state_code": r.state_code,
                "county_name": r.county_name,
                "raw_json": json.dumps(r.raw_json),
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_COUNTIES_SQL)
        await session.execute(_CREATE_OFFICIALS_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached NACo county data into bronze.bronze_jurisdictions_counties_naco"
    )
    parser.add_argument(
        "--states", type=str, help="Comma-separated state codes to load (e.g., AL,GA,MA)"
    )
    parser.add_argument(
        "--date", type=str, help="Cache date to load (YYYYMMDD). Default: today."
    )
    parser.add_argument(
        "--truncate", action="store_true", help="TRUNCATE table before loading"
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    date_str = args.date or datetime.now().strftime("%Y%m%d")
    states = (
        [s.strip().upper() for s in args.states.split(",")] if args.states else None
    )
    pipeline = NacoCountiesPipeline(
        date_str=date_str, states=states, limit=args.limit
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

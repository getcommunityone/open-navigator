#!/usr/bin/env python3
"""Census Gazetteer pipeline: load cached CSVs into bronze jurisdiction tables.

Ported from load_census_gazetteer.py to the core_lib DataSourcePipeline
contract.

Reads cached CSVs from data/cache/census/gazetteer/ and loads into:
  states                -> bronze.bronze_jurisdictions_states
  counties              -> bronze.bronze_jurisdictions_counties
  municipalities        -> bronze.bronze_jurisdictions_municipalities
  school_districts      -> bronze.bronze_jurisdictions_school_districts  (unified only)
  townships             -> bronze.bronze_jurisdictions_townships
  zcta                  -> bronze.bronze_jurisdictions_zcta

Run download_census_gazetteer.py first to populate the cache.

Usage:
    python -m ingestion.census.gazetteer
    python -m ingestion.census.gazetteer --types counties municipalities
    python -m ingestion.census.gazetteer --filter-usps AL,GA

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 / target_database_url resolution).
"""
from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/census/gazetteer")

# Configuration for each jurisdiction type
TYPES = {
    "states": {
        "table": "bronze.bronze_jurisdictions_states",
        "cache_file": "states.csv",
        "geoid_len": 2,
        "ddl": [
            "CREATE SCHEMA IF NOT EXISTS bronze",
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_states (
                geoid           VARCHAR(2)    PRIMARY KEY,
                usps            VARCHAR(2),
                ansicode        VARCHAR(8),
                name            VARCHAR(255),
                aland           BIGINT,
                awater          BIGINT,
                aland_sqmi      NUMERIC(12, 6),
                awater_sqmi     NUMERIC(12, 6),
                intptlat        NUMERIC(11, 8),
                intptlong       NUMERIC(12, 8),
                ingestion_date  TIMESTAMP DEFAULT NOW(),
                jurisdiction_id      TEXT GENERATED ALWAYS AS (usps) STORED,
                jurisdiction_type       bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'state',
                jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'usps',
                UNIQUE (jurisdiction_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_bjs_usps            ON bronze.bronze_jurisdictions_states(usps)",
            "CREATE INDEX IF NOT EXISTS idx_bjs_coords          ON bronze.bronze_jurisdictions_states(intptlat, intptlong)",
            "CREATE INDEX IF NOT EXISTS idx_bjs_jurisdiction_id ON bronze.bronze_jurisdictions_states(jurisdiction_id)",
        ],
        "columns": ["geoid", "usps", "ansicode", "name", "aland", "awater", "aland_sqmi", "awater_sqmi", "intptlat", "intptlong"],
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_states
                (geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (:geoid, :usps, :ansicode, :name, :aland, :awater, :aland_sqmi, :awater_sqmi, :intptlat, :intptlong)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "counties": {
        "table": "bronze.bronze_jurisdictions_counties",
        "cache_file": "counties.csv",
        "geoid_len": 5,
        "ddl": [
            "CREATE SCHEMA IF NOT EXISTS bronze",
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_counties (
                geoid           VARCHAR(5)    PRIMARY KEY,
                usps            VARCHAR(2),
                ansicode        VARCHAR(8),
                name            VARCHAR(255),
                aland           BIGINT,
                awater          BIGINT,
                aland_sqmi      NUMERIC(12, 6),
                awater_sqmi     NUMERIC(12, 6),
                intptlat        NUMERIC(11, 8),
                intptlong       NUMERIC(12, 8),
                ingestion_date  TIMESTAMP DEFAULT NOW(),
                jurisdiction_id        TEXT GENERATED ALWAYS AS (bronze.jurisdiction_id_from_place(name, geoid)) STORED,
                jurisdiction_type       bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'county',
                jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'county_fips',
                UNIQUE (jurisdiction_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_bjc_usps            ON bronze.bronze_jurisdictions_counties(usps)",
            "CREATE INDEX IF NOT EXISTS idx_bjc_coords          ON bronze.bronze_jurisdictions_counties(intptlat, intptlong)",
            "CREATE INDEX IF NOT EXISTS idx_bjc_jurisdiction_id ON bronze.bronze_jurisdictions_counties(jurisdiction_id)",
        ],
        "columns": ["geoid", "usps", "ansicode", "name", "aland", "awater", "aland_sqmi", "awater_sqmi", "intptlat", "intptlong"],
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_counties
                (geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (:geoid, :usps, :ansicode, :name, :aland, :awater, :aland_sqmi, :awater_sqmi, :intptlat, :intptlong)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "municipalities": {
        "table": "bronze.bronze_jurisdictions_municipalities",
        "cache_file": "municipalities.csv",
        "geoid_len": 7,
        "ddl": [
            "CREATE SCHEMA IF NOT EXISTS bronze",
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_municipalities (
                geoid           VARCHAR(7)    PRIMARY KEY,
                usps            VARCHAR(2),
                ansicode        VARCHAR(8),
                name            VARCHAR(255),
                lsad            VARCHAR(5),
                funcstat        VARCHAR(1),
                aland           BIGINT,
                awater          BIGINT,
                aland_sqmi      NUMERIC(12, 6),
                awater_sqmi     NUMERIC(12, 6),
                intptlat        NUMERIC(11, 8),
                intptlong       NUMERIC(12, 8),
                ingestion_date  TIMESTAMP DEFAULT NOW(),
                jurisdiction_id        TEXT GENERATED ALWAYS AS (bronze.jurisdiction_id_from_place(name, geoid)) STORED,
                jurisdiction_type       bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'municipality',
                jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'place_geoid',
                UNIQUE (jurisdiction_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_bjm_usps            ON bronze.bronze_jurisdictions_municipalities(usps)",
            "CREATE INDEX IF NOT EXISTS idx_bjm_lsad            ON bronze.bronze_jurisdictions_municipalities(lsad)",
            "CREATE INDEX IF NOT EXISTS idx_bjm_funcstat        ON bronze.bronze_jurisdictions_municipalities(funcstat)",
            "CREATE INDEX IF NOT EXISTS idx_bjm_coords          ON bronze.bronze_jurisdictions_municipalities(intptlat, intptlong)",
            "CREATE INDEX IF NOT EXISTS idx_bjm_jurisdiction_id ON bronze.bronze_jurisdictions_municipalities(jurisdiction_id)",
        ],
        "columns": ["geoid", "usps", "ansicode", "name", "lsad", "funcstat", "aland", "awater", "aland_sqmi", "awater_sqmi", "intptlat", "intptlong"],
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_municipalities
                (geoid, usps, ansicode, name, lsad, funcstat, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (:geoid, :usps, :ansicode, :name, :lsad, :funcstat, :aland, :awater, :aland_sqmi, :awater_sqmi, :intptlat, :intptlong)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                lsad           = EXCLUDED.lsad,
                funcstat       = EXCLUDED.funcstat,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "school_districts": {
        "table": "bronze.bronze_jurisdictions_school_districts",
        "cache_file": "school_districts_unified.csv",
        "geoid_len": 7,
        "ddl": [
            "CREATE SCHEMA IF NOT EXISTS bronze",
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_school_districts (
                geoid           VARCHAR(7)    PRIMARY KEY,
                usps            VARCHAR(2),
                name            VARCHAR(255),
                lograde         VARCHAR(5),
                higrade         VARCHAR(5),
                aland           BIGINT,
                awater          BIGINT,
                aland_sqmi      NUMERIC(12, 6),
                awater_sqmi     NUMERIC(12, 6),
                intptlat        NUMERIC(11, 8),
                intptlong       NUMERIC(12, 8),
                ingestion_date  TIMESTAMP DEFAULT NOW(),
                jurisdiction_id        TEXT GENERATED ALWAYS AS (bronze.jurisdiction_id_from_place(name, geoid)) STORED,
                jurisdiction_type       bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'school_district',
                jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'school_district_geoid',
                UNIQUE (jurisdiction_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_bjsd_usps            ON bronze.bronze_jurisdictions_school_districts(usps)",
            "CREATE INDEX IF NOT EXISTS idx_bjsd_coords          ON bronze.bronze_jurisdictions_school_districts(intptlat, intptlong)",
            "CREATE INDEX IF NOT EXISTS idx_bjsd_jurisdiction_id ON bronze.bronze_jurisdictions_school_districts(jurisdiction_id)",
        ],
        "columns": ["geoid", "usps", "name", "lograde", "higrade", "aland", "awater", "aland_sqmi", "awater_sqmi", "intptlat", "intptlong"],
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_school_districts
                (geoid, usps, name, lograde, higrade, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (:geoid, :usps, :name, :lograde, :higrade, :aland, :awater, :aland_sqmi, :awater_sqmi, :intptlat, :intptlong)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                name           = EXCLUDED.name,
                lograde        = EXCLUDED.lograde,
                higrade        = EXCLUDED.higrade,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "townships": {
        "table": "bronze.bronze_jurisdictions_townships",
        "cache_file": "townships.csv",
        "geoid_len": 10,
        "ddl": [
            "CREATE SCHEMA IF NOT EXISTS bronze",
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_townships (
                geoid          VARCHAR(10)   PRIMARY KEY,
                usps           VARCHAR(2),
                ansicode       VARCHAR(8),
                name           VARCHAR(255),
                funcstat       VARCHAR(1),
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_bjt_usps     ON bronze.bronze_jurisdictions_townships(usps)",
            "CREATE INDEX IF NOT EXISTS idx_bjt_funcstat ON bronze.bronze_jurisdictions_townships(funcstat)",
            "CREATE INDEX IF NOT EXISTS idx_bjt_coords   ON bronze.bronze_jurisdictions_townships(intptlat, intptlong)",
        ],
        "columns": ["geoid", "usps", "ansicode", "name", "funcstat", "aland", "awater", "aland_sqmi", "awater_sqmi", "intptlat", "intptlong"],
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_townships
                (geoid, usps, ansicode, name, funcstat, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (:geoid, :usps, :ansicode, :name, :funcstat, :aland, :awater, :aland_sqmi, :awater_sqmi, :intptlat, :intptlong)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                funcstat       = EXCLUDED.funcstat,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "zcta": {
        "table": "bronze.bronze_jurisdictions_zcta",
        "cache_file": "zcta.csv",
        "geoid_len": 5,
        "ddl": [
            "CREATE SCHEMA IF NOT EXISTS bronze",
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_zcta (
                geoid          VARCHAR(5)    PRIMARY KEY,
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_bjz_coords ON bronze.bronze_jurisdictions_zcta(intptlat, intptlong)",
        ],
        "columns": ["geoid", "aland", "awater", "aland_sqmi", "awater_sqmi", "intptlat", "intptlong"],
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_zcta
                (geoid, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (:geoid, :aland, :awater, :aland_sqmi, :awater_sqmi, :intptlat, :intptlong)
            ON CONFLICT (geoid) DO UPDATE SET
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
}


def _filter_gazetteer_df(df: pd.DataFrame, jtype: str, filter_usps: set[str], include_zcta: bool):
    """Keep rows whose USPS matches filter_usps; ZCTAs are national-only unless --include-zcta-national."""
    if not filter_usps:
        return df
    if jtype == "zcta":
        if include_zcta:
            return df
        logger.warning(
            "Skipping zcta rows: --filter-usps is set; pass --include-zcta-national to load national ZCTA anyway."
        )
        return df.iloc[0:0].copy()
    col = None
    for c in df.columns:
        if str(c).strip().upper() == "USPS":
            col = c
            break
    if col is None:
        logger.warning(f"No USPS column in {jtype} gazetteer; loading all rows (no USPS filter)")
        return df
    normalized = df[col].fillna("").astype(str).str.strip().str.upper()
    return df.loc[normalized.isin(filter_usps)].copy()


def safe_int(val):
    try:
        return int(float(val)) if pd.notna(val) else None
    except (ValueError, TypeError):
        return None


def safe_float(val):
    try:
        return float(val) if pd.notna(val) else None
    except (ValueError, TypeError):
        return None


def safe_str(val, maxlen=None):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    return s[:maxlen] if maxlen else s


def build_records(df: pd.DataFrame, jtype: str) -> list[dict]:
    """Map a Gazetteer DataFrame to per-column dicts keyed by the target columns."""
    geoid_len = TYPES[jtype]["geoid_len"]
    records: list[dict] = []

    for _, row in df.iterrows():
        raw_geoid = safe_str(row.get("GEOID"))
        if not raw_geoid:
            continue
        geoid = raw_geoid.zfill(geoid_len)

        common = {
            "aland": safe_int(row.get("ALAND")),
            "awater": safe_int(row.get("AWATER")),
            "aland_sqmi": safe_float(row.get("ALAND_SQMI")),
            "awater_sqmi": safe_float(row.get("AWATER_SQMI")),
            "intptlat": safe_float(row.get("INTPTLAT")),
            "intptlong": safe_float(row.get("INTPTLONG")),
        }

        if jtype == "states":
            records.append({
                "geoid": geoid,
                "usps": safe_str(row.get("USPS"), 2),
                "ansicode": safe_str(row.get("ANSICODE"), 8),
                "name": safe_str(row.get("NAME"), 255),
                **common,
            })
        elif jtype == "counties":
            records.append({
                "geoid": geoid,
                "usps": safe_str(row.get("USPS"), 2),
                "ansicode": safe_str(row.get("ANSICODE"), 8),
                "name": safe_str(row.get("NAME"), 255),
                **common,
            })
        elif jtype == "municipalities":
            records.append({
                "geoid": geoid,
                "usps": safe_str(row.get("USPS"), 2),
                "ansicode": safe_str(row.get("ANSICODE"), 8),
                "name": safe_str(row.get("NAME"), 255),
                "lsad": safe_str(row.get("LSAD"), 5),
                "funcstat": safe_str(row.get("FUNCSTAT"), 1),
                **common,
            })
        elif jtype == "school_districts":
            records.append({
                "geoid": geoid,
                "usps": safe_str(row.get("USPS"), 2),
                "name": safe_str(row.get("NAME"), 255),
                "lograde": safe_str(row.get("LOGRADE"), 5),
                "higrade": safe_str(row.get("HIGRADE"), 5),
                **common,
            })
        elif jtype == "townships":
            records.append({
                "geoid": geoid,
                "usps": safe_str(row.get("USPS"), 2),
                "ansicode": safe_str(row.get("ANSICODE"), 8),
                "name": safe_str(row.get("NAME"), 255),
                "funcstat": safe_str(row.get("FUNCSTAT"), 1),
                **common,
            })
        elif jtype == "zcta":
            records.append({"geoid": geoid, **common})

    return records


class GazetteerRow(RawRow):
    """One Census Gazetteer jurisdiction row, validated before upsert.

    Columns span every jurisdiction type; only the columns relevant to a
    given type are populated (the rest stay None). Field constraints mirror
    the bronze DDL column types (VARCHAR(n) -> max_length, NUMERIC -> Decimal).
    """

    jtype: str = Field(min_length=1)
    geoid: str = Field(min_length=1, max_length=10)
    usps: str | None = Field(default=None, max_length=2)
    ansicode: str | None = Field(default=None, max_length=8)
    name: str | None = Field(default=None, max_length=255)
    lsad: str | None = Field(default=None, max_length=5)
    funcstat: str | None = Field(default=None, max_length=1)
    lograde: str | None = Field(default=None, max_length=5)
    higrade: str | None = Field(default=None, max_length=5)
    aland: int | None = None
    awater: int | None = None
    aland_sqmi: Decimal | None = None
    awater_sqmi: Decimal | None = None
    intptlat: Decimal | None = None
    intptlong: Decimal | None = None


class CensusGazetteerPipeline(DataSourcePipeline[GazetteerRow]):
    source = "census_gazetteer"
    batch_size = 5_000
    row_schema = GazetteerRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        limit: int | None = None,
        types: list[str] | None = None,
        filter_usps: set[str] | None = None,
        include_zcta: bool = False,
    ):
        self._path = path
        self._limit = limit
        self._types = types or list(TYPES.keys())
        self._filter_usps = filter_usps
        self._include_zcta = include_zcta

    def _cache_file(self, jtype: str) -> Path:
        if self._path is not None:
            return self._path
        return CACHE_DIR / TYPES[jtype]["cache_file"]

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        for jtype in self._types:
            cache_file = self._cache_file(jtype)
            if not cache_file.exists():
                logger.error(
                    f"Cache file not found: {cache_file}. Run download_census_gazetteer.py first."
                )
                continue

            logger.info(f"Reading {jtype} from {cache_file}...")
            df = pd.read_csv(cache_file, dtype=str, low_memory=False)
            df.columns = [c.strip() for c in df.columns]
            if self._filter_usps:
                df = _filter_gazetteer_df(df, jtype, self._filter_usps, self._include_zcta)
                logger.info(
                    f"After USPS filter {sorted(self._filter_usps)}: {len(df):,} {jtype} row(s)"
                )
            if self._limit:
                df = df.head(self._limit)

            records = build_records(df, jtype)
            logger.info(f"Prepared {len(records):,} {jtype} records")

            for rec in records:
                yield {
                    "source": self.source,
                    "source_version": jtype,
                    "natural_key": f"{jtype}:{rec['geoid']}",
                    "jtype": jtype,
                    **rec,
                }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[GazetteerRow],
        ctx: PipelineContext,
    ) -> None:
        # Rows of different types route to different tables; group by jtype.
        by_type: dict[str, list[GazetteerRow]] = {}
        for r in rows:
            by_type.setdefault(r.jtype, []).append(r)

        for jtype, group in by_type.items():
            cfg = TYPES[jtype]
            cols = cfg["columns"]
            params = [{col: getattr(r, col) for col in cols} for r in group]
            await session.execute(text(cfg["insert"]), params)


async def _prepare_target(truncate: bool, types: list[str] | None = None) -> None:
    target_types = types or list(TYPES.keys())
    async with async_session() as session:
        for jtype in target_types:
            cfg = TYPES[jtype]
            for stmt in cfg["ddl"]:
                await session.execute(text(stmt))
            if truncate:
                await session.execute(text(f"TRUNCATE TABLE {cfg['table']}"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Census Gazetteer CSVs into bronze jurisdiction tables"
    )
    parser.add_argument(
        "--types", nargs="+", choices=list(TYPES.keys()), default=list(TYPES.keys()),
        help="Types to load (default: all)",
    )
    parser.add_argument("--limit", type=int, help="Limit records per type (for testing)")
    parser.add_argument(
        "--filter-usps",
        default="",
        help="Comma-separated USPS (e.g. AL,WA). Skips national ZCTA unless --include-zcta-national.",
    )
    parser.add_argument(
        "--include-zcta-national",
        action="store_true",
        help="When using --filter-usps, still load full ZCTA file (national, not USPS scoped).",
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE tables before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    filter_usps: set[str] = set()
    if args.filter_usps.strip():
        filter_usps = {x.strip().upper() for x in args.filter_usps.split(",") if x.strip()}

    await _prepare_target(args.truncate, types=args.types)
    pipeline = CensusGazetteerPipeline(
        limit=args.limit,
        types=args.types,
        filter_usps=filter_usps if filter_usps else None,
        include_zcta=args.include_zcta_national,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

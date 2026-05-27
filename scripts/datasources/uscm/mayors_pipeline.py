#!/usr/bin/env python3
"""USCM "Meet the Mayors" pipeline: load cached scrape JSON into bronze.

Ported from load_uscm_mayors_to_bronze.py to the core_lib DataSourcePipeline
contract.

Expects output from download_uscm_mayors.py
(``data/cache/uscm/meet_the_mayors_us_*.json``).

Usage:
    python -m scripts.datasources.uscm.mayors_pipeline
    python scripts/datasources/uscm/mayors_pipeline.py --truncate
    python scripts/datasources/uscm/mayors_pipeline.py \\
        --file data/cache/uscm/meet_the_mayors_us_20260510.json

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
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


CACHE_DIR = Path("data/cache/uscm")
BRONZE_TABLE = "bronze.bronze_jurisdictions_municipalities_uscm"


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


def find_latest_cache() -> Path | None:
    if not CACHE_DIR.exists():
        return None
    paths = sorted(
        CACHE_DIR.glob("meet_the_mayors_us_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return paths[0] if paths else None


class MayorRow(RawRow):
    """One USCM mayor card, validated before upsert into bronze."""

    state_code: str = Field(min_length=2, max_length=2)
    municipality_name: str = Field(min_length=1, max_length=255)
    mayor_name: str | None = Field(default=None, max_length=255)
    population: int | None = None
    mayor_photo_url: str | None = None
    city_website: str | None = Field(default=None, max_length=500)
    bio_url: str | None = Field(default=None, max_length=500)
    next_election_raw: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    search_term_used: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=500)
    scraped_at: str | None = None  # passthrough (timestamptz-castable)
    raw_json: dict[str, Any] = Field(default_factory=dict)


_CREATE_SQL = text(
    f"""
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS {BRONZE_TABLE} (
        state_code           VARCHAR(2) NOT NULL,
        municipality_name    VARCHAR(255) NOT NULL,
        mayor_name           VARCHAR(255),
        population           INTEGER,
        mayor_photo_url      TEXT,
        city_website         VARCHAR(500),
        bio_url              VARCHAR(500),
        next_election_raw    VARCHAR(255),
        phone                VARCHAR(80),
        email                VARCHAR(255),
        search_term_used     VARCHAR(120),
        source_url           VARCHAR(500),
        scraped_at           TIMESTAMPTZ,
        raw_json             JSONB,
        ingestion_date       TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (state_code, municipality_name)
    );
    CREATE INDEX IF NOT EXISTS idx_bjmuscm_state ON {BRONZE_TABLE}(state_code);
    """
)
_TRUNCATE_SQL = text(f"TRUNCATE TABLE {BRONZE_TABLE}")
_UPSERT_SQL = text(
    f"""
    INSERT INTO {BRONZE_TABLE} (
        state_code, municipality_name, mayor_name, population, mayor_photo_url,
        city_website, bio_url, next_election_raw, phone, email,
        search_term_used, source_url, scraped_at, raw_json
    )
    VALUES (
        :state_code, :municipality_name, :mayor_name, :population, :mayor_photo_url,
        :city_website, :bio_url, :next_election_raw, :phone, :email,
        :search_term_used, :source_url, :scraped_at, CAST(:raw_json AS jsonb)
    )
    ON CONFLICT (state_code, municipality_name) DO UPDATE SET
        mayor_name = EXCLUDED.mayor_name,
        population = EXCLUDED.population,
        mayor_photo_url = EXCLUDED.mayor_photo_url,
        city_website = EXCLUDED.city_website,
        bio_url = EXCLUDED.bio_url,
        next_election_raw = EXCLUDED.next_election_raw,
        phone = EXCLUDED.phone,
        email = EXCLUDED.email,
        search_term_used = EXCLUDED.search_term_used,
        source_url = EXCLUDED.source_url,
        scraped_at = EXCLUDED.scraped_at,
        raw_json = EXCLUDED.raw_json,
        ingestion_date = NOW()
    """
)


class UscmMayorsPipeline(DataSourcePipeline[MayorRow]):
    source = "uscm_mayors"
    batch_size = 2_000
    row_schema = MayorRow

    def __init__(self, *, json_path: Path | None = None):
        self._json_path = json_path

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._json_path or find_latest_cache()
        if path is None or not path.is_file():
            raise FileNotFoundError(
                f"No USCM cache file. Run download_uscm_mayors.py first or pass --file. "
                f"Expected under {CACHE_DIR}/meet_the_mayors_us_*.json"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        mayors = raw.get("mayors")
        if not isinstance(mayors, list):
            return
        scraped_at = raw.get("scraped_at")
        source_url = _str(raw.get("source_url"), 500)
        for m in mayors:
            if not isinstance(m, dict):
                continue
            state_code = _str(m.get("state_code"), 2)
            municipality_name = _str(m.get("municipality_name"), 255)
            if not state_code or not municipality_name:
                continue
            slim_raw = {k: v for k, v in m.items() if k != "raw_card_html"}
            state_code = state_code.upper()
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": f"{state_code}:{municipality_name}",
                "state_code": state_code,
                "municipality_name": municipality_name,
                "mayor_name": _str(m.get("mayor_name"), 255),
                "population": _int(m.get("population")),
                "mayor_photo_url": _str(m.get("mayor_photo_url")),
                "city_website": _str(m.get("city_website"), 500),
                "bio_url": _str(m.get("bio_url"), 500),
                "next_election_raw": _str(m.get("next_election_raw"), 255),
                "phone": _str(m.get("phone"), 80),
                "email": _str(m.get("email"), 255),
                "search_term_used": _str(m.get("search_term_used"), 120),
                "source_url": source_url,
                "scraped_at": scraped_at,
                "raw_json": slim_raw,
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[MayorRow],
        ctx: PipelineContext,
    ) -> None:
        params = []
        for r in rows:
            params.append({
                "state_code": r.state_code,
                "municipality_name": r.municipality_name,
                "mayor_name": r.mayor_name,
                "population": r.population,
                "mayor_photo_url": r.mayor_photo_url,
                "city_website": r.city_website,
                "bio_url": r.bio_url,
                "next_election_raw": r.next_election_raw,
                "phone": r.phone,
                "email": r.email,
                "search_term_used": r.search_term_used,
                "source_url": r.source_url,
                "scraped_at": r.scraped_at,
                "raw_json": json.dumps(r.raw_json),
            })
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        # CREATE SCHEMA + CREATE TABLE + CREATE INDEX combined; SQLAlchemy text()
        # supports multiple statements only when no params — split for safety.
        for stmt in str(_CREATE_SQL.text).split(";"):
            s = stmt.strip()
            if s:
                await session.execute(text(s))
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Load USCM Meet the Mayors JSON into {BRONZE_TABLE}"
    )
    parser.add_argument("--file", type=Path,
                        help="meet_the_mayors_us_*.json path (default: newest in cache)")
    parser.add_argument("--truncate", action="store_true",
                        help=f"TRUNCATE {BRONZE_TABLE} before loading")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = UscmMayorsPipeline(json_path=args.file)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

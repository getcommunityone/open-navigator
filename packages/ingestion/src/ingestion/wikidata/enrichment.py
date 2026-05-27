#!/usr/bin/env python3
"""Wikidata enrichment bronze loader (LAND layer).

Reads the per-state/type enrichment JSON written by ingestion.wikidata.download
(data/cache/wikidata/<usps>/wikidata_enrichment_<type>.json) and lands each row
RAW into bronze.bronze_jurisdiction_wikidata_enrichment — one physical row per
(state_code, jurisdiction_type, wikidata_id). No transformation: the
identifier reconciliation + UPDATE-onto-seed-by-geoid happens downstream in dbt
(stg_wikidata__enrichment -> int_wikidata__jurisdictions_enriched).

Pipeline order: ingestion.wikidata.download (FETCH) -> THIS (LAND) -> dbt (DERIVE).

Usage:
    python -m ingestion.wikidata.enrichment
    python -m ingestion.wikidata.enrichment --truncate
    python -m ingestion.wikidata.enrichment --cache-dir data/cache/wikidata --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/wikidata")

# Enrichment payload fields (raw strings, exactly as ingestion.wikidata.download
# writes them). dbt (stg_wikidata__enrichment) casts numerics; bronze stays raw.
_PAYLOAD_FIELDS = [
    "item_label",
    "fips_code", "fips_alt", "gnis_id", "nces_id",
    "official_website", "official_image_url", "page_banner_image", "locator_map_image",
    "youtube_channel_id", "facebook_username", "twitter_username",
    "population", "area_sq_km", "per_capita_income", "number_of_households",
    "median_age", "latitude", "longitude",
]
# Full insert column set, in order.
COLUMNS = ["state_code", "jurisdiction_type", "wikidata_id", *_PAYLOAD_FIELDS, "fetched_at"]


def find_enrichment_files(cache_dir: Path) -> list[Path]:
    files = sorted(cache_dir.glob("*/wikidata_enrichment_*.json"))
    if not files:
        raise FileNotFoundError(
            f"No Wikidata enrichment cache found in {cache_dir} "
            "(expected <usps>/wikidata_enrichment_<type>.json). "
            "Run ingestion.wikidata.download first."
        )
    return files


def _s(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


class WikidataEnrichmentRow(RawRow):
    """One Wikidata enrichment record, validated before upsert. Raw strings."""

    state_code: str = Field(min_length=1, max_length=2)
    jurisdiction_type: str = Field(min_length=1, max_length=32)
    wikidata_id: str = Field(min_length=1, max_length=32)
    item_label: str | None = None
    fips_code: str | None = Field(default=None, max_length=20)
    fips_alt: str | None = Field(default=None, max_length=20)
    gnis_id: str | None = Field(default=None, max_length=20)
    nces_id: str | None = Field(default=None, max_length=20)
    official_website: str | None = None
    official_image_url: str | None = None
    page_banner_image: str | None = None
    locator_map_image: str | None = None
    youtube_channel_id: str | None = None
    facebook_username: str | None = None
    twitter_username: str | None = None
    population: str | None = None
    area_sq_km: str | None = None
    per_capita_income: str | None = None
    number_of_households: str | None = None
    median_age: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    fetched_at: str | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_wikidata_enrichment (
        state_code           VARCHAR(2)   NOT NULL,
        jurisdiction_type    VARCHAR(32)  NOT NULL,
        wikidata_id          VARCHAR(32)  NOT NULL,
        item_label           TEXT,
        fips_code            VARCHAR(20),
        fips_alt             VARCHAR(20),
        gnis_id              VARCHAR(20),
        nces_id              VARCHAR(20),
        official_website     TEXT,
        official_image_url   TEXT,
        page_banner_image    TEXT,
        locator_map_image    TEXT,
        youtube_channel_id   TEXT,
        facebook_username    TEXT,
        twitter_username     TEXT,
        population           TEXT,
        area_sq_km           TEXT,
        per_capita_income    TEXT,
        number_of_households TEXT,
        median_age           TEXT,
        latitude             TEXT,
        longitude            TEXT,
        fetched_at           TIMESTAMPTZ,
        loaded_at            TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (state_code, jurisdiction_type, wikidata_id)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bjwe_fips ON bronze.bronze_jurisdiction_wikidata_enrichment(fips_code)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjwe_gnis ON bronze.bronze_jurisdiction_wikidata_enrichment(gnis_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bjwe_nces ON bronze.bronze_jurisdiction_wikidata_enrichment(nces_id)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_jurisdiction_wikidata_enrichment")

_SET_CLAUSE = ",\n        ".join(
    f"{c} = EXCLUDED.{c}" for c in (*_PAYLOAD_FIELDS, "fetched_at")
)
_UPSERT_SQL = text(
    f"""
    INSERT INTO bronze.bronze_jurisdiction_wikidata_enrichment
        ({", ".join(COLUMNS)})
    VALUES
        ({", ".join(":" + c if c != "fetched_at" else "CAST(:fetched_at AS timestamptz)" for c in COLUMNS)})
    ON CONFLICT (state_code, jurisdiction_type, wikidata_id) DO UPDATE SET
        {_SET_CLAUSE},
        loaded_at = NOW()
    """
)


class WikidataEnrichmentPipeline(DataSourcePipeline[WikidataEnrichmentRow]):
    source = "wikidata_enrichment"
    batch_size = 2_000
    row_schema = WikidataEnrichmentRow

    def __init__(self, *, cache_dir: Path | None = None, limit: int | None = None):
        self._cache_dir = cache_dir or CACHE_DIR
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        emitted = 0
        for path in find_enrichment_files(self._cache_dir):
            payload = json.loads(path.read_text())
            state_code = _s(payload.get("state_code"))
            jurisdiction_type = _s(payload.get("jurisdiction_type"))
            fetched_at = _s(payload.get("fetched_at"))
            for rec in payload.get("rows") or []:
                if self._limit is not None and emitted >= self._limit:
                    return
                wikidata_id = _s(rec.get("wikidata_id"))
                if not (state_code and jurisdiction_type and wikidata_id):
                    continue
                row = {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{state_code}:{jurisdiction_type}:{wikidata_id}",
                    "state_code": state_code,
                    "jurisdiction_type": jurisdiction_type,
                    "wikidata_id": wikidata_id,
                    "fetched_at": fetched_at,
                }
                for f in _PAYLOAD_FIELDS:
                    row[f] = _s(rec.get(f))
                yield row
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[WikidataEnrichmentRow],
        ctx: PipelineContext,
    ) -> None:
        params = [{c: getattr(r, c) for c in COLUMNS} for r in rows]
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
        description="Land Wikidata enrichment cache JSON into bronze.bronze_jurisdiction_wikidata_enrichment"
    )
    parser.add_argument("--cache-dir", type=Path, help="Override cache dir (default data/cache/wikidata)")
    parser.add_argument("--limit", type=int, help="Load only the first N rows")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE before loading")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = WikidataEnrichmentPipeline(cache_dir=args.cache_dir, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

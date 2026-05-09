#!/usr/bin/env python3
"""
Create / repair bronze Census gazetteer + jurisdiction *_wikidata tables on Postgres (Neon or local).

Idempotent DDL only — **no pg_dump**. Run before:
  - scripts/datasources/census/load_census_gazetteer.py
  - scripts/datasources/wikidata/load_jurisdictions_wikidata.py

Usage:
  .venv/bin/python scripts/deployment/neon/ensure_bronze_jurisdictions_cloud.py
  DATABASE_URL='postgresql://...' .venv/bin/python ... --gazetteer-types states counties
  OPEN_NAVIGATOR_DATABASE_URL='postgresql://...' .venv/bin/python ... --schema-only

Env for URL resolution: scripts/database/target_database_url.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from scripts.database.target_database_url import resolve_target_database_url  # noqa: E402
from scripts.datasources.census.load_census_gazetteer import TYPES as GAZETTEER_TYPES  # noqa: E402


_SEED_MAPPING = (
    ("state", "bronze.bronze_jurisdictions_states", "bronze.bronze_jurisdictions_states_wikidata"),
    ("county", "bronze.bronze_jurisdictions_counties", "bronze.bronze_jurisdictions_counties_wikidata"),
    ("city", "bronze.bronze_jurisdictions_municipalities", "bronze.bronze_jurisdictions_municipalities_wikidata"),
    ("school_district", "bronze.bronze_jurisdictions_school_districts", "bronze.bronze_jurisdictions_school_districts_wikidata"),
)

_COMMON_EXTRA_COLS = [
    ("wikidata_id", "VARCHAR(64)"),
    ("official_website", "TEXT"),
    ("official_image_url", "TEXT"),
    ("page_banner_image", "TEXT"),
    ("locator_map_image", "TEXT"),
    ("youtube_channel_id", "VARCHAR(128)"),
    ("youtube_channel_url", "TEXT"),
    ("facebook_username", "TEXT"),
    ("facebook_url", "TEXT"),
    ("twitter_username", "TEXT"),
    ("twitter_url", "TEXT"),
    ("population", "BIGINT"),
    ("area_sq_km", "DOUBLE PRECISION"),
    ("per_capita_income", "BIGINT"),
    ("number_of_households", "BIGINT"),
    ("median_age", "DOUBLE PRECISION"),
    ("time_zone", "TEXT"),
    ("local_dialing_code", "TEXT"),
    ("google_maps_customer_id", "TEXT"),
    ("language_of_work_or_name", "TEXT"),
    ("head_of_government", "TEXT"),
    ("head_of_government_position", "TEXT"),
    ("head_of_government_start_time", "TEXT"),
    ("postal_codes", "JSONB"),
    ("latitude", "DOUBLE PRECISION"),
    ("longitude", "DOUBLE PRECISION"),
    ("wikidata_fetched_at", "TIMESTAMP"),
    ("wikidata_last_updated", "TIMESTAMP"),
    ("wikidata_fips_code", "TEXT"),
    ("wikidata_geoid", "TEXT"),
    ("wikidata_gnis_id", "TEXT"),
    ("wikidata_nces_id", "TEXT"),
]

_STATE_EXTRA_COLS = [
    ("jurisdiction_label", "TEXT"),
    ("jurisdiction_description", "TEXT"),
    ("jurisdiction_aliases", "JSONB"),
    ("native_label", "TEXT"),
    ("nickname", "JSONB"),
    ("short_name", "JSONB"),
    ("demonym", "JSONB"),
    ("official_language", "JSONB"),
    ("motto", "TEXT"),
    ("anthem", "JSONB"),
    ("inception_date", "TEXT"),
    ("capital", "JSONB"),
    ("iso_3166_2", "VARCHAR(16)"),
    ("pronunciation_audio", "TEXT"),
    ("geoshape", "TEXT"),
]


def _split_pg_ddl(sql: str) -> list[str]:
    parts: list[str] = []
    for chunk in sql.split(";"):
        s = chunk.strip()
        if s:
            parts.append(s)
    return parts


def apply_gazetteer_ddl(conn, gazetteer_types: list[str]) -> None:
    cur = conn.cursor()
    for jtype in gazetteer_types:
        ddl = GAZETTEER_TYPES[jtype]["ddl"]
        for stmt in _split_pg_ddl(ddl):
            cur.execute(stmt + ";")
    conn.commit()
    cur.close()
    logger.info(f"Applied Census gazetteer DDL for: {', '.join(gazetteer_types)}")


def ensure_wikidata_tables(conn) -> None:
    cur = conn.cursor()
    for task, base_fq, wikt_fq in _SEED_MAPPING:
        schema_b, tbl_b = base_fq.split(".", 1)
        schema_w, tbl_w = wikt_fq.split(".", 1)
        cur.execute(
            f'CREATE TABLE IF NOT EXISTS "{schema_w}"."{tbl_w}" '
            f'(LIKE "{schema_b}"."{tbl_b}" INCLUDING ALL);'
        )
        cols = list(_COMMON_EXTRA_COLS)
        if task == "state":
            cols.extend(_STATE_EXTRA_COLS)

        seen: set[str] = set()
        for col_name, pg_type in cols:
            if col_name in seen:
                continue
            seen.add(col_name)
            cur.execute(
                f'ALTER TABLE "{schema_w}"."{tbl_w}" ADD COLUMN IF NOT EXISTS "{col_name}" {pg_type};'
            )
    conn.commit()
    cur.close()
    logger.success("Ensured bronze *_wikidata mirror tables (LIKE base + enrichment columns)")


def main() -> None:
    default_types = ",".join(GAZETTEER_TYPES.keys())

    parser = argparse.ArgumentParser(
        description="Apply bronze gazetteer + jurisdiction *_wikidata DDL (Neon-ready, idempotent)."
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="PostgreSQL URL; default from OPEN_NAVIGATOR_DATABASE_URL → NEON_* → localhost",
    )
    parser.add_argument(
        "--gazetteer-types",
        default="",
        help=f"Comma subset of Gazetteer CSV types (default: all). Choices: {default_types}",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="DDL only; caller runs gazetteer + Wikidata loaders separately",
    )
    args = parser.parse_args()

    url = args.database_url.strip() or resolve_target_database_url()

    gazetteer_types = sorted(GAZETTEER_TYPES.keys())
    if args.gazetteer_types.strip():
        gazetteer_types = [x.strip() for x in args.gazetteer_types.split(",") if x.strip()]
        unknown = [t for t in gazetteer_types if t not in GAZETTEER_TYPES]
        if unknown:
            raise SystemExit(f"Unknown gazetteer type(s): {unknown}. Choices: {list(GAZETTEER_TYPES.keys())}")

    at = url.find("@")
    logger.info(f"Ensuring DDL (logged host): …{url[at:] if at > 0 else url}")

    conn = psycopg2.connect(url)
    try:
        apply_gazetteer_ddl(conn, gazetteer_types)
        ensure_wikidata_tables(conn)
        if not args.schema_only:
            logger.info(
                "Next: populate rows — "
                ".venv/bin/python scripts/datasources/census/load_census_gazetteer.py … "
                "then scripts/datasources/wikidata/… "
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Materialize Wikidata-enriched jurisdiction tables into the bronze schema.

Creates (or replaces) the following tables in the *open_navigator* database:
- bronze.bronze_jurisdictions_states_wikidata
- bronze.bronze_jurisdictions_counties_wikidata
- bronze.bronze_jurisdictions_municipalities_wikidata
- bronze.bronze_jurisdictions_school_districts_wikidata

These tables join Census Gazetteer bronze tables to `jurisdictions_wikidata`
(populated by `scripts/datasources/wikidata/load_jurisdictions_wikidata.py`).

They are intentionally separate tables (suffix `_wikidata`) so we do not mutate
the canonical Census bronze tables.
"""

import os
import argparse
from typing import Iterable

import psycopg2
from loguru import logger
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv(
    "NEON_DATABASE_URL_DEV",
    "postgresql://postgres:password@localhost:5433/open_navigator",
)


DDL = """
CREATE SCHEMA IF NOT EXISTS bronze;
"""


def _exec(conn, sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def _replace_table(conn, fqtn: str, select_sql: str) -> None:
    schema, name = fqtn.split(".", 1)
    with conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS "{schema}"."{name}" CASCADE;')
        cur.execute(f'CREATE TABLE "{schema}"."{name}" AS {select_sql}')
    conn.commit()


def _create_indexes(conn) -> None:
    stmts: Iterable[str] = [
        "CREATE INDEX IF NOT EXISTS idx_bjsw_geoid ON bronze.bronze_jurisdictions_states_wikidata(geoid);",
        "CREATE INDEX IF NOT EXISTS idx_bjcw_geoid ON bronze.bronze_jurisdictions_counties_wikidata(geoid);",
        "CREATE INDEX IF NOT EXISTS idx_bjmw_geoid ON bronze.bronze_jurisdictions_municipalities_wikidata(geoid);",
        "CREATE INDEX IF NOT EXISTS idx_bjsdw_geoid ON bronze.bronze_jurisdictions_school_districts_wikidata(geoid);",
        "CREATE INDEX IF NOT EXISTS idx_bjcw_wikidata_id ON bronze.bronze_jurisdictions_counties_wikidata(wikidata_id);",
        "CREATE INDEX IF NOT EXISTS idx_bjmw_wikidata_id ON bronze.bronze_jurisdictions_municipalities_wikidata(wikidata_id);",
        "CREATE INDEX IF NOT EXISTS idx_bjsdw_wikidata_id ON bronze.bronze_jurisdictions_school_districts_wikidata(wikidata_id);",
    ]
    with conn.cursor() as cur:
        for s in stmts:
            cur.execute(s)
    conn.commit()


SELECT_STATES = """
SELECT
  s.*,
  w.wikidata_id,
  w.jurisdiction_label,
  w.jurisdiction_description,
  w.jurisdiction_aliases,
  w.native_label,
  w.nickname,
  w.short_name,
  w.demonym,
  w.official_language,
  w.motto,
  w.anthem,
  w.inception_date,
  w.capital,
  w.iso_3166_2,
  w.pronunciation_audio,
  w.geoshape,
  w.official_website,
  w.official_image_url,
  w.page_banner_image,
  w.locator_map_image,
  w.youtube_channel_id,
  w.youtube_channel_url,
  w.facebook_username,
  w.facebook_url,
  w.twitter_username,
  w.twitter_url,
  w.population,
  w.area_sq_km,
  w.per_capita_income,
  w.number_of_households,
  w.median_age,
  w.time_zone,
  w.local_dialing_code,
  w.google_maps_customer_id,
  w.language_of_work_or_name,
  w.head_of_government,
  w.head_of_government_position,
  w.head_of_government_start_time,
  w.postal_codes,
  w.latitude,
  w.longitude,
  w.fips_code AS wikidata_fips_code,
  w.geoid    AS wikidata_geoid,
  w.fetched_at AS wikidata_fetched_at,
  w.last_updated AS wikidata_last_updated
FROM bronze.bronze_jurisdictions_states s
LEFT JOIN jurisdictions_wikidata w
  ON w.jurisdiction_type = 'state'
 AND w.geoid = s.geoid
"""


SELECT_COUNTIES = """
SELECT
  c.*,
  w.wikidata_id,
  w.official_website,
  w.official_image_url,
  w.page_banner_image,
  w.locator_map_image,
  w.youtube_channel_id,
  w.youtube_channel_url,
  w.facebook_username,
  w.facebook_url,
  w.twitter_username,
  w.twitter_url,
  w.population,
  w.area_sq_km,
  w.per_capita_income,
  w.number_of_households,
  w.median_age,
  w.time_zone,
  w.local_dialing_code,
  w.google_maps_customer_id,
  w.language_of_work_or_name,
  w.head_of_government,
  w.head_of_government_position,
  w.head_of_government_start_time,
  w.postal_codes,
  w.latitude,
  w.longitude,
  w.fips_code AS wikidata_fips_code,
  w.geoid    AS wikidata_geoid,
  w.fetched_at AS wikidata_fetched_at,
  w.last_updated AS wikidata_last_updated
FROM bronze.bronze_jurisdictions_counties c
LEFT JOIN jurisdictions_wikidata w
  ON w.jurisdiction_type = 'county'
 AND w.geoid = c.geoid
"""


SELECT_SCHOOL_DISTRICTS = """
SELECT
  sd.*,
  w.wikidata_id,
  w.official_website,
  w.official_image_url,
  w.page_banner_image,
  w.locator_map_image,
  w.youtube_channel_id,
  w.youtube_channel_url,
  w.facebook_username,
  w.facebook_url,
  w.twitter_username,
  w.twitter_url,
  w.population,
  w.area_sq_km,
  w.per_capita_income,
  w.number_of_households,
  w.median_age,
  w.time_zone,
  w.local_dialing_code,
  w.google_maps_customer_id,
  w.language_of_work_or_name,
  w.head_of_government,
  w.head_of_government_position,
  w.head_of_government_start_time,
  w.postal_codes,
  w.latitude,
  w.longitude,
  w.nces_id AS wikidata_nces_id,
  w.geoid   AS wikidata_geoid,
  w.fetched_at AS wikidata_fetched_at,
  w.last_updated AS wikidata_last_updated
FROM bronze.bronze_jurisdictions_school_districts sd
LEFT JOIN jurisdictions_wikidata w
  ON w.jurisdiction_type = 'school_district'
 AND COALESCE(w.nces_id, w.geoid) = sd.geoid
"""


SELECT_MUNICIPALITIES = """
WITH muni_norm AS (
  SELECT
    m.*,
    LOWER(
      REGEXP_REPLACE(
        REGEXP_REPLACE(TRIM(m.name), '\\s+(city|town|village|borough|cdp)$', '', 1, 0, 'i'),
        '\\s+(?:town|city)\\s*', ' ', 1, 0, 'i'
      )
    ) AS name_clean
  FROM bronze.bronze_jurisdictions_municipalities m
),
wiki_norm AS (
  SELECT
    w.*,
    LOWER(
      REGEXP_REPLACE(
        REGEXP_REPLACE(TRIM(w.jurisdiction_name), '\\s+(city|town|village|borough|cdp)$', '', 1, 0, 'i'),
        '\\s+(?:town|city)\\s*', ' ', 1, 0, 'i'
      )
    ) AS name_clean
  FROM jurisdictions_wikidata w
  WHERE w.jurisdiction_type IN ('city', 'town')
)
SELECT
  m.*,
  w.wikidata_id,
  w.official_website,
  w.official_image_url,
  w.page_banner_image,
  w.locator_map_image,
  w.youtube_channel_id,
  w.youtube_channel_url,
  w.facebook_username,
  w.facebook_url,
  w.twitter_username,
  w.twitter_url,
  w.population,
  w.area_sq_km,
  w.per_capita_income,
  w.number_of_households,
  w.median_age,
  w.time_zone,
  w.local_dialing_code,
  w.google_maps_customer_id,
  w.language_of_work_or_name,
  w.head_of_government,
  w.head_of_government_position,
  w.head_of_government_start_time,
  w.postal_codes,
  w.latitude,
  w.longitude,
  w.fips_code AS wikidata_fips_code,
  w.gnis_id   AS wikidata_gnis_id,
  w.geoid     AS wikidata_geoid,
  w.fetched_at AS wikidata_fetched_at,
  w.last_updated AS wikidata_last_updated
FROM muni_norm m
LEFT JOIN wiki_norm w
  ON w.state_code = m.usps
 AND w.name_clean = m.name_clean
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Materialize Wikidata-enriched bronze jurisdiction tables")
    ap.add_argument(
        "--require-wikidata",
        action="store_true",
        help="Fail if jurisdictions_wikidata is empty/missing",
    )
    args = ap.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        _exec(conn, DDL)

        if args.require_wikidata:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('public.jurisdictions_wikidata'), (SELECT COUNT(*) FROM jurisdictions_wikidata)"
                )
                rel, n = cur.fetchone()
            if rel is None or n == 0:
                raise RuntimeError("jurisdictions_wikidata missing or empty; run load_jurisdictions_wikidata.py first")

        logger.info("Creating bronze.bronze_jurisdictions_states_wikidata…")
        _replace_table(conn, "bronze.bronze_jurisdictions_states_wikidata", SELECT_STATES)

        logger.info("Creating bronze.bronze_jurisdictions_counties_wikidata…")
        _replace_table(conn, "bronze.bronze_jurisdictions_counties_wikidata", SELECT_COUNTIES)

        logger.info("Creating bronze.bronze_jurisdictions_school_districts_wikidata…")
        _replace_table(conn, "bronze.bronze_jurisdictions_school_districts_wikidata", SELECT_SCHOOL_DISTRICTS)

        logger.info("Creating bronze.bronze_jurisdictions_municipalities_wikidata…")
        _replace_table(conn, "bronze.bronze_jurisdictions_municipalities_wikidata", SELECT_MUNICIPALITIES)

        _create_indexes(conn)
        logger.success("✓ Done")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())


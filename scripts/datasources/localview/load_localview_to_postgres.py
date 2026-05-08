#!/usr/bin/env python3
"""
Load LocalView Meeting Data into bronze.bronze_events_localview table

This script reads all LocalView parquet files and inserts meeting data
into the bronze.bronze_events_localview table following the medallion architecture.

Uniqueness is enforced on datasource_id (YouTube video ID). event_id is a
BIGSERIAL surrogate key — never hash-derived, which was non-deterministic.

Usage:
    python3 scripts/datasources/localview/load_localview_to_postgres.py
    python3 scripts/datasources/localview/load_localview_to_postgres.py --truncate
    python3 scripts/datasources/localview/load_localview_to_postgres.py --truncate --year 2023
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')
LOCALVIEW_DIR = Path('data/cache/localview')

CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_events_localview (
        event_id          BIGSERIAL PRIMARY KEY,
        event_date        DATE,
        jurisdiction_name VARCHAR(500),
        jurisdiction_type VARCHAR(100),
        city              VARCHAR(255),
        city_name         VARCHAR(255),
        state_code        VARCHAR(2),
        state             VARCHAR(100),
        meeting_type      VARCHAR(255),
        title             VARCHAR(500),
        video_url         TEXT,
        datasource        VARCHAR(100),
        datasource_id     VARCHAR(255) NOT NULL,
        loaded_at         TIMESTAMP DEFAULT NOW(),

        -- Raw LocalView columns (kept for lineage/debugging)
        st_fips                  VARCHAR(10),
        place_govt               VARCHAR(255),
        channel_title            VARCHAR(500),
        vid_title                VARCHAR(500),
        vid_desc                 TEXT,
        vid_length_min           DOUBLE PRECISION,
        vid_upload_date          TIMESTAMP,
        vid_livestreamed         BOOLEAN,
        vid_views                DOUBLE PRECISION,
        vid_likes                DOUBLE PRECISION,
        vid_dislikes             DOUBLE PRECISION,
        vid_comments             DOUBLE PRECISION,
        vid_favorites            DOUBLE PRECISION,
        meeting_date_raw         VARCHAR(50),
        caption_text             TEXT,
        caption_text_clean       TEXT,
        channel_type             VARCHAR(100),
        acs_18_amind             DOUBLE PRECISION,
        acs_18_asian             DOUBLE PRECISION,
        acs_18_black             DOUBLE PRECISION,
        acs_18_hispanic          DOUBLE PRECISION,
        acs_18_median_age        DOUBLE PRECISION,
        acs_18_median_gross_rent DOUBLE PRECISION,
        acs_18_median_hh_inc     DOUBLE PRECISION,
        acs_18_nhapi             DOUBLE PRECISION,
        acs_18_pop               DOUBLE PRECISION,
        acs_18_white             DOUBLE PRECISION,

        CONSTRAINT uq_localview_datasource_id UNIQUE (datasource_id)
    );

    CREATE INDEX IF NOT EXISTS idx_belv_event_date  ON bronze.bronze_events_localview(event_date);
    CREATE INDEX IF NOT EXISTS idx_belv_state_code  ON bronze.bronze_events_localview(state_code);
    CREATE INDEX IF NOT EXISTS idx_belv_datasource  ON bronze.bronze_events_localview(datasource);
"""

JURISDICTION_TYPE_MAP = {
    # Municipal
    'MUNICIPAL COUNCIL':              'city',
    'BOARD OF ALDERMEN':              'city',
    'CITY COMMISSION':                'city',
    'BOARD OF TRUSTEES':              'city',
    'BOARD OF HEALTH':                'city',
    'PARKS/REC BOARD/COMMISSION':     'city',
    'PLANNING/ZONING BOARD/COMMISSION': 'city',
    'COMMITTEE':                      'city',
    'SPECIAL COMMISSION':             'city',
    'DEVELOPMENT CORPORATION':        'city',
    'HOUSING AUTHORITY':              'city',
    'OTHER BOARD':                    'city',
    # Town / Township
    'BOARD OF SELECTMEN':             'town',
    'TOWN BOARD':                     'town',
    'VILLAGE BOARD':                  'village',
    # County
    'COUNTY COMMISSION':              'county',
    'COUNTY BOARD':                   'county',
    'COUNTY COUNCIL':                 'county',
    'BOARD OF COMMISSIONERS':         'county',
    'BOARD OF SUPERVISORS':           'county',
    # School district
    'SCHOOL BOARD':                   'school_district',
    'BOARD OF EDUCATION':             'school_district',
}


def infer_jurisdiction_type(place_govt: Any) -> str:
    if pd.isna(place_govt) or not place_govt:
        return 'unknown'
    return JURISDICTION_TYPE_MAP.get(str(place_govt).strip().upper(), 'city')


STATE_ABBREV = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
}


def get_state_abbrev(state_name: str) -> Optional[str]:
    if pd.isna(state_name):
        return None
    return STATE_ABBREV.get(state_name, state_name[:2].upper())


def row_to_event(row: pd.Series) -> Dict[str, Any]:
    event_date = None
    if pd.notna(row.get('meeting_date')):
        try:
            event_date = pd.to_datetime(row['meeting_date']).date()
        except Exception:
            pass

    vid_id = row.get('vid_id')
    video_url = f"https://www.youtube.com/watch?v={vid_id}" if pd.notna(vid_id) else None

    state_name = row.get('state_name')
    state_code = get_state_abbrev(state_name)

    place_name = row.get('place_name')
    title = row.get('vid_title')
    if pd.isna(title) or not title:
        date_str = event_date.strftime('%B %d, %Y') if event_date else ''
        title = f"{place_name} Meeting - {date_str}" if date_str else f"{place_name} Meeting"

    return {
        'event_date':        event_date,
        'jurisdiction_name': place_name,
        'jurisdiction_type': infer_jurisdiction_type(row.get('place_govt')),
        'city':              place_name,
        'city_name':         place_name,
        'state_code':        state_code,
        'state':             state_name,
        'meeting_type':      row.get('place_govt', 'City Council'),
        'title':             (title or '')[:500],
        'video_url':         video_url,
        'datasource':        'localview',
        'datasource_id':     vid_id,
        'loaded_at':         datetime.now(),
        'st_fips':           row.get('st_fips'),
        'place_govt':        row.get('place_govt'),
        'channel_title':     row.get('channel_title'),
        'vid_title':         row.get('vid_title'),
        'vid_desc':          row.get('vid_desc'),
        'vid_length_min':    row.get('vid_length_min'),
        'vid_upload_date':   pd.to_datetime(row.get('vid_upload_date'), errors='coerce') if row.get('vid_upload_date') is not None else None,
        'vid_livestreamed':  bool(row.get('vid_livestreamed')) if pd.notna(row.get('vid_livestreamed')) else None,
        'vid_views':         row.get('vid_views'),
        'vid_likes':         row.get('vid_likes'),
        'vid_dislikes':      row.get('vid_dislikes'),
        'vid_comments':      row.get('vid_comments'),
        'vid_favorites':     row.get('vid_favorites'),
        'meeting_date_raw':  str(row.get('meeting_date')) if pd.notna(row.get('meeting_date')) else None,
        'caption_text':      row.get('caption_text'),
        'caption_text_clean': row.get('caption_text_clean'),
        'channel_type':      row.get('channel_type'),
        'acs_18_amind':      row.get('acs_18_amind'),
        'acs_18_asian':      row.get('acs_18_asian'),
        'acs_18_black':      row.get('acs_18_black'),
        'acs_18_hispanic':   row.get('acs_18_hispanic'),
        'acs_18_median_age': row.get('acs_18_median_age'),
        'acs_18_median_gross_rent': row.get('acs_18_median_gross_rent'),
        'acs_18_median_hh_inc':     row.get('acs_18_median_hh_inc'),
        'acs_18_nhapi':      row.get('acs_18_nhapi'),
        'acs_18_pop':        row.get('acs_18_pop'),
        'acs_18_white':      row.get('acs_18_white'),
    }


INSERT_SQL = """
    INSERT INTO bronze.bronze_events_localview (
        event_date, jurisdiction_name, jurisdiction_type,
        city, city_name, state_code, state, meeting_type,
        title, video_url, datasource, datasource_id, loaded_at,
        st_fips, place_govt, channel_title, vid_title, vid_desc,
        vid_length_min, vid_upload_date, vid_livestreamed,
        vid_views, vid_likes, vid_dislikes, vid_comments, vid_favorites,
        meeting_date_raw, caption_text, caption_text_clean, channel_type,
        acs_18_amind, acs_18_asian, acs_18_black, acs_18_hispanic,
        acs_18_median_age, acs_18_median_gross_rent, acs_18_median_hh_inc,
        acs_18_nhapi, acs_18_pop, acs_18_white
    ) VALUES (
        %(event_date)s, %(jurisdiction_name)s, %(jurisdiction_type)s,
        %(city)s, %(city_name)s, %(state_code)s, %(state)s, %(meeting_type)s,
        %(title)s, %(video_url)s, %(datasource)s, %(datasource_id)s, %(loaded_at)s,
        %(st_fips)s, %(place_govt)s, %(channel_title)s, %(vid_title)s, %(vid_desc)s,
        %(vid_length_min)s, %(vid_upload_date)s, %(vid_livestreamed)s,
        %(vid_views)s, %(vid_likes)s, %(vid_dislikes)s, %(vid_comments)s, %(vid_favorites)s,
        %(meeting_date_raw)s, %(caption_text)s, %(caption_text_clean)s, %(channel_type)s,
        %(acs_18_amind)s, %(acs_18_asian)s, %(acs_18_black)s, %(acs_18_hispanic)s,
        %(acs_18_median_age)s, %(acs_18_median_gross_rent)s, %(acs_18_median_hh_inc)s,
        %(acs_18_nhapi)s, %(acs_18_pop)s, %(acs_18_white)s
    )
    ON CONFLICT (datasource_id) DO UPDATE SET
        event_date        = COALESCE(EXCLUDED.event_date,        bronze_events_localview.event_date),
        jurisdiction_name = COALESCE(EXCLUDED.jurisdiction_name, bronze_events_localview.jurisdiction_name),
        city              = COALESCE(EXCLUDED.city,              bronze_events_localview.city),
        city_name         = COALESCE(EXCLUDED.city_name,         bronze_events_localview.city_name),
        state_code        = COALESCE(EXCLUDED.state_code,        bronze_events_localview.state_code),
        state             = COALESCE(EXCLUDED.state,             bronze_events_localview.state),
        meeting_type      = COALESCE(EXCLUDED.meeting_type,      bronze_events_localview.meeting_type),
        title             = COALESCE(EXCLUDED.title,             bronze_events_localview.title),
        video_url         = COALESCE(EXCLUDED.video_url,         bronze_events_localview.video_url),
        st_fips           = COALESCE(EXCLUDED.st_fips,           bronze_events_localview.st_fips),
        place_govt        = COALESCE(EXCLUDED.place_govt,        bronze_events_localview.place_govt),
        channel_title     = COALESCE(EXCLUDED.channel_title,     bronze_events_localview.channel_title),
        vid_title         = COALESCE(EXCLUDED.vid_title,         bronze_events_localview.vid_title),
        vid_desc          = COALESCE(EXCLUDED.vid_desc,          bronze_events_localview.vid_desc),
        vid_length_min    = COALESCE(EXCLUDED.vid_length_min,    bronze_events_localview.vid_length_min),
        vid_upload_date   = COALESCE(EXCLUDED.vid_upload_date,   bronze_events_localview.vid_upload_date),
        vid_livestreamed  = COALESCE(EXCLUDED.vid_livestreamed,  bronze_events_localview.vid_livestreamed),
        vid_views         = COALESCE(EXCLUDED.vid_views,         bronze_events_localview.vid_views),
        vid_likes         = COALESCE(EXCLUDED.vid_likes,         bronze_events_localview.vid_likes),
        vid_dislikes      = COALESCE(EXCLUDED.vid_dislikes,      bronze_events_localview.vid_dislikes),
        vid_comments      = COALESCE(EXCLUDED.vid_comments,      bronze_events_localview.vid_comments),
        vid_favorites     = COALESCE(EXCLUDED.vid_favorites,     bronze_events_localview.vid_favorites),
        meeting_date_raw  = COALESCE(EXCLUDED.meeting_date_raw,  bronze_events_localview.meeting_date_raw),
        caption_text      = COALESCE(EXCLUDED.caption_text,      bronze_events_localview.caption_text),
        caption_text_clean= COALESCE(EXCLUDED.caption_text_clean,bronze_events_localview.caption_text_clean),
        channel_type      = COALESCE(EXCLUDED.channel_type,      bronze_events_localview.channel_type),
        acs_18_amind      = COALESCE(EXCLUDED.acs_18_amind,      bronze_events_localview.acs_18_amind),
        acs_18_asian      = COALESCE(EXCLUDED.acs_18_asian,      bronze_events_localview.acs_18_asian),
        acs_18_black      = COALESCE(EXCLUDED.acs_18_black,      bronze_events_localview.acs_18_black),
        acs_18_hispanic   = COALESCE(EXCLUDED.acs_18_hispanic,   bronze_events_localview.acs_18_hispanic),
        acs_18_median_age = COALESCE(EXCLUDED.acs_18_median_age, bronze_events_localview.acs_18_median_age),
        acs_18_median_gross_rent = COALESCE(EXCLUDED.acs_18_median_gross_rent, bronze_events_localview.acs_18_median_gross_rent),
        acs_18_median_hh_inc     = COALESCE(EXCLUDED.acs_18_median_hh_inc,    bronze_events_localview.acs_18_median_hh_inc),
        acs_18_nhapi      = COALESCE(EXCLUDED.acs_18_nhapi,      bronze_events_localview.acs_18_nhapi),
        acs_18_pop        = COALESCE(EXCLUDED.acs_18_pop,        bronze_events_localview.acs_18_pop),
        acs_18_white      = COALESCE(EXCLUDED.acs_18_white,      bronze_events_localview.acs_18_white),
        loaded_at         = NOW()
"""


def load_parquet_file(filepath: Path, conn, batch_size: int = 1000) -> int:
    logger.info(f"Loading {filepath.name}...")
    df = pd.read_parquet(filepath)
    logger.info(f"  Rows in file: {len(df):,}")

    df_valid = df[df['meeting_date'].notna() & df['vid_id'].notna()].copy()
    logger.info(f"  Valid rows (have date + video ID): {len(df_valid):,}")

    if df_valid.empty:
        return 0

    events = [row_to_event(row) for _, row in df_valid.iterrows()]

    cursor = conn.cursor()
    inserted = 0
    try:
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            execute_batch(cursor, INSERT_SQL, batch, page_size=batch_size)
            inserted += len(batch)
            conn.commit()
            if i % 10000 == 0 and i > 0:
                logger.info(f"  Processed {i:,} / {len(events):,}...")
        logger.success(f"  ✓ {inserted:,} rows upserted from {filepath.name}")
        return inserted
    except Exception as e:
        conn.rollback()
        logger.error(f"  ✗ Error on {filepath.name}: {e}")
        raise
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description="Load LocalView parquet files → bronze.bronze_events_localview")
    parser.add_argument('--truncate', action='store_true', help='Drop and recreate the table before loading (full reload)')
    parser.add_argument('--year', type=int, help='Load only a specific year (e.g. --year 2023)')
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("LOCALVIEW → POSTGRES LOADER")
    logger.info("=" * 80)

    parquet_files = sorted(LOCALVIEW_DIR.glob('meetings.*.parquet'))
    if args.year:
        parquet_files = [f for f in parquet_files if f.name == f'meetings.{args.year}.parquet']
    logger.info(f"Found {len(parquet_files)} parquet file(s) to load")

    if not parquet_files:
        logger.error("No parquet files found — check LOCALVIEW_DIR.")
        return 1

    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.success("✓ Connected to database")
        cur = conn.cursor()

        if args.truncate:
            logger.warning("--truncate: dropping bronze.bronze_events_localview...")
            cur.execute("DROP TABLE IF EXISTS bronze.bronze_events_localview CASCADE;")
            conn.commit()
            logger.info("Table dropped.")

        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        cur.close()
        logger.info("✓ bronze.bronze_events_localview ready")
    except Exception as e:
        logger.error(f"✗ Database setup failed: {e}")
        return 1

    total = 0
    start = datetime.now()
    try:
        for filepath in parquet_files:
            total += load_parquet_file(filepath, conn)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_events_localview")
        final_count = cur.fetchone()[0]
        cur.close()

        duration = (datetime.now() - start).total_seconds()
        logger.success("=" * 80)
        logger.success(f"✓ Done. {total:,} rows upserted | {final_count:,} total in table | {duration:.1f}s")
        logger.success("=" * 80)
        return 0
    except Exception as e:
        logger.error(f"✗ Load failed: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

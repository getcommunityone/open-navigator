#!/usr/bin/env python3
"""
Load jurisdiction discovery/enrichment fields into public.jurisdiction.

Reads data/gold/jurisdictions_details.parquet and upserts discovery metadata
(YouTube channels, websites, meeting platforms) onto jurisdiction rows keyed by
jurisdiction_id.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')
PARQUET_FILE = Path('data/gold/jurisdictions_details.parquet')


def create_table(conn):
    """Ensure jurisdiction has enrichment columns (migration 038)."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS jurisdiction_id VARCHAR(50);
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS discovery_timestamp TIMESTAMP;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS website_url TEXT;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS youtube_channel_count INTEGER DEFAULT 0;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS youtube_channels JSONB;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS meeting_platform_count INTEGER DEFAULT 0;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS meeting_platforms JSONB;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS social_media JSONB;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS agenda_portal_count INTEGER DEFAULT 0;
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS discovery_status VARCHAR(50);
            ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS in_localview BOOLEAN DEFAULT FALSE;
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_jurisdiction_jurisdiction_id
            ON jurisdiction (jurisdiction_id)
            WHERE jurisdiction_id IS NOT NULL AND BTRIM(jurisdiction_id) <> ''
        """)
        conn.commit()
        logger.success("✓ Table jurisdiction enrichment columns verified")
    except Exception as e:
        conn.rollback()
        logger.error(f"✗ Failed to verify jurisdiction columns: {e}")
        raise
    finally:
        cursor.close()


def load_data(conn, parquet_file: Path, batch_size: int = 1000):
    """Load parquet rows into jurisdiction."""
    logger.info(f"Loading data from {parquet_file.name}...")
    df = pd.read_parquet(parquet_file)
    logger.info(f"  Rows in file: {len(df):,}")
    df['discovery_timestamp'] = pd.to_datetime(df['discovery_timestamp'])

    records = []
    for _, row in df.iterrows():
        youtube_channels = row['youtube_channels'] if pd.notna(row['youtube_channels']) else '[]'
        if isinstance(youtube_channels, str):
            try:
                import ast
                youtube_channels = json.dumps(ast.literal_eval(youtube_channels))
            except Exception:
                youtube_channels = '[]'
        elif isinstance(youtube_channels, (list, dict)):
            youtube_channels = json.dumps(youtube_channels)

        meeting_platforms = row['meeting_platforms'] if pd.notna(row['meeting_platforms']) else '[]'
        if isinstance(meeting_platforms, str):
            try:
                import ast
                meeting_platforms = json.dumps(ast.literal_eval(meeting_platforms))
            except Exception:
                meeting_platforms = '[]'
        elif isinstance(meeting_platforms, (list, dict)):
            meeting_platforms = json.dumps(meeting_platforms)

        social_media = row['social_media'] if pd.notna(row['social_media']) else '{}'
        if isinstance(social_media, str):
            try:
                import ast
                social_media = json.dumps(ast.literal_eval(social_media))
            except Exception:
                social_media = '{}'
        elif isinstance(social_media, dict):
            social_media = json.dumps(social_media)

        records.append({
            'jurisdiction_id': row['jurisdiction_id'],
            'name': row['jurisdiction_name'],
            'state_code': row['state_code'],
            'state': row['state'],
            'type': row['jurisdiction_type'],
            'population': int(row['population']) if pd.notna(row['population']) else 0,
            'discovery_timestamp': row['discovery_timestamp'],
            'website_url': row['website_url'] if pd.notna(row['website_url']) else None,
            'youtube_channel_count': int(row['youtube_channel_count']) if pd.notna(row['youtube_channel_count']) else 0,
            'youtube_channels': youtube_channels,
            'meeting_platform_count': int(row['meeting_platform_count']) if pd.notna(row['meeting_platform_count']) else 0,
            'meeting_platforms': meeting_platforms,
            'social_media': social_media,
            'agenda_portal_count': int(row['agenda_portal_count']) if pd.notna(row['agenda_portal_count']) else 0,
            'discovery_status': row['status'] if pd.notna(row['status']) else 'unknown',
            'in_localview': bool(row['in_localview']) if pd.notna(row['in_localview']) else False,
        })

    insert_query = """
        INSERT INTO jurisdiction (
            jurisdiction_id, name, state_code, state, type,
            population, discovery_timestamp, website_url,
            youtube_channel_count, youtube_channels,
            meeting_platform_count, meeting_platforms,
            social_media, agenda_portal_count, discovery_status, in_localview,
            source
        ) VALUES (
            %(jurisdiction_id)s, %(name)s, %(state_code)s, %(state)s, %(type)s,
            %(population)s, %(discovery_timestamp)s, %(website_url)s,
            %(youtube_channel_count)s, %(youtube_channels)s::jsonb,
            %(meeting_platform_count)s, %(meeting_platforms)s::jsonb,
            %(social_media)s::jsonb, %(agenda_portal_count)s, %(discovery_status)s, %(in_localview)s,
            'discovery'
        )
        ON CONFLICT (jurisdiction_id)
        DO UPDATE SET
            name = EXCLUDED.name,
            state_code = EXCLUDED.state_code,
            state = EXCLUDED.state,
            type = EXCLUDED.type,
            population = EXCLUDED.population,
            discovery_timestamp = EXCLUDED.discovery_timestamp,
            website_url = EXCLUDED.website_url,
            youtube_channel_count = EXCLUDED.youtube_channel_count,
            youtube_channels = EXCLUDED.youtube_channels,
            meeting_platform_count = EXCLUDED.meeting_platform_count,
            meeting_platforms = EXCLUDED.meeting_platforms,
            social_media = EXCLUDED.social_media,
            agenda_portal_count = EXCLUDED.agenda_portal_count,
            discovery_status = EXCLUDED.discovery_status,
            in_localview = EXCLUDED.in_localview,
            last_updated = CURRENT_TIMESTAMP
    """

    cursor = conn.cursor()
    inserted = 0
    try:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            execute_batch(cursor, insert_query, batch, page_size=batch_size)
            inserted += len(batch)
            conn.commit()
            if i % 1000 == 0 and i > 0:
                logger.info(f"  Inserted {i:,} / {len(records):,} jurisdictions...")
        logger.success(f"  ✓ Inserted/updated {inserted:,} jurisdictions")
        return inserted
    except Exception as e:
        conn.rollback()
        logger.error(f"  ✗ Error loading data: {e}")
        raise
    finally:
        cursor.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Load jurisdictions_details.parquet into jurisdiction')
    parser.add_argument('--file', type=Path, default=PARQUET_FILE)
    parser.add_argument('--batch-size', type=int, default=1000)
    args = parser.parse_args()

    if not args.file.exists():
        logger.error(f"Parquet file not found: {args.file}")
        return 1

    conn = psycopg2.connect(DATABASE_URL)
    try:
        create_table(conn)
        load_data(conn, args.file, batch_size=args.batch_size)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE youtube_channel_count > 0) AS with_youtube
            FROM jurisdiction
            WHERE jurisdiction_id IS NOT NULL
        """)
        total, with_yt = cursor.fetchone()
        logger.info(f"Database totals: {total:,} jurisdictions with typed id, {with_yt:,} with YouTube")
        cursor.close()
        logger.info("Next steps:")
        logger.info("  SELECT name, state_code, youtube_channels FROM jurisdiction WHERE youtube_channel_count > 0 LIMIT 10;")
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())

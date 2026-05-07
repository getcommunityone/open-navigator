#!/usr/bin/env python3
"""
NCCS (National Center for Charitable Statistics) → Bronze Table Loader

Loads Unified BMF (Business Master File) data from local CSV files into the
bronze_organizations_nonprofits_nccs table.

This provides historical nonprofit data (1989-2025) with one row per organization,
enriched with additional metadata not available in raw IRS files.

Run download_nccs_bulk.py first to fetch the CSV files.

Directory Structure:
    /mnt/d/nccs_data/  (or configurable base path)
    ├── unified-bmf/
    │   └── v1.2/
    │       ├── full/
    │       │   └── UNIFIED_BMF_V1.2.csv
    │       └── by-state/
    │           ├── AL.csv
    │           └── ...

Usage:
    # Load full file to bronze
    python load_nccs_bulk.py

    # Custom base directory
    python load_nccs_bulk.py --base-dir /mnt/d/nccs_data

    # Load specific states only
    python load_nccs_bulk.py --states CA,NY,TX
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
from loguru import logger
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DEFAULT_DB_URL = "postgresql://postgres:password@localhost:5433/open_navigator"


def create_bronze_tables(cursor):
    """Create bronze_organizations_nonprofits_nccs tables (current + history)."""

    cursor.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_nonprofits_nccs_history (
            id SERIAL PRIMARY KEY,
            ein2 VARCHAR(20),
            ein VARCHAR(20) NOT NULL,
            ntee_irs VARCHAR(20),
            ntee_nccs VARCHAR(20),
            nteev2 VARCHAR(20),
            nccs_level_1 VARCHAR(100),
            nccs_level_2 VARCHAR(100),
            nccs_level_3 VARCHAR(100),
            f990_org_addr_city VARCHAR(100),
            f990_org_addr_state VARCHAR(2),
            f990_org_addr_zip VARCHAR(20),
            f990_org_addr_street VARCHAR(255),
            census_cbsa_fips VARCHAR(20),
            census_cbsa_name VARCHAR(200),
            census_block_fips VARCHAR(20),
            census_urban_area VARCHAR(200),
            census_state_abbr VARCHAR(2),
            census_county_name VARCHAR(100),
            org_addr_full TEXT,
            org_addr_match VARCHAR(200),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            geocoder_score DOUBLE PRECISION,
            geocoder_match VARCHAR(100),
            bmf_subsection_code VARCHAR(20),
            bmf_status_code VARCHAR(20),
            bmf_pf_filing_req_code VARCHAR(20),
            bmf_organization_code VARCHAR(20),
            bmf_income_code VARCHAR(20),
            bmf_group_exempt_num VARCHAR(20),
            bmf_foundation_code VARCHAR(20),
            bmf_filing_req_code VARCHAR(20),
            bmf_deductibility_code VARCHAR(20),
            bmf_classification_code VARCHAR(20),
            bmf_asset_code VARCHAR(20),
            bmf_affiliation_code VARCHAR(20),
            org_ruling_date VARCHAR(20),
            org_fiscal_year INTEGER,
            org_ruling_year INTEGER,
            org_year_first INTEGER,
            org_year_last INTEGER,
            org_year_count INTEGER,
            org_pers_ico TEXT,
            org_name_sec TEXT,
            org_name_current TEXT,
            org_fiscal_period VARCHAR(20),
            f990_total_revenue_recent BIGINT,
            f990_total_income_recent BIGINT,
            f990_total_assets_recent BIGINT,
            f990_total_expenses_recent BIGINT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ein, org_year_last)
        );

        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_ein ON bronze.bronze_organizations_nonprofits_nccs_history(ein);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_year ON bronze.bronze_organizations_nonprofits_nccs_history(org_year_last);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_state ON bronze.bronze_organizations_nonprofits_nccs_history(f990_org_addr_state);
    """)
    logger.success("Created bronze_organizations_nonprofits_nccs_history table")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_nonprofits_nccs (
            id SERIAL PRIMARY KEY,
            ein2 VARCHAR(20),
            ein VARCHAR(20) NOT NULL,
            ntee_irs VARCHAR(20),
            ntee_nccs VARCHAR(20),
            nteev2 VARCHAR(20),
            nccs_level_1 VARCHAR(100),
            nccs_level_2 VARCHAR(100),
            nccs_level_3 VARCHAR(100),
            f990_org_addr_city VARCHAR(100),
            f990_org_addr_state VARCHAR(2),
            f990_org_addr_zip VARCHAR(20),
            f990_org_addr_street VARCHAR(255),
            census_cbsa_fips VARCHAR(20),
            census_cbsa_name VARCHAR(200),
            census_block_fips VARCHAR(20),
            census_urban_area VARCHAR(200),
            census_state_abbr VARCHAR(2),
            census_county_name VARCHAR(100),
            org_addr_full TEXT,
            org_addr_match VARCHAR(200),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            geocoder_score DOUBLE PRECISION,
            geocoder_match VARCHAR(100),
            bmf_subsection_code VARCHAR(20),
            bmf_status_code VARCHAR(20),
            bmf_pf_filing_req_code VARCHAR(20),
            bmf_organization_code VARCHAR(20),
            bmf_income_code VARCHAR(20),
            bmf_group_exempt_num VARCHAR(20),
            bmf_foundation_code VARCHAR(20),
            bmf_filing_req_code VARCHAR(20),
            bmf_deductibility_code VARCHAR(20),
            bmf_classification_code VARCHAR(20),
            bmf_asset_code VARCHAR(20),
            bmf_affiliation_code VARCHAR(20),
            org_ruling_date VARCHAR(20),
            org_fiscal_year INTEGER,
            org_ruling_year INTEGER,
            org_year_first INTEGER,
            org_year_last INTEGER,
            org_year_count INTEGER,
            org_pers_ico TEXT,
            org_name_sec TEXT,
            org_name_current TEXT,
            org_fiscal_period VARCHAR(20),
            f990_total_revenue_recent BIGINT,
            f990_total_income_recent BIGINT,
            f990_total_assets_recent BIGINT,
            f990_total_expenses_recent BIGINT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ein)
        );

        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_state ON bronze.bronze_organizations_nonprofits_nccs(f990_org_addr_state);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_city ON bronze.bronze_organizations_nonprofits_nccs(f990_org_addr_city, f990_org_addr_state);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_ntee ON bronze.bronze_organizations_nonprofits_nccs(ntee_nccs);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_ntee_irs ON bronze.bronze_organizations_nonprofits_nccs(ntee_irs);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_level1 ON bronze.bronze_organizations_nonprofits_nccs(nccs_level_1);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_county ON bronze.bronze_organizations_nonprofits_nccs(census_county_name, census_state_abbr);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_name ON bronze.bronze_organizations_nonprofits_nccs USING gin(to_tsvector('english', org_name_current));
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_lat ON bronze.bronze_organizations_nonprofits_nccs(latitude) WHERE latitude IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_lon ON bronze.bronze_organizations_nonprofits_nccs(longitude) WHERE longitude IS NOT NULL;
    """)
    logger.success("Created bronze_organizations_nonprofits_nccs table (current only)")


def _row_to_tuple(row: dict) -> tuple:
    def safe_get(key):
        val = row.get(key)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return val

    return (
        safe_get('ein2'), safe_get('ein'), safe_get('ntee_irs'), safe_get('ntee_nccs'), safe_get('nteev2'),
        safe_get('nccs_level_1'), safe_get('nccs_level_2'), safe_get('nccs_level_3'),
        safe_get('f990_org_addr_city'), safe_get('f990_org_addr_state'), safe_get('f990_org_addr_zip'), safe_get('f990_org_addr_street'),
        safe_get('census_cbsa_fips'), safe_get('census_cbsa_name'), safe_get('census_block_fips'), safe_get('census_urban_area'),
        safe_get('census_state_abbr'), safe_get('census_county_name'), safe_get('org_addr_full'), safe_get('org_addr_match'),
        safe_get('latitude'), safe_get('longitude'), safe_get('geocoder_score'), safe_get('geocoder_match'),
        safe_get('bmf_subsection_code'), safe_get('bmf_status_code'), safe_get('bmf_pf_filing_req_code'), safe_get('bmf_organization_code'),
        safe_get('bmf_income_code'), safe_get('bmf_group_exempt_num'), safe_get('bmf_foundation_code'), safe_get('bmf_filing_req_code'),
        safe_get('bmf_deductibility_code'), safe_get('bmf_classification_code'), safe_get('bmf_asset_code'), safe_get('bmf_affiliation_code'),
        safe_get('org_ruling_date'), safe_get('org_fiscal_year'), safe_get('org_ruling_year'), safe_get('org_year_first'), safe_get('org_year_last'),
        safe_get('org_year_count'), safe_get('org_pers_ico'), safe_get('org_name_sec'), safe_get('org_name_current'), safe_get('org_fiscal_period'),
        safe_get('f990_total_revenue_recent'), safe_get('f990_total_income_recent'), safe_get('f990_total_assets_recent'), safe_get('f990_total_expenses_recent'),
    )


INSERT_HISTORY = """
    INSERT INTO bronze.bronze_organizations_nonprofits_nccs_history (
        ein2, ein, ntee_irs, ntee_nccs, nteev2, nccs_level_1, nccs_level_2, nccs_level_3,
        f990_org_addr_city, f990_org_addr_state, f990_org_addr_zip, f990_org_addr_street,
        census_cbsa_fips, census_cbsa_name, census_block_fips, census_urban_area,
        census_state_abbr, census_county_name, org_addr_full, org_addr_match,
        latitude, longitude, geocoder_score, geocoder_match,
        bmf_subsection_code, bmf_status_code, bmf_pf_filing_req_code, bmf_organization_code,
        bmf_income_code, bmf_group_exempt_num, bmf_foundation_code, bmf_filing_req_code,
        bmf_deductibility_code, bmf_classification_code, bmf_asset_code, bmf_affiliation_code,
        org_ruling_date, org_fiscal_year, org_ruling_year, org_year_first, org_year_last,
        org_year_count, org_pers_ico, org_name_sec, org_name_current, org_fiscal_period,
        f990_total_revenue_recent, f990_total_income_recent, f990_total_assets_recent, f990_total_expenses_recent
    ) VALUES %s
    ON CONFLICT (ein, org_year_last) DO UPDATE SET
        org_name_current = EXCLUDED.org_name_current,
        f990_total_revenue_recent = EXCLUDED.f990_total_revenue_recent,
        f990_total_assets_recent = EXCLUDED.f990_total_assets_recent,
        loaded_at = CURRENT_TIMESTAMP
"""

INSERT_CURRENT = """
    INSERT INTO bronze.bronze_organizations_nonprofits_nccs (
        ein2, ein, ntee_irs, ntee_nccs, nteev2, nccs_level_1, nccs_level_2, nccs_level_3,
        f990_org_addr_city, f990_org_addr_state, f990_org_addr_zip, f990_org_addr_street,
        census_cbsa_fips, census_cbsa_name, census_block_fips, census_urban_area,
        census_state_abbr, census_county_name, org_addr_full, org_addr_match,
        latitude, longitude, geocoder_score, geocoder_match,
        bmf_subsection_code, bmf_status_code, bmf_pf_filing_req_code, bmf_organization_code,
        bmf_income_code, bmf_group_exempt_num, bmf_foundation_code, bmf_filing_req_code,
        bmf_deductibility_code, bmf_classification_code, bmf_asset_code, bmf_affiliation_code,
        org_ruling_date, org_fiscal_year, org_ruling_year, org_year_first, org_year_last,
        org_year_count, org_pers_ico, org_name_sec, org_name_current, org_fiscal_period,
        f990_total_revenue_recent, f990_total_income_recent, f990_total_assets_recent, f990_total_expenses_recent
    ) VALUES %s
    ON CONFLICT (ein) DO UPDATE SET
        org_name_current = EXCLUDED.org_name_current,
        f990_org_addr_city = EXCLUDED.f990_org_addr_city,
        f990_org_addr_state = EXCLUDED.f990_org_addr_state,
        ntee_nccs = EXCLUDED.ntee_nccs,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        f990_total_revenue_recent = EXCLUDED.f990_total_revenue_recent,
        f990_total_assets_recent = EXCLUDED.f990_total_assets_recent,
        org_year_last = EXCLUDED.org_year_last,
        loaded_at = CURRENT_TIMESTAMP
"""


def load_to_bronze(file_path: Path, db_url: str = DEFAULT_DB_URL):
    """Load NCCS Unified BMF CSV into bronze tables (history + current)."""
    logger.info(f"Loading NCCS data from: {file_path}")

    chunk_size = 50000
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    try:
        create_bronze_tables(cursor)
        conn.commit()

        chunks_processed = 0
        total_rows = 0
        total_history_rows = 0
        total_current_rows = 0

        numeric_cols = [
            'org_fiscal_year', 'org_ruling_year', 'org_year_first', 'org_year_last', 'org_year_count',
            'f990_total_revenue_recent', 'f990_total_income_recent',
            'f990_total_assets_recent', 'f990_total_expenses_recent',
        ]
        float_cols = ['latitude', 'longitude', 'geocoder_score']

        try:
            for chunk in pd.read_csv(file_path, chunksize=chunk_size, dtype=str, low_memory=False, on_bad_lines='skip'):
                chunks_processed += 1
                total_rows += len(chunk)
                logger.info(f"Processing chunk {chunks_processed}: {len(chunk):,} rows (total: {total_rows:,})")

                chunk.columns = chunk.columns.str.lower()

                for col in numeric_cols:
                    if col in chunk.columns:
                        chunk[col] = pd.to_numeric(chunk[col], errors='coerce')
                for col in float_cols:
                    if col in chunk.columns:
                        chunk[col] = pd.to_numeric(chunk[col], errors='coerce')

                chunk_clean = chunk.where(pd.notna(chunk), None)

                # History: all records, deduplicated on (ein, org_year_last)
                chunk_history = chunk_clean.copy()
                if 'ein' in chunk_history.columns and 'org_year_last' in chunk_history.columns:
                    before = len(chunk_history)
                    chunk_history = chunk_history.drop_duplicates(subset=['ein', 'org_year_last'], keep='first')
                    removed = before - len(chunk_history)
                    if removed > 0:
                        logger.info(f"  Removed {removed:,} duplicate (ein, year) pairs for history")

                history_records = [_row_to_tuple(row) for row in chunk_history.to_dict('records')]
                execute_values(cursor, INSERT_HISTORY, history_records, page_size=1000)
                conn.commit()
                total_history_rows += len(history_records)
                logger.info(f"  Inserted {len(history_records):,} records to history table")

                # Current: most recent record per EIN
                chunk_current = chunk_clean.copy()
                if 'ein' in chunk_current.columns:
                    before = len(chunk_current)
                    chunk_current = chunk_current.sort_values('org_year_last', ascending=False, na_position='last')
                    chunk_current = chunk_current.drop_duplicates(subset=['ein'], keep='first')
                    removed = before - len(chunk_current)
                    if removed > 0:
                        logger.info(f"  Keeping {len(chunk_current):,} most recent records (removed {removed:,} older versions)")

                current_records = [_row_to_tuple(row) for row in chunk_current.to_dict('records')]
                execute_values(cursor, INSERT_CURRENT, current_records, page_size=1000)
                conn.commit()
                total_current_rows += len(current_records)

                logger.success(f"  Chunk {chunks_processed} complete: {len(current_records):,} current, {len(history_records):,} history")

        except pd.errors.ParserError as e:
            logger.warning(f"CSV parsing ended due to malformed data: {e}")
            logger.info("This is likely an incomplete last line — continuing with loaded data...")

        logger.success("Load complete!")
        logger.info(f"  Total rows processed: {total_rows:,}")
        logger.info(f"  History table: {total_history_rows:,} records (all versions)")
        logger.info(f"  Current table: {total_current_rows:,} records (most recent only)")

    except Exception as e:
        logger.error(f"Error loading to bronze: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Load NCCS BMF CSV files into the bronze database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python load_nccs_bulk.py
  python load_nccs_bulk.py --base-dir /mnt/d/nccs_data
  python load_nccs_bulk.py --states CA,NY,TX
  python load_nccs_bulk.py --db-url postgresql://user:pass@host:5432/db
        """
    )

    parser.add_argument('--base-dir', type=str, default='data/cache/nccs',
                        help='Base directory where NCCS data was downloaded (default: data/cache/nccs)')
    parser.add_argument('--states', type=str,
                        help='Comma-separated state codes to load (e.g., CA,NY,TX); omit to load full file')
    parser.add_argument('--db-url', type=str, default=DEFAULT_DB_URL,
                        help='PostgreSQL connection string')

    args = parser.parse_args()

    states: Optional[List[str]] = args.states.split(',') if args.states else None

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )

    logger.info("=" * 60)
    logger.info("NCCS Unified BMF → Bronze Table Loader")
    logger.info("=" * 60)
    logger.info(f"Base directory: {args.base_dir}")

    base = Path(args.base_dir)

    if states:
        logger.info(f"Loading {len(states)} state file(s) to bronze...")
        for state in states:
            file_path = base / "unified-bmf" / "v1.2" / "by-state" / f"{state}.csv"
            if file_path.exists():
                load_to_bronze(file_path, db_url=args.db_url)
            else:
                logger.warning(f"File not found: {file_path}")
    else:
        file_path = base / "unified-bmf" / "v1.2" / "full" / "UNIFIED_BMF_V1.2.csv"
        if file_path.exists():
            load_to_bronze(file_path, db_url=args.db_url)
        else:
            logger.error(f"Full file not found: {file_path}")
            sys.exit(1)

    logger.info("=" * 60)
    logger.success("NCCS data loaded to bronze!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

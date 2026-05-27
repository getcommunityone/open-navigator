#!/usr/bin/env python3
"""
Load GSA .gov Domain List into bronze.bronze_gov_domains

Reads a previously downloaded CSV from the cache and upserts records into
the bronze.bronze_gov_domains PostgreSQL table. Run download_gsa_domains.py first.

Data Source: https://github.com/cisagov/dotgov-data

Usage:
    python scripts/datasources/gsa/load_gsa_domains_to_postgres.py
    python scripts/datasources/gsa/load_gsa_domains_to_postgres.py --truncate
    python scripts/datasources/gsa/load_gsa_domains_to_postgres.py --file data/cache/gsa/dotgov_domains_20260507.csv
    python scripts/datasources/gsa/load_gsa_domains_to_postgres.py --limit 100 --dry-run
"""
import sys
import argparse
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


CACHE_DIR = Path("data/cache/gsa")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"

# Known approximate bounds for .gov domain counts (cisagov/dotgov-data)
EXPECTED_MIN = 5_000
EXPECTED_MAX = 15_000

MIGRATE_TABLE_SQL = """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'bronze_bronze_gov_domains'
        ) THEN
            CREATE SCHEMA IF NOT EXISTS bronze;
            ALTER TABLE public.bronze_bronze_gov_domains SET SCHEMA bronze;
            ALTER TABLE bronze.bronze_bronze_gov_domains RENAME TO bronze_gov_domains;
        END IF;
    END
    $$;
"""

CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_gov_domains (
        domain_name         VARCHAR(255) PRIMARY KEY,
        domain_type         VARCHAR(50),
        agency              VARCHAR(255),
        organization        VARCHAR(255),
        city                VARCHAR(100),
        state               VARCHAR(2),
        security_contact    VARCHAR(255),
        ingestion_date      TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_bgd_domain_type ON bronze.bronze_gov_domains(domain_type);
    CREATE INDEX IF NOT EXISTS idx_bgd_state       ON bronze.bronze_gov_domains(state);
"""

INSERT_SQL = """
    INSERT INTO bronze.bronze_gov_domains
        (domain_name, domain_type, agency, organization, city, state, security_contact)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (domain_name) DO UPDATE SET
        domain_type      = EXCLUDED.domain_type,
        agency           = EXCLUDED.agency,
        organization     = EXCLUDED.organization,
        city             = EXCLUDED.city,
        state            = EXCLUDED.state,
        security_contact = EXCLUDED.security_contact,
        ingestion_date   = NOW()
"""


def find_latest_csv() -> Path:
    csvs = sorted(CACHE_DIR.glob("dotgov_domains_*.csv"), reverse=True)
    if not csvs:
        raise FileNotFoundError(
            f"No cached GSA CSV found in {CACHE_DIR}. "
            "Run download_gsa_domains.py first."
        )
    return csvs[0]


def safe_str(val, maxlen=None):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def parse_csv(csv_path: Path, limit: int = None) -> list[tuple]:
    logger.info(f"Parsing {csv_path}...")
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    logger.info(f"Columns: {list(df.columns)}")
    logger.info(f"Raw rows in CSV: {len(df):,}")

    if limit:
        df = df.head(limit)

    col_map = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=col_map)

    # Sanity-check source before building records
    null_domain_count = df["domain_name"].isna().sum() if "domain_name" in df.columns else len(df)
    dup_domain_count = df["domain_name"].duplicated().sum() if "domain_name" in df.columns else 0
    if null_domain_count:
        logger.warning(f"  {null_domain_count:,} rows have NULL domain_name — will be dropped")
    if dup_domain_count:
        logger.warning(f"  {dup_domain_count:,} duplicate domain_name values in source — ON CONFLICT will keep last write")

    records = [
        (
            safe_str(row.get("domain_name"), 255),
            safe_str(row.get("domain_type"), 50),
            safe_str(row.get("organization_name"), 255),
            safe_str(row.get("suborganization_name"), 255),
            safe_str(row.get("city"), 100),
            safe_str(row.get("state"), 2),
            safe_str(row.get("security_contact_email"), 255),
        )
        for _, row in df.iterrows()
    ]

    records = [r for r in records if r[0]]
    logger.info(f"Prepared {len(records):,} domain records (after dropping nulls)")
    return records


def sanity_check(cur, source_count: int, limit: int = None) -> bool:
    cur.execute("SELECT COUNT(*) FROM bronze.bronze_gov_domains")
    table_count = cur.fetchone()[0]

    if limit:
        logger.info(f"Post-load table count: {table_count:,} (limit mode — skipping range check)")
        return True

    ok = EXPECTED_MIN <= table_count <= EXPECTED_MAX
    status = "OK" if ok else "FAIL"
    logger.info(
        f"Sanity check [{status}]: table={table_count:,}, "
        f"source={source_count:,}, "
        f"expected={EXPECTED_MIN:,}–{EXPECTED_MAX:,}"
    )
    if not ok:
        logger.error(
            f"Row count {table_count:,} is outside expected range "
            f"[{EXPECTED_MIN:,}, {EXPECTED_MAX:,}]. "
            "Consider running with --truncate to clear stale data."
        )
    return ok


def load_to_postgres(records: list[tuple], dry_run: bool = False, truncate: bool = False, limit: int = None) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute(MIGRATE_TABLE_SQL)
    conn.commit()
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    if truncate:
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_gov_domains")
        before = cur.fetchone()[0]
        cur.execute("TRUNCATE TABLE bronze.bronze_gov_domains")
        conn.commit()
        logger.info(f"Truncated bronze.bronze_gov_domains ({before:,} rows removed)")

    if dry_run:
        logger.warning("DRY RUN — skipping INSERT, showing first 5 records:")
        for r in records[:5]:
            logger.info(f"  {r}")
        cur.close()
        conn.close()
        return 0

    execute_batch(cur, INSERT_SQL, records, page_size=5000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM bronze.bronze_gov_domains")
    total = cur.fetchone()[0]
    logger.success(f"Upserted {len(records):,} domains → bronze.bronze_gov_domains (table total: {total:,})")

    sanity_check(cur, source_count=len(records), limit=limit)

    cur.execute("""
        SELECT domain_type, COUNT(*) AS cnt
        FROM bronze.bronze_gov_domains
        GROUP BY domain_type
        ORDER BY cnt DESC
        LIMIT 10
    """)
    logger.info("Breakdown by domain type:")
    for domain_type, cnt in cur.fetchall():
        logger.info(f"  {domain_type or '(unknown)'}: {cnt:,}")

    cur.close()
    conn.close()
    return len(records)


def main():
    parser = argparse.ArgumentParser(description="Load cached GSA .gov domain CSV into bronze.bronze_gov_domains")
    parser.add_argument("--file", type=str, help="Path to CSV file (default: latest in data/cache/gsa/)")
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write to database")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading (recommended for full reloads)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("GSA .gov Domains → bronze.bronze_gov_domains")
    logger.info("=" * 70)

    csv_path = Path(args.file) if args.file else find_latest_csv()
    logger.info(f"Source: {csv_path}")

    records = parse_csv(csv_path, limit=args.limit)
    load_to_postgres(records, dry_run=args.dry_run, truncate=args.truncate, limit=args.limit)

    logger.success("=" * 70)
    logger.success("Done.")
    logger.success("=" * 70)


if __name__ == "__main__":
    main()

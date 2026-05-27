"""
GSA .gov Domain List Integration

Downloads and processes the GSA's public list of all registered .gov domains
to identify official government websites.

Data Source: https://github.com/cisagov/dotgov-data

Usage:
    python scripts/datasources/gsa/download_gsa_domains.py
    python scripts/datasources/gsa/download_gsa_domains.py --limit 100
"""
import sys
import asyncio
import argparse
import os
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


DOMAIN_LIST_URL = "https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv"
CACHE_DIR = Path("data/cache/gsa")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"

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


async def download_domain_list() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"dotgov_domains_{datetime.now().strftime('%Y%m%d')}.csv"

    if cache_file.exists() and (datetime.now().timestamp() - cache_file.stat().st_mtime) < 86400:
        logger.info(f"Using cached GSA domain list: {cache_file}")
        return cache_file

    logger.info(f"Downloading .gov domain list from GSA...")
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(DOMAIN_LIST_URL)
        response.raise_for_status()

    cache_file.write_bytes(response.content)
    logger.success(f"Downloaded {len(response.content):,} bytes → {cache_file}")
    return cache_file


def safe_str(val, maxlen=None):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def load_domains(csv_path: Path, limit: int = None) -> int:
    logger.info(f"Parsing {csv_path}...")
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    logger.info(f"Columns: {list(df.columns)}")
    logger.info(f"Total rows: {len(df):,}")

    if limit:
        df = df.head(limit)

    # Normalize column names — the CSV uses "Domain Name", "Domain Type", etc.
    col_map = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=col_map)

    records = []
    for _, row in df.iterrows():
        records.append((
            safe_str(row.get("domain_name"), 255),
            safe_str(row.get("domain_type"), 50),
            safe_str(row.get("organization_name"), 255),        # "Organization name" column
            safe_str(row.get("suborganization_name"), 255),     # "Suborganization name" column
            safe_str(row.get("city"), 100),
            safe_str(row.get("state"), 2),
            safe_str(row.get("security_contact_email"), 255),
        ))

    # Drop rows with no domain name
    records = [r for r in records if r[0]]
    logger.info(f"Prepared {len(records):,} domain records")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    execute_batch(cur, INSERT_SQL, records, page_size=5000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM bronze.bronze_gov_domains")
    total = cur.fetchone()[0]
    logger.success(f"Loaded {len(records):,} domains → bronze.bronze_gov_domains (total in table: {total:,})")

    cur.execute("""
        SELECT domain_type, COUNT(*) as cnt
        FROM bronze.bronze_gov_domains
        GROUP BY domain_type
        ORDER BY cnt DESC
        LIMIT 10
    """)
    logger.info("\nBreakdown by domain type:")
    for domain_type, cnt in cur.fetchall():
        logger.info(f"  {domain_type or '(unknown)'}: {cnt:,}")

    cur.close()
    conn.close()
    return len(records)


async def main(limit: int = None):
    logger.info("=" * 70)
    logger.info("GSA .gov Domains → bronze.bronze_gov_domains")
    logger.info("=" * 70)

    csv_path = await download_domain_list()
    load_domains(csv_path, limit=limit)

    logger.success("=" * 70)
    logger.success("Done.")
    logger.success("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download GSA .gov domain list into bronze table")
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit))

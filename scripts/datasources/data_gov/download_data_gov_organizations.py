"""
Data.gov Organizations Integration

Downloads all publishing organizations from the Data.gov CKAN Action API
(organization_list with all_fields=true) and upserts them into
bronze.bronze_organizations_gov.

The Data.gov catalog runs on CKAN, which exposes organizations (federal
agencies, sub-agencies, states, cities) via an RPC-style Action API.

API base: https://api.gsa.gov/technology/datagov/v3/action/
Docs:     https://docs.ckan.org/en/latest/api/

Requires a free api.data.gov key, passed via the DATA_GOV_API_KEY env var
or --api-key. Sign up at https://api.data.gov/signup/.

Usage:
    export DATA_GOV_API_KEY=your_key_here
    python scripts/datasources/data_gov/download_data_gov_organizations.py
    python scripts/datasources/data_gov/download_data_gov_organizations.py --limit 50
    python scripts/datasources/data_gov/download_data_gov_organizations.py --truncate
    python scripts/datasources/data_gov/download_data_gov_organizations.py --dry-run
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
import psycopg2
from loguru import logger
from psycopg2.extras import Json, execute_batch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


API_BASE = "https://api.gsa.gov/technology/datagov/v3/action"
CACHE_DIR = Path("data/cache/data.gov")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"

# Rough sanity bounds: Data.gov currently publishes ~1.5k organizations.
EXPECTED_MIN = 500
EXPECTED_MAX = 10_000

CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_gov (
        id                  VARCHAR(64) PRIMARY KEY,
        name                VARCHAR(255),
        title               VARCHAR(512),
        display_name        VARCHAR(512),
        description         TEXT,
        image_url           TEXT,
        image_display_url   TEXT,
        website_url         TEXT,
        org_type            VARCHAR(64),
        state               VARCHAR(32),
        approval_status     VARCHAR(64),
        is_organization     BOOLEAN,
        package_count       INTEGER,
        num_followers       INTEGER,
        created_at          TIMESTAMP,
        extras              JSONB,
        raw                 JSONB,
        ingestion_date      TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_bog_name    ON bronze.bronze_organizations_gov(name);
    CREATE INDEX IF NOT EXISTS idx_bog_state   ON bronze.bronze_organizations_gov(state);
    CREATE INDEX IF NOT EXISTS idx_bog_type    ON bronze.bronze_organizations_gov(org_type);
"""

INSERT_SQL = """
    INSERT INTO bronze.bronze_organizations_gov (
        id, name, title, display_name, description,
        image_url, image_display_url, website_url,
        org_type, state, approval_status, is_organization,
        package_count, num_followers, created_at, extras, raw
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        name              = EXCLUDED.name,
        title             = EXCLUDED.title,
        display_name      = EXCLUDED.display_name,
        description       = EXCLUDED.description,
        image_url         = EXCLUDED.image_url,
        image_display_url = EXCLUDED.image_display_url,
        website_url       = EXCLUDED.website_url,
        org_type          = EXCLUDED.org_type,
        state             = EXCLUDED.state,
        approval_status   = EXCLUDED.approval_status,
        is_organization   = EXCLUDED.is_organization,
        package_count     = EXCLUDED.package_count,
        num_followers     = EXCLUDED.num_followers,
        created_at        = EXCLUDED.created_at,
        extras            = EXCLUDED.extras,
        raw               = EXCLUDED.raw,
        ingestion_date    = NOW()
"""


def fetch_organizations(api_key: str, limit: int | None = None) -> list[dict]:
    """Fetch the full organization list with all fields from Data.gov CKAN API."""
    url = f"{API_BASE}/organization_list"
    params = {
        "all_fields": "true",
        "include_extras": "true",
        "include_dataset_count": "true",
        "include_users": "false",
    }
    headers = {"x-api-key": api_key, "Accept": "application/json"}

    logger.info(f"GET {url} (all_fields=true, include_extras=true)")
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    if not payload.get("success"):
        raise RuntimeError(f"CKAN API returned success=false: {payload}")

    orgs = payload.get("result", []) or []
    logger.success(f"Received {len(orgs):,} organizations from Data.gov")

    if limit:
        orgs = orgs[:limit]
        logger.info(f"Limited to first {len(orgs):,} for testing")

    return orgs


def cache_payload(orgs: list[dict]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"organizations_{datetime.now().strftime('%Y%m%d')}.json"
    cache_file.write_text(json.dumps(orgs, indent=2))
    logger.info(f"Cached payload → {cache_file}")
    return cache_file


def safe_str(val, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def safe_int(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def parse_timestamp(val) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def extract_website(org: dict) -> str | None:
    """Look for a website URL in `extras` (CKAN convention) and common fields."""
    for extra in org.get("extras") or []:
        key = (extra.get("key") or "").strip().lower()
        if key in {"website", "website_url", "url", "homepage", "agency_url"}:
            val = safe_str(extra.get("value"))
            if val:
                return val
    return safe_str(org.get("url")) or safe_str(org.get("homepage"))


def to_record(org: dict) -> tuple:
    extras = org.get("extras") or []
    return (
        safe_str(org.get("id"), 64),
        safe_str(org.get("name"), 255),
        safe_str(org.get("title"), 512),
        safe_str(org.get("display_name"), 512),
        safe_str(org.get("description")),
        safe_str(org.get("image_url")),
        safe_str(org.get("image_display_url")),
        extract_website(org),
        safe_str(org.get("type"), 64),
        safe_str(org.get("state"), 32),
        safe_str(org.get("approval_status"), 64),
        bool(org.get("is_organization")) if org.get("is_organization") is not None else None,
        safe_int(org.get("package_count")),
        safe_int(org.get("num_followers")),
        parse_timestamp(org.get("created")),
        Json(extras),
        Json(org),
    )


def load_to_postgres(
    orgs: list[dict],
    dry_run: bool = False,
    truncate: bool = False,
    limit: int | None = None,
) -> int:
    records = [to_record(o) for o in orgs if o.get("id")]
    skipped = len(orgs) - len(records)
    if skipped:
        logger.warning(f"Skipped {skipped:,} organizations missing 'id'")
    logger.info(f"Prepared {len(records):,} organization records")

    if dry_run:
        logger.warning("DRY RUN — showing first 3 records, not writing to database:")
        for r in records[:3]:
            logger.info(f"  id={r[0]} name={r[1]} title={r[2]!r} website={r[7]}")
        return 0

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    if truncate:
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_organizations_gov")
        before = cur.fetchone()[0]
        cur.execute("TRUNCATE TABLE bronze.bronze_organizations_gov")
        conn.commit()
        logger.info(f"Truncated bronze.bronze_organizations_gov ({before:,} rows removed)")

    execute_batch(cur, INSERT_SQL, records, page_size=500)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM bronze.bronze_organizations_gov")
    total = cur.fetchone()[0]
    logger.success(
        f"Upserted {len(records):,} organizations → "
        f"bronze.bronze_organizations_gov (table total: {total:,})"
    )

    if not limit and not (EXPECTED_MIN <= total <= EXPECTED_MAX):
        logger.warning(
            f"Row count {total:,} is outside expected range "
            f"[{EXPECTED_MIN:,}, {EXPECTED_MAX:,}] — review the source feed."
        )

    cur.execute("""
        SELECT COALESCE(org_type, '(unknown)') AS t, COUNT(*) AS cnt
        FROM bronze.bronze_organizations_gov
        GROUP BY t
        ORDER BY cnt DESC
        LIMIT 10
    """)
    logger.info("Breakdown by org_type:")
    for org_type, cnt in cur.fetchall():
        logger.info(f"  {org_type}: {cnt:,}")

    cur.execute("""
        SELECT COUNT(*) FROM bronze.bronze_organizations_gov WHERE website_url IS NOT NULL
    """)
    with_url = cur.fetchone()[0]
    logger.info(f"Organizations with a website_url: {with_url:,} / {total:,}")

    cur.close()
    conn.close()
    return len(records)


def main():
    parser = argparse.ArgumentParser(
        description="Download Data.gov organizations into bronze.bronze_organizations_gov"
    )
    parser.add_argument("--api-key", help="api.data.gov key (overrides DATA_GOV_API_KEY env var)")
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + parse, no DB writes")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument(
        "--from-cache",
        type=str,
        help="Skip the HTTP call and load from a previously cached JSON file",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Data.gov Organizations → bronze.bronze_organizations_gov")
    logger.info("=" * 70)

    if args.from_cache:
        cache_path = Path(args.from_cache)
        logger.info(f"Loading orgs from cache: {cache_path}")
        orgs = json.loads(cache_path.read_text())
        if args.limit:
            orgs = orgs[: args.limit]
    else:
        api_key = args.api_key or os.getenv("DATA_GOV_API_KEY")
        if not api_key:
            logger.error(
                "Missing API key. Set DATA_GOV_API_KEY or pass --api-key. "
                "Sign up free at https://api.data.gov/signup/"
            )
            sys.exit(2)
        orgs = fetch_organizations(api_key, limit=args.limit)
        cache_payload(orgs)

    load_to_postgres(orgs, dry_run=args.dry_run, truncate=args.truncate, limit=args.limit)

    logger.success("=" * 70)
    logger.success("Done.")
    logger.success("=" * 70)


if __name__ == "__main__":
    main()

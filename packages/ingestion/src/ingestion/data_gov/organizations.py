"""Data.gov Organizations integration.

Downloads all publishing organizations from the Data.gov CKAN Action API
(``organization_list`` with ``all_fields=true``) and upserts them into
``bronze.bronze_organizations_gov``.

Ported from scripts/datasources/data_gov/download_data_gov_organizations.py to
the ingestion workspace package. This is a faithful port: the typed bronze
schema, the typed-column UPSERT (PK = ``id``), the parsing helpers, the
post-load summary logging, and all CLI flags are preserved. The hardcoded
psycopg2 ``postgresql://...:5433`` connection is replaced with the async
``core_lib.db`` session (DSN resolves via ``NEON_DATABASE_URL_DEV`` /
``DATABASE_URL`` — DEV target only).

The Data.gov catalog runs on CKAN, which exposes organizations (federal
agencies, sub-agencies, states, cities) via an RPC-style Action API.

API base: https://api.gsa.gov/technology/datagov/v3/action/
Docs:     https://docs.ckan.org/en/latest/api/

Requires a free api.data.gov key, passed via the DATA_GOV_API_KEY env var
or --api-key. Sign up at https://api.data.gov/signup/.

Usage:
    export DATA_GOV_API_KEY=your_key_here
    python -m ingestion.data_gov.organizations
    python -m ingestion.data_gov.organizations --limit 50
    python -m ingestion.data_gov.organizations --truncate
    python -m ingestion.data_gov.organizations --dry-run
    python -m ingestion.data_gov.organizations --from-cache data/cache/data.gov/organizations_20260606.json

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging

_ROOT = Path(__file__).resolve().parents[3]

API_BASE = "https://api.gsa.gov/technology/datagov/v3/action"
CACHE_DIR = Path("data/cache/data.gov")

TABLE = "bronze.bronze_organizations_gov"

# Rough sanity bounds: Data.gov currently publishes ~1.5k organizations.
EXPECTED_MIN = 500
EXPECTED_MAX = 10_000


# --- DDL (each statement as a SEPARATE text(); never multiple per text()) ----

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
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
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bog_name ON bronze.bronze_organizations_gov(name)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bog_state ON bronze.bronze_organizations_gov(state)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bog_type ON bronze.bronze_organizations_gov(org_type)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_organizations_gov")

_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_organizations_gov (
        id, name, title, display_name, description,
        image_url, image_display_url, website_url,
        org_type, state, approval_status, is_organization,
        package_count, num_followers, created_at, extras, raw
    ) VALUES (
        :id, :name, :title, :display_name, :description,
        :image_url, :image_display_url, :website_url,
        :org_type, :state, :approval_status, :is_organization,
        :package_count, :num_followers, :created_at,
        CAST(:extras AS JSONB), CAST(:raw AS JSONB)
    )
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
)


def fetch_organizations(api_key: str, limit: int | None = None) -> list[dict]:
    """Fetch the full organization list with all fields from Data.gov CKAN API.

    Sends the api.data.gov key as both the X-Api-Key header and the api_key
    query parameter — api.gsa.gov accepts either, and passing both avoids
    edge cases where a gateway strips one.
    """
    url = f"{API_BASE}/organization_list"
    params = {
        "all_fields": "true",
        "include_extras": "true",
        "include_dataset_count": "true",
        "include_users": "false",
        "api_key": api_key,
    }
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}

    logger.info("GET {} (all_fields=true, include_extras=true)", url)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(url, params=params, headers=headers)

    if resp.status_code >= 400:
        body_preview = resp.text[:500].replace("\n", " ")
        logger.error("HTTP {} from {}", resp.status_code, url)
        logger.error("Response body: {}", body_preview)
        if resp.status_code == 403:
            logger.error(
                "403 typically means the api.data.gov key is not authorized "
                "for the Data.gov Catalog API. Verify the key at "
                "https://api.data.gov/signup/ — some keys must be requested "
                "per-API. You can also test the key directly with:"
            )
            logger.error(
                '  curl -H "X-Api-Key: $DATA_GOV_API_KEY" '
                '"{}/organization_list?all_fields=true"',
                API_BASE,
            )
        resp.raise_for_status()

    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN API returned success=false: {payload}")

    orgs = payload.get("result", []) or []
    logger.success("Received {:,} organizations from Data.gov", len(orgs))

    if limit:
        orgs = orgs[:limit]
        logger.info("Limited to first {:,} for testing", len(orgs))

    return orgs


def cache_payload(orgs: list[dict]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"organizations_{datetime.now().strftime('%Y%m%d')}.json"
    cache_file.write_text(json.dumps(orgs, indent=2))
    logger.info("Cached payload → {}", cache_file)
    return cache_file


def safe_str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def safe_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def parse_timestamp(val: Any) -> datetime | None:
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


def to_record(org: dict) -> dict[str, Any]:
    extras = org.get("extras") or []
    is_org = org.get("is_organization")
    return {
        "id": safe_str(org.get("id"), 64),
        "name": safe_str(org.get("name"), 255),
        "title": safe_str(org.get("title"), 512),
        "display_name": safe_str(org.get("display_name"), 512),
        "description": safe_str(org.get("description")),
        "image_url": safe_str(org.get("image_url")),
        "image_display_url": safe_str(org.get("image_display_url")),
        "website_url": extract_website(org),
        "org_type": safe_str(org.get("type"), 64),
        "state": safe_str(org.get("state"), 32),
        "approval_status": safe_str(org.get("approval_status"), 64),
        "is_organization": bool(is_org) if is_org is not None else None,
        "package_count": safe_int(org.get("package_count")),
        "num_followers": safe_int(org.get("num_followers")),
        "created_at": parse_timestamp(org.get("created")),
        "extras": json.dumps(extras),
        "raw": json.dumps(org),
    }


async def _prepare_target(session: AsyncSession, truncate: bool) -> None:
    await session.execute(_CREATE_SCHEMA_SQL)
    await session.execute(_CREATE_TABLE_SQL)
    for idx in _CREATE_INDEXES_SQL:
        await session.execute(idx)
    if truncate:
        result = await session.execute(text(f"SELECT COUNT(*) FROM {TABLE}"))
        before = result.scalar_one()
        await session.execute(_TRUNCATE_SQL)
        logger.info("Truncated {} ({:,} rows removed)", TABLE, before)


async def _log_summary(session: AsyncSession, loaded: int, limit: int | None) -> None:
    total = (await session.execute(text(f"SELECT COUNT(*) FROM {TABLE}"))).scalar_one()
    logger.success(
        "Upserted {:,} organizations → {} (table total: {:,})", loaded, TABLE, total
    )

    if not limit and not (EXPECTED_MIN <= total <= EXPECTED_MAX):
        logger.warning(
            "Row count {:,} is outside expected range [{:,}, {:,}] — "
            "review the source feed.",
            total,
            EXPECTED_MIN,
            EXPECTED_MAX,
        )

    breakdown = await session.execute(
        text(
            f"""
            SELECT COALESCE(org_type, '(unknown)') AS t, COUNT(*) AS cnt
            FROM {TABLE}
            GROUP BY t
            ORDER BY cnt DESC
            LIMIT 10
            """
        )
    )
    logger.info("Breakdown by org_type:")
    for org_type, cnt in breakdown.all():
        logger.info("  {}: {:,}", org_type, cnt)

    with_url = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE website_url IS NOT NULL")
        )
    ).scalar_one()
    logger.info("Organizations with a website_url: {:,} / {:,}", with_url, total)


async def load_to_postgres(
    orgs: list[dict],
    dry_run: bool = False,
    truncate: bool = False,
    limit: int | None = None,
) -> int:
    records = [to_record(o) for o in orgs if o.get("id")]
    skipped = len(orgs) - len(records)
    if skipped:
        logger.warning("Skipped {:,} organizations missing 'id'", skipped)
    logger.info("Prepared {:,} organization records", len(records))

    if dry_run:
        logger.warning("DRY RUN — showing first 3 records, not writing to database:")
        for r in records[:3]:
            logger.info(
                "  id={} name={} title={!r} website={}",
                r["id"],
                r["name"],
                r["title"],
                r["website_url"],
            )
        return 0

    async with async_session() as session:
        await _prepare_target(session, truncate)
        if records:
            await session.execute(_INSERT_SQL, records)
        await _log_summary(session, len(records), limit)

    return len(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Data.gov organizations into bronze.bronze_organizations_gov"
    )
    parser.add_argument(
        "--api-key", help="api.data.gov key (overrides DATA_GOV_API_KEY env var)"
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch + parse, no DB writes"
    )
    parser.add_argument(
        "--truncate", action="store_true", help="TRUNCATE table before loading"
    )
    parser.add_argument(
        "--from-cache",
        type=str,
        help="Skip the HTTP call and load from a previously cached JSON file",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    logger.info("=" * 70)
    logger.info("Data.gov Organizations → {}", TABLE)
    logger.info("=" * 70)

    if args.from_cache:
        cache_path = Path(args.from_cache)
        logger.info("Loading orgs from cache: {}", cache_path)
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
            return 2
        orgs = fetch_organizations(api_key, limit=args.limit)
        cache_payload(orgs)

    await load_to_postgres(
        orgs, dry_run=args.dry_run, truncate=args.truncate, limit=args.limit
    )

    logger.success("=" * 70)
    logger.success("Done.")
    logger.success("=" * 70)
    return 0


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

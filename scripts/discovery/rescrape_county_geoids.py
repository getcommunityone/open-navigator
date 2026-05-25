#!/usr/bin/env python3
"""
Re-run jurisdiction discovery for specific county GEOIDs (AL by default).

Uses ``intermediate.int_jurisdiction_websites`` for homepage seeds (override rows win).
Upserts optional ``jurisdiction_website_url_overrides``-style rows into
``int_jurisdiction_websites`` when ``--apply-homepage-overrides`` is set.

Usage:
  .venv/bin/python scripts/discovery/rescrape_county_geoids.py \\
    --geoids 01009,01021,01035,01053,01077,01091,01115 --apply-homepage-overrides

  .venv/bin/python scripts/discovery/rescrape_county_geoids.py --geoids 01053 --state AL
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from loguru import logger

from scripts.discovery.jurisdiction_discovery_pipeline import (
    JurisdictionDiscoveryPipeline,
    ensure_scraped_tables,
    resolve_database_url,
)

# Curated AL county homepages (override discovery seed URLs).
_HOMEPAGE_OVERRIDES: Dict[str, str] = {
    "01009": "https://www.blountcountyal.gov/",
    "01021": "https://chiltoncounty.org/",
    "01035": "https://www.conecuhcounty.us/",
    "01053": "https://www.escambiacountyal.gov/",
    "01077": "https://lauderdalecountyal.gov",
    "01091": "http://www.marengocountyal.com",
    "01115": "http://www.stclairco.com",
}


def _domain(url: str) -> Optional[str]:
    try:
        return (urlparse(url).hostname or "").lower() or None
    except Exception:
        return None


def _override_record_key(jurisdiction_id: str, website_url: str) -> str:
    return f"override|{jurisdiction_id}|{hashlib.md5(website_url.encode()).hexdigest()}"


def upsert_homepage_overrides(conn, geoids: List[str], state: str) -> int:
    import psycopg2

    n = 0
    with conn.cursor() as cur:
        for geoid in geoids:
            url = _HOMEPAGE_OVERRIDES.get(geoid)
            if not url:
                logger.warning("No homepage override for geoid {}", geoid)
                continue
            cur.execute(
                """
                SELECT jurisdiction_id, name, state_code, state
                FROM bronze.bronze_jurisdictions_counties
                WHERE geoid = %s
                """,
                (geoid.zfill(5),),
            )
            row = cur.fetchone()
            if not row:
                logger.warning("Unknown county geoid {}", geoid)
                continue
            jid, name, state_code, state_name = row
            cur.execute(
                """
                DELETE FROM intermediate.int_jurisdiction_websites
                WHERE jurisdiction_id = %s AND website_source = 'override'
                """,
                (jid,),
            )
            cur.execute(
                """
                INSERT INTO intermediate.int_jurisdiction_websites (
                    website_record_key, website_source, domain_name, website_url,
                    domain_type, jurisdiction_category, organization_name,
                    agency, city, state_code, state, jurisdiction_id,
                    ingestion_date, transformed_at, ocd_id
                ) VALUES (
                    %s, 'override', %s, %s,
                    NULL, 'county', %s,
                    NULL, NULL, %s, %s, %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL
                )
                """,
                (
                    _override_record_key(jid, url),
                    _domain(url),
                    url,
                    name,
                    state_code or state,
                    state_name,
                    jid,
                ),
            )
            n += 1
            logger.info("Override homepage {} → {}", jid, url)
    conn.commit()
    return n


def load_counties(conn, geoids: List[str], state: str) -> List[Dict[str, Any]]:
    import psycopg2

    out: List[Dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT geoid, usps, name, ansicode
            FROM bronze.bronze_jurisdictions_counties
            WHERE usps = %s AND geoid = ANY(%s)
            ORDER BY geoid
            """,
            (state.upper(), geoids),
        )
        for geoid, usps_r, name, ansi in cur.fetchall():
            gid = str(geoid or "").strip().replace("-", "")
            if not gid:
                continue
            out.append(
                {
                    "GEOID": gid,
                    "name": str(name or "").strip(),
                    "state_code": str(usps_r or "").strip().upper(),
                    "type": "county",
                    "population": 0,
                    "ANSICODE": str(ansi).strip() if ansi else "",
                    "full_name": str(name or "").strip(),
                }
            )
    return out


async def run_rescrape(
    geoids: List[str],
    *,
    state: str,
    apply_homepage_overrides: bool,
    max_concurrent: int,
) -> None:
    import psycopg2

    dbu = resolve_database_url()
    if not dbu:
        raise SystemExit("No database URL configured")

    geoids_norm = [g.strip().zfill(5) for g in geoids if g.strip()]
    conn = psycopg2.connect(dbu)
    try:
        if apply_homepage_overrides:
            upsert_homepage_overrides(conn, geoids_norm, state)
        jurisdictions = load_counties(conn, geoids_norm, state)
    finally:
        conn.close()

    if not jurisdictions:
        raise SystemExit(f"No counties found for {state} geoids={geoids_norm}")

    pipeline = JurisdictionDiscoveryPipeline(
        database_url=dbu,
        max_concurrent=max_concurrent,
        incremental=False,
    )
    try:
        ensure_scraped_tables(pipeline._conn())
        logger.info("Rescraping {} AL county(ies): {}", len(jurisdictions), geoids_norm)
        await pipeline.discover_batch(jurisdictions)
    finally:
        pipeline.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--geoids",
        required=True,
        help="Comma-separated 5-digit county GEOIDs, e.g. 01009,01053",
    )
    parser.add_argument("--state", default="AL", help="USPS state code (default AL)")
    parser.add_argument(
        "--apply-homepage-overrides",
        action="store_true",
        help="Insert override rows into int_jurisdiction_websites before scrape",
    )
    parser.add_argument("--max-concurrent", type=int, default=4)
    args = parser.parse_args()
    geoids = [g.strip() for g in args.geoids.split(",") if g.strip()]
    asyncio.run(
        run_rescrape(
            geoids,
            state=args.state,
            apply_homepage_overrides=args.apply_homepage_overrides,
            max_concurrent=args.max_concurrent,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

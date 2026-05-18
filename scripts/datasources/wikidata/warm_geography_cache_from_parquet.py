#!/usr/bin/env python3
"""
Warm geography Q-id cache and/or bronze tables from ``fips_gnis_map.parquet``.

Run once after the dump extract finishes, **before** ``load_jurisdictions_wikidata.py``,
to avoid WDQS bulk mapping (and ReadError / 429 retries).

Typical workflow (local Postgres)::

  # 1) Warm JSON cache + load SQL lookup table (one-time, ~minutes for large parquet)
  .venv/bin/python scripts/datasources/wikidata/warm_geography_cache_from_parquet.py \\
    --warm-cache --postgres

  # 2) Stamp Q-ids onto bronze for Alabama cities (no websites yet)
  .venv/bin/python scripts/datasources/wikidata/warm_geography_cache_from_parquet.py \\
    --apply-bronze --states AL --types city

  # 3) Hydrate websites via Wikibase API only (no bulk WDQS)
  WIKIDATA_WARM_FROM_PARQUET=1 WIKIDATA_SKIP_BULK_WDQS=1 WIKIDATA_HYDRATE_MISSING_WEBSITES=1 \\
    ./scripts/datasources/wikidata/run_wikidata_happy_path.sh --states AL --types city --force
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv()

from scripts.datasources.wikidata.geography_qid_cache import GeographyQidCache  # noqa: E402
from scripts.datasources.wikidata.parquet_qid_lookup import (  # noqa: E402
    apply_parquet_qids_to_bronze_counties,
    apply_parquet_qids_to_bronze_municipalities,
    load_parquet_to_postgres,
    resolve_fips_gnis_parquet_path,
    warm_geography_qid_cache_from_parquet,
)


def _database_url() -> str:
    return (
        os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Warm Q-id mappings from fips_gnis_map.parquet")
    ap.add_argument(
        "--parquet",
        type=Path,
        default=None,
        help="Path to fips_gnis_map.parquet (default: WIKIDATA_FIPS_GNIS_PARQUET or data/cache/wikidata/…)",
    )
    ap.add_argument("--warm-cache", action="store_true", help="Merge parquet into geography_qid_mapping_v1.json")
    ap.add_argument("--postgres", action="store_true", help="Load parquet into wikidata_fips_gnis_map table")
    ap.add_argument(
        "--apply-bronze",
        action="store_true",
        help="UPDATE bronze *_wikidata.wikidata_id from parquet (per --states / --types)",
    )
    ap.add_argument("--states", default="AL", help="Comma-separated USPS codes for --apply-bronze")
    ap.add_argument(
        "--types",
        default="city,county",
        help="city and/or county for --apply-bronze",
    )
    ap.add_argument("--database-url", default=None, help="Postgres URL (default: NEON_* env)")
    args = ap.parse_args()

    parquet = resolve_fips_gnis_parquet_path(args.parquet)
    if not parquet.is_file():
        logger.error(f"Parquet not found: {parquet}")
        return 1

    if not (args.warm_cache or args.postgres or args.apply_bronze):
        ap.error("Pass at least one of: --warm-cache, --postgres, --apply-bronze")

    if args.warm_cache:
        qcache = GeographyQidCache()
        stats = warm_geography_qid_cache_from_parquet(qcache, parquet)
        logger.success(
            f"Warmed geography cache at {qcache.path}: "
            f"{stats['parquet_rows']:,} parquet rows, +{stats['cache_keys_added']:,} cache keys"
        )

    db_url = args.database_url or _database_url()

    if args.postgres:
        n = load_parquet_to_postgres(parquet, db_url)
        logger.success(f"Loaded {n:,} rows into wikidata_fips_gnis_map")

    if args.apply_bronze:
        import psycopg2

        states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
        types = {t.strip().lower() for t in args.types.split(",") if t.strip()}
        conn = psycopg2.connect(db_url)
        try:
            for us in states:
                if "city" in types:
                    n = apply_parquet_qids_to_bronze_municipalities(conn, us, parquet)
                    logger.info(f"{us} municipalities: updated wikidata_id on {n} row(s)")
                if "county" in types:
                    n = apply_parquet_qids_to_bronze_counties(conn, us, parquet)
                    logger.info(f"{us} counties: updated wikidata_id on {n} row(s)")
        finally:
            conn.close()
        logger.success(
            "Bronze Q-ids stamped. Next: run load_jurisdictions_wikidata with "
            "WIKIDATA_SKIP_BULK_WDQS=1 WIKIDATA_HYDRATE_MISSING_WEBSITES=1 to fetch official_website via wbgetentities."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

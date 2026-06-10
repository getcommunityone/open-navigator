#!/usr/bin/env python3
"""
Backfill ``youtube_channel_*`` columns on municipality/county scraped tables from ``payload``.

Usage (repo root):
  .venv/bin/python scripts/discovery/backfill_youtube_primary_on_scraped.py
  .venv/bin/python scripts/discovery/backfill_youtube_primary_on_scraped.py --state AL
  .venv/bin/python scripts/discovery/backfill_youtube_primary_on_scraped.py --counties-only \\
    --states AL,GA,IN,MA,WA,WI
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url
from scrapers.discovery.youtube_primary_channel import pick_primary_youtube_channel

_COUNTIES_TABLE = "bronze.bronze_jurisdictions_counties_scraped"
_MUNICIPALITIES_TABLE = "bronze.bronze_jurisdictions_municipalities_scraped"
_ALL_TABLES = (_MUNICIPALITIES_TABLE, _COUNTIES_TABLE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="2-letter USPS filter (single state)")
    parser.add_argument(
        "--states",
        help="Comma-separated USPS codes (e.g. AL,GA,IN,MA,WA,WI); overrides --state",
    )
    parser.add_argument(
        "--counties-only",
        action="store_true",
        help="Only bronze.bronze_jurisdictions_counties_scraped",
    )
    parser.add_argument(
        "--municipalities-only",
        action="store_true",
        help="Only bronze.bronze_jurisdictions_municipalities_scraped",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.counties_only and args.municipalities_only:
        print("Use at most one of --counties-only and --municipalities-only", file=sys.stderr)
        return 1

    try:
        import psycopg2
    except ModuleNotFoundError:
        print("psycopg2 required", file=sys.stderr)
        return 1

    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1

    state_codes: list[str] = []
    if args.states:
        state_codes = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    elif args.state:
        state_codes = [args.state.strip().upper()]

    state_clause = ""
    params: list = []
    if state_codes:
        state_clause = " AND upper(btrim(usps::text)) = ANY(%s)"
        params.append(state_codes)

    if args.counties_only:
        tables = (_COUNTIES_TABLE,)
    elif args.municipalities_only:
        tables = (_MUNICIPALITIES_TABLE,)
    else:
        tables = _ALL_TABLES

    conn = psycopg2.connect(dbu)
    updated = 0
    scanned = 0
    try:
        with conn.cursor() as cur:
            for tbl in tables:
                cur.execute(
                    f"""
                    SELECT geoid, payload
                    FROM {tbl}
                    WHERE payload ? 'youtube_channels'
                      AND jsonb_array_length(COALESCE(payload->'youtube_channels', '[]'::jsonb)) > 0
                      {state_clause}
                    """,
                    params,
                )
                rows = cur.fetchall()
                for geoid, payload in rows:
                    scanned += 1
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    channels = (payload or {}).get("youtube_channels") or []
                    url, method, conf = pick_primary_youtube_channel(channels)
                    if not url:
                        continue
                    if args.dry_run:
                        print(f"{tbl} {geoid}: {url} ({method}, {conf})")
                        updated += 1
                        continue
                    cur.execute(
                        f"""
                        UPDATE {tbl}
                        SET youtube_channel_url = %s,
                            youtube_channel_selection_method = %s,
                            youtube_channel_selection_confidence = %s
                        WHERE geoid = %s
                        """,
                        (url, method, conf, geoid),
                    )
                    updated += cur.rowcount
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    db_host = dbu.split("@")[-1] if "@" in dbu else dbu
    print(
        json.dumps(
            {
                "database": "NEON_DATABASE_URL_DEV (via resolve_database_url)",
                "host": db_host,
                "scanned": scanned,
                "updated": updated,
                "dry_run": args.dry_run,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

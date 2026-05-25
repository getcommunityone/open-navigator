#!/usr/bin/env python3
"""
Backfill ``youtube_channel_*`` columns on municipality/county scraped tables from ``payload``.

Usage (repo root):
  .venv/bin/python scripts/discovery/backfill_youtube_primary_on_scraped.py
  .venv/bin/python scripts/discovery/backfill_youtube_primary_on_scraped.py --state AL
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
from scripts.discovery.youtube_primary_channel import pick_primary_youtube_channel

_TABLES = (
    "bronze.bronze_jurisdictions_municipalities_scraped",
    "bronze.bronze_jurisdictions_counties_scraped",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="2-letter USPS filter")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        import psycopg2
    except ModuleNotFoundError:
        print("psycopg2 required", file=sys.stderr)
        return 1

    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1

    state_clause = ""
    params: list = []
    if args.state:
        state_clause = " AND upper(btrim(usps::text)) = %s"
        params.append(args.state.strip().upper())

    conn = psycopg2.connect(dbu)
    updated = 0
    scanned = 0
    try:
        with conn.cursor() as cur:
            for tbl in _TABLES:
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

    print(json.dumps({"scanned": scanned, "updated": updated, "dry_run": args.dry_run}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

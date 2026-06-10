#!/usr/bin/env python3
"""
Populate ``intermediate.int_youtube_channel_metadata`` and refresh jurisdiction channel rows.

Phase 1 (no YouTube scrape): copy from ``bronze_events_channels`` + ``int_events_channels``.
Phase 2: apply cache onto ``int_events_channels`` / ``int_events_channels_candidates``.
Phase 3 (optional): scrape About pages for rows still missing metadata (HTML + RSS, no API).

Scraped fields written to ``int_events_channels_candidates`` include ``youtube_channel_id``,
``channel_title``, ``channel_description``, ``subscriber_count``, ``view_count``,
``latest_upload``, ``jurisdiction_website_back_links``, and ``back_links_to_jurisdiction_website``.

Examples::

  .venv/bin/python scripts/discovery/sync_int_youtube_channel_metadata.py --from-warehouse
  .venv/bin/python scripts/discovery/sync_int_youtube_channel_metadata.py --from-warehouse --apply-bronze --states AL
  .venv/bin/python scripts/discovery/sync_int_youtube_channel_metadata.py --scrape-missing --table candidates --states AL --limit 20
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py --table candidates --states AL
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.discovery.int_youtube_channel_metadata import (  # noqa: E402
    apply_metadata_to_jurisdiction_tables,
    ensure_table,
    fetch_row,
    row_needs_youtube_metadata_refresh,
    sync_from_bronze_events_channels,
    sync_from_int_events_channels,
    update_jurisdiction_youtube_row,
)
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url  # noqa: E402
from scrapers.youtube.youtube_channel_enrich import enrich_channel  # noqa: E402

import requests


def _scrape_missing(
    conn,
    *,
    state_codes: list[str] | None,
    limit: int | None,
    cookies: str,
    sleep: float,
    table: str,
) -> dict[str, int]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    clauses = [
        "y.youtube_channel_url IS NOT NULL",
        "BTRIM(y.youtube_channel_url) <> ''",
    ]
    params: list = []
    if state_codes:
        clauses.append("y.state_code = ANY(%s)")
        params.append([s.upper() for s in state_codes])

    sql = f"""
        SELECT y.id, y.jurisdiction_id, y.state_code, y.website_url,
               y.youtube_channel_url, y.youtube_channel_id, y.channel_title,
               y.channel_description, y.subscriber_count, y.video_count,
               y.view_count, y.latest_upload,
               y.jurisdiction_website_back_links, y.back_links_to_jurisdiction_website,
               y.discovery_method, y.official_meeting_confidence, y.jurisdiction_type,
               j.name AS jurisdiction_name
        FROM {table} y
        LEFT JOIN intermediate.int_jurisdictions j ON j.jurisdiction_id = y.jurisdiction_id
        WHERE {' AND '.join(clauses)}
        ORDER BY y.loaded_at DESC
    """
    if limit:
        sql += " LIMIT %s"
        params.append(int(limit))

    stats = {"scraped": 0, "failed": 0, "skipped_cached": 0}
    session = requests.Session()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = list(cur.fetchall())

    for row in rows:
        if not row_needs_youtube_metadata_refresh(row):
            stats["skipped_cached"] += 1
            continue
        cid = (row.get("youtube_channel_id") or "").strip()
        if cid and fetch_row(conn, cid):
            cached = fetch_row(conn, cid)
            if cached and (cached.get("channel_title") or cached.get("channel_description")):
                if not row_needs_youtube_metadata_refresh({**row, **cached}):
                    stats["skipped_cached"] += 1
                    continue
        try:
            enriched = enrich_channel(
                channel={
                    "channel_url": row["youtube_channel_url"],
                    "youtube_channel_url": row["youtube_channel_url"],
                    "youtube_channel_id": row.get("youtube_channel_id"),
                    "channel_title": row.get("channel_title"),
                    "discovery_method": row.get("discovery_method"),
                    "official_meeting_confidence": row.get("official_meeting_confidence"),
                },
                jurisdiction_name=str(row.get("jurisdiction_name") or row["jurisdiction_id"]),
                jurisdiction_state_code=row["state_code"],
                jurisdiction_homepage=row.get("website_url") or "",
                jurisdiction_type=str(row.get("jurisdiction_type") or ""),
                session=session,
                cookies_file=cookies,
            )
            update_jurisdiction_youtube_row(
                conn,
                table=table,
                row_id=int(row["id"]),
                enriched=enriched,
                row=row,
            )
            stats["scraped"] += 1
        except Exception as exc:
            stats["failed"] += 1
            print(f"FAIL {row['jurisdiction_id']}: {exc}", file=sys.stderr)
        if sleep > 0:
            time.sleep(sleep)
    return stats


def main() -> int:
    load_dotenv(_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-warehouse",
        action="store_true",
        help="Copy metadata from bronze_events_channels + int_events_channels",
    )
    parser.add_argument(
        "--apply-bronze",
        action="store_true",
        help="Push int cache onto int_events_channels tables",
    )
    parser.add_argument(
        "--scrape-missing",
        action="store_true",
        help="Scrape YouTube About for rows still missing metadata (writes int cache)",
    )
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument(
        "--table",
        choices=("verified", "candidates", "both"),
        default="candidates",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cookies", default="youtube_cookies.txt")
    parser.add_argument("--sleep", type=float, default=0.75)
    parser.add_argument(
        "--force-bronze",
        action="store_true",
        help="Apply cache even when bronze rows already have some metadata",
    )
    args = parser.parse_args()

    if not any((args.from_warehouse, args.apply_bronze, args.scrape_missing)):
        args.from_warehouse = True
        args.apply_bronze = True

    import psycopg2

    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1

    state_codes = [s.strip().upper() for s in (args.states or "").split(",") if s.strip()] or None
    stats: dict[str, int | dict] = {}

    conn = psycopg2.connect(dbu)
    try:
        ensure_table(conn)
        if args.from_warehouse:
            stats["from_bronze_events_channels"] = sync_from_bronze_events_channels(conn)
            stats["from_int_events_channels"] = sync_from_int_events_channels(conn)

        tables = []
        if args.table in ("verified", "both"):
            tables.append("intermediate.int_events_channels")
        if args.table in ("candidates", "both"):
            tables.append("intermediate.int_events_channels_candidates")

        if args.apply_bronze:
            stats["bronze_updated"] = {}
            for tbl in tables:
                stats["bronze_updated"][tbl] = apply_metadata_to_jurisdiction_tables(
                    conn,
                    table=tbl,
                    state_codes=state_codes,
                    only_missing=not args.force_bronze,
                )

        if args.scrape_missing:
            stats["scrape"] = {}
            for tbl in tables:
                stats["scrape"][tbl] = _scrape_missing(
                    conn,
                    state_codes=state_codes,
                    limit=args.limit,
                    cookies=args.cookies,
                    sleep=args.sleep,
                    table=tbl,
                )
            if args.apply_bronze:
                stats["bronze_updated_after_scrape"] = {}
                for tbl in tables:
                    stats["bronze_updated_after_scrape"][tbl] = apply_metadata_to_jurisdiction_tables(
                        conn,
                        table=tbl,
                        state_codes=state_codes,
                        only_missing=True,
                    )
    finally:
        conn.close()

    print(json.dumps(stats, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

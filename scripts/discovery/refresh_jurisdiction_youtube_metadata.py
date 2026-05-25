#!/usr/bin/env python3
"""
Re-fetch YouTube channel metadata (HTML + RSS, no Data API) for jurisdiction channel rows.

Updates ``youtube_channel_id``, ``channel_title``, ``channel_description``,
``subscriber_count``, ``video_count``, ``view_count``, ``latest_upload`` (``YYYY-MM-DD``),
``external_links``, ``jurisdiction_website_back_links``, and
``back_links_to_jurisdiction_website`` on ``intermediate.int_events_channels`` and/or
``intermediate.int_events_channels_candidates``.

Usage:
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py --all
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py --all --states AL,GA
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py \\
      --table candidates --all --states AL
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py \\
      --jurisdiction-id dothan_0121184 --cookies youtube_cookies.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.datasources.jurisdiction_pilot.youtube_channel_enrich import enrich_channel
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url
from scripts.discovery.int_youtube_channel_metadata import (
    row_needs_youtube_metadata_refresh,
    update_jurisdiction_youtube_row,
    values_from_enriched_metadata,
)


def _jurisdiction_name(row: dict) -> str:
    name = (row.get("jurisdiction_name") or "").strip()
    if name:
        return name
    return row["jurisdiction_id"].rsplit("_", 1)[0].replace("_", " ")


def main() -> int:
    load_dotenv(_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument("--jurisdiction-id", action="append", default=[])
    parser.add_argument(
        "--table",
        choices=("verified", "candidates", "both"),
        default="candidates",
        help="Default: intermediate.int_events_channels_candidates",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh every row (default: only rows missing metadata)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cookies", default="youtube_cookies.txt")
    parser.add_argument("--sleep", type=float, default=0.75, help="Seconds between channel fetches")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import psycopg2
    from psycopg2.extras import RealDictCursor

    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1

    tables = []
    if args.table in ("verified", "both"):
        tables.append("intermediate.int_events_channels")
    if args.table in ("candidates", "both"):
        tables.append("intermediate.int_events_channels_candidates")

    state_codes = [s.strip().upper() for s in (args.states or "").split(",") if s.strip()]
    jids = [j.strip() for j in args.jurisdiction_id if j.strip()]

    updated = skipped = failed = 0
    session = requests.Session()
    conn = psycopg2.connect(dbu)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for tbl in tables:
                clauses = ["y.youtube_channel_url IS NOT NULL", "BTRIM(y.youtube_channel_url) <> ''"]
                params: list = []
                if state_codes:
                    clauses.append("y.state_code = ANY(%s)")
                    params.append(state_codes)
                if jids:
                    clauses.append("y.jurisdiction_id = ANY(%s)")
                    params.append(jids)
                sql = f"""
                    SELECT
                        y.id,
                        y.jurisdiction_id,
                        y.state_code,
                        y.website_url,
                        y.youtube_channel_url,
                        y.youtube_channel_id,
                        y.channel_title,
                        y.channel_description,
                        y.subscriber_count,
                        y.video_count,
                        y.view_count,
                        y.latest_upload,
                        y.jurisdiction_website_back_links,
                        y.back_links_to_jurisdiction_website,
                        y.discovery_method,
                        y.official_meeting_confidence,
                        y.jurisdiction_type,
                        j.name AS jurisdiction_name
                    FROM {tbl} y
                    LEFT JOIN intermediate.int_jurisdictions j
                      ON j.jurisdiction_id = y.jurisdiction_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY y.loaded_at DESC
                """
                if args.limit:
                    sql += " LIMIT %s"
                    params.append(int(args.limit))
                cur.execute(sql, params)
                rows = list(cur.fetchall())

                for row in rows:
                    if not args.all and not row_needs_youtube_metadata_refresh(row):
                        skipped += 1
                        continue
                    try:
                        enriched = enrich_channel(
                            channel={
                                "channel_url": row["youtube_channel_url"],
                                "youtube_channel_url": row["youtube_channel_url"],
                                "youtube_channel_id": row.get("youtube_channel_id"),
                                "channel_title": row.get("channel_title"),
                                "channel_description": row.get("channel_description"),
                                "subscriber_count": row.get("subscriber_count"),
                                "video_count": row.get("video_count"),
                                "view_count": row.get("view_count"),
                                "latest_upload": row.get("latest_upload"),
                                "discovery_method": row.get("discovery_method"),
                                "official_meeting_confidence": row.get("official_meeting_confidence"),
                            },
                            jurisdiction_name=_jurisdiction_name(row),
                            jurisdiction_state_code=row["state_code"],
                            jurisdiction_homepage=row.get("website_url") or "",
                            jurisdiction_type=str(row.get("jurisdiction_type") or ""),
                            session=session,
                            cookies_file=args.cookies,
                        )
                    except Exception as exc:
                        failed += 1
                        print(f"FAIL {row['jurisdiction_id']}: {exc}", file=sys.stderr)
                        continue

                    values = values_from_enriched_metadata(enriched, row)
                    if args.dry_run:
                        print(
                            json.dumps(
                                {
                                    "table": tbl,
                                    "jurisdiction_id": row["jurisdiction_id"],
                                    "youtube_channel_url": row["youtube_channel_url"],
                                    **values,
                                },
                                default=str,
                            )
                        )
                        updated += 1
                    else:
                        try:
                            update_jurisdiction_youtube_row(
                                conn,
                                table=tbl,
                                row_id=int(row["id"]),
                                enriched=enriched,
                                row=row,
                            )
                            updated += 1
                        except Exception as exc:
                            failed += 1
                            conn.rollback()
                            print(
                                f"FAIL {row['jurisdiction_id']} id={row['id']}: {exc}",
                                file=sys.stderr,
                            )
                            continue

                    if args.sleep > 0:
                        time.sleep(args.sleep)
        if not args.dry_run and updated == 0 and failed == 0:
            conn.commit()
    finally:
        conn.close()

    print(json.dumps({"updated": updated, "skipped": skipped, "failed": failed}, indent=2))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

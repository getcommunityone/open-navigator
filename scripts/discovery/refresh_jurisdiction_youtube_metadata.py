#!/usr/bin/env python3
"""
Re-fetch YouTube channel metadata (HTML + RSS, no Data API) for bronze channel rows.

Updates ``channel_title``, ``channel_description``, ``subscriber_count``,
``video_count``, ``latest_upload`` (``YYYY-MM-DD``), ``external_links``, and
``jurisdiction_website_back_links`` on ``bronze.bronze_jurisdiction_youtube``.

Usage:
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py --all
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py --all --states AL,GA
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
from scripts.datasources.youtube.youtube_channel_page import is_junk_channel_title
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url


def _needs_refresh(row: dict) -> bool:
    title = (row.get("channel_title") or "").strip()
    desc = (row.get("channel_description") or "").strip()
    if not desc:
        return True
    if is_junk_channel_title(title):
        return True
    if row.get("subscriber_count") is None or row.get("video_count") is None:
        return True
    if not (row.get("latest_upload") or "").strip():
        return True
    if not row.get("jurisdiction_website_back_links") and row.get("back_links_to_jurisdiction_website"):
        return True
    return False


def _jurisdiction_name(row: dict) -> str:
    name = (row.get("jurisdiction_name") or "").strip()
    if name:
        return name
    return row["jurisdiction_id"].rsplit("_", 1)[0].replace("_", " ")


def _update_values(enriched: dict, row: dict) -> dict:
    latest = enriched.get("latest_upload") or row.get("latest_upload")
    if latest:
        latest = str(latest)[:10]
    return {
        "channel_title": enriched.get("channel_title") or row.get("channel_title"),
        "channel_description": enriched.get("channel_description") or row.get("channel_description"),
        "subscriber_count": enriched.get("subscriber_count"),
        "video_count": enriched.get("video_count"),
        "view_count": enriched.get("view_count"),
        "latest_upload": latest,
        "external_links": enriched.get("external_links") or [],
        "jurisdiction_website_back_links": enriched.get("jurisdiction_website_back_links") or [],
        "back_links_to_jurisdiction_website": bool(enriched.get("back_links_to_jurisdiction_website")),
        "official_meeting_confidence": enriched.get("official_meeting_confidence"),
        "youtube_channel_id": enriched.get("youtube_channel_id") or row.get("youtube_channel_id"),
        "youtube_channel_url": enriched.get("youtube_channel_url") or row.get("youtube_channel_url"),
    }


def main() -> int:
    load_dotenv(_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument("--jurisdiction-id", action="append", default=[])
    parser.add_argument(
        "--table",
        choices=("verified", "candidates", "both"),
        default="verified",
        help="Default: bronze.bronze_jurisdiction_youtube only",
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
        tables.append("bronze.bronze_jurisdiction_youtube")
    if args.table in ("candidates", "both"):
        tables.append("bronze.bronze_jurisdiction_youtube_candidates")

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
                    if not args.all and not _needs_refresh(row):
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
                            session=session,
                            cookies_file=args.cookies,
                        )
                    except Exception as exc:
                        failed += 1
                        print(f"FAIL {row['jurisdiction_id']}: {exc}", file=sys.stderr)
                        continue

                    values = _update_values(enriched, row)
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
                            cur.execute(
                                f"""
                                UPDATE {tbl}
                                SET channel_title = %s,
                                    channel_description = %s,
                                    subscriber_count = %s,
                                    video_count = %s,
                                    view_count = %s,
                                    latest_upload = %s,
                                    external_links = %s::jsonb,
                                    jurisdiction_website_back_links = %s::jsonb,
                                    back_links_to_jurisdiction_website = %s,
                                    official_meeting_confidence = %s,
                                    youtube_channel_id = COALESCE(%s, youtube_channel_id),
                                    loaded_at = NOW()
                                WHERE id = %s
                                """,
                                (
                                    values["channel_title"],
                                    values["channel_description"],
                                    values["subscriber_count"],
                                    values["video_count"],
                                    values["view_count"],
                                    values["latest_upload"],
                                    json.dumps(values["external_links"]),
                                    json.dumps(values["jurisdiction_website_back_links"]),
                                    values["back_links_to_jurisdiction_website"],
                                    values["official_meeting_confidence"],
                                    values["youtube_channel_id"],
                                    row["id"],
                                ),
                            )
                            conn.commit()
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

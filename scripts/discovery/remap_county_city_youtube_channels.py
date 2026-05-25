#!/usr/bin/env python3
"""
Remap municipal/town YouTube channels off county (or CDP) jurisdictions.

For each row attached to the wrong local government:
1. Resolve target place from ``City/Town of …`` title (includes New England ``township`` rows).
2. If the place already has the same channel URL → delete the wrong row.
3. Otherwise → upsert under the correct jurisdiction and delete the wrong row.

Usage:
  .venv/bin/python scripts/discovery/remap_county_city_youtube_channels.py --dry-run
  .venv/bin/python scripts/discovery/remap_county_city_youtube_channels.py --states AL,GA,MA
  .venv/bin/python scripts/discovery/remap_county_city_youtube_channels.py --table verified
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.discovery.bronze_jurisdiction_youtube_persist import (  # noqa: E402
    upsert_bronze_jurisdiction_youtube_verified,
)
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url  # noqa: E402
from scripts.discovery.youtube_city_channel_remap import (  # noqa: E402
    build_local_place_index,
    channel_url_key,
    is_misassigned_local_place_channel,
    lookup_local_place_jurisdiction,
    parse_municipality_name_from_channel,
    parse_place_kind_from_channel,
)


def _fetch_misassigned_rows(cur, table: str, state_codes: list[str] | None) -> list[dict[str, Any]]:
    clauses = [
        """(
            y.jurisdiction_type = 'county'
            OR (
                y.jurisdiction_type = 'municipality'
                AND POSITION(' cdp' IN LOWER(j.name)) > 0
                AND LOWER(BTRIM(COALESCE(y.channel_title, ''))) ~ '^(town|village|borough) of '
            )
        )""",
        """(
            LOWER(BTRIM(COALESCE(y.channel_title, ''))) ~ '^city of '
            OR LOWER(BTRIM(COALESCE(y.channel_title, ''))) ~ '^(town|village|borough) of '
            OR POSITION('cityof' IN LOWER(y.youtube_channel_url)) > 0
        )""",
    ]
    params: list[Any] = []
    if state_codes:
        clauses.append("y.state_code = ANY(%s)")
        params.append(state_codes)
    sql = f"""
        SELECT
            y.*,
            j.name AS attached_jurisdiction_name,
            j.jurisdiction_type::text AS attached_jurisdiction_type
        FROM {table} y
        JOIN intermediate.int_jurisdictions j ON j.jurisdiction_id = y.jurisdiction_id
        WHERE {' AND '.join(clauses)}
        ORDER BY y.state_code, y.jurisdiction_id, y.id
    """
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _city_has_channel(cur, table: str, city_id: str, channel_url: str) -> bool:
    cur.execute(
        f"""
        SELECT 1
        FROM {table}
        WHERE jurisdiction_id = %s
          AND LOWER(BTRIM(youtube_channel_url)) = %s
        LIMIT 1
        """,
        (city_id, channel_url_key(channel_url)),
    )
    return cur.fetchone() is not None


def _row_to_verified_payload(row: dict[str, Any], city: dict[str, str]) -> dict[str, Any]:
    return {
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
        "back_links_to_jurisdiction_website": row.get("back_links_to_jurisdiction_website"),
        "external_links": row.get("external_links") or [],
        "jurisdiction_website_back_links": row.get("jurisdiction_website_back_links") or [],
        "is_primary": bool(row.get("is_primary")),
        "scrape_batch_id": row.get("scrape_batch_id"),
        "source": row.get("source"),
        "jurisdiction_type": city.get("jurisdiction_type") or "municipality",
        "state_code": row.get("state_code"),
        "website_url": city.get("website_url") or row.get("website_url"),
    }


def remap_table(
    database_url: str,
    *,
    table: str,
    state_codes: list[str] | None,
    dry_run: bool,
) -> dict[str, int]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    stats = {
        "scanned": 0,
        "misassigned": 0,
        "deleted_duplicate": 0,
        "moved_to_city": 0,
        "deleted_unresolved": 0,
        "unresolved": 0,
        "skipped_not_mismatch": 0,
    }
    actions: list[dict[str, Any]] = []

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            rows = _fetch_misassigned_rows(cur, table, state_codes)
            stats["scanned"] = len(rows)
            place_indexes: dict[str, dict[str, list[dict[str, str]]]] = {}

            for row in rows:
                attached_name = str(row.get("attached_jurisdiction_name") or "")
                attached_type = str(
                    row.get("attached_jurisdiction_type") or row.get("jurisdiction_type") or ""
                )
                if not is_misassigned_local_place_channel(
                    row,
                    jurisdiction_type=attached_type,
                    jurisdiction_name=attached_name,
                ):
                    stats["skipped_not_mismatch"] += 1
                    continue

                stats["misassigned"] += 1
                place = parse_municipality_name_from_channel(row)
                place_kind = parse_place_kind_from_channel(row)
                if not place:
                    stats["unresolved"] += 1
                    actions.append(
                        {
                            "action": "unresolved",
                            "table": table,
                            "from_id": row["jurisdiction_id"],
                            "channel_title": row.get("channel_title"),
                            "youtube_channel_url": row.get("youtube_channel_url"),
                        }
                    )
                    continue

                state = str(row["state_code"]).upper()[:2]
                if state not in place_indexes:
                    place_indexes[state] = build_local_place_index(cur, state_code=state)

                city = lookup_local_place_jurisdiction(
                    cur,
                    state_code=state,
                    place_name=place,
                    channel_title=str(row.get("channel_title") or ""),
                    place_kind=place_kind,
                    local_place_index=place_indexes[state],
                )
                if not city:
                    stats["unresolved"] += 1
                    actions.append(
                        {
                            "action": "no_place_match",
                            "table": table,
                            "from_id": row["jurisdiction_id"],
                            "parsed_place": place,
                            "place_kind": place_kind,
                            "channel_title": row.get("channel_title"),
                            "youtube_channel_url": row.get("youtube_channel_url"),
                        }
                    )
                    if dry_run:
                        continue
                    cur.execute(
                        f"DELETE FROM {table} WHERE id = %s",
                        (row["id"],),
                    )
                    stats["deleted_unresolved"] = stats.get("deleted_unresolved", 0) + 1
                    continue

                if city["jurisdiction_id"] == row["jurisdiction_id"]:
                    stats["skipped_not_mismatch"] += 1
                    continue

                url_key = channel_url_key(str(row["youtube_channel_url"]))
                city_id = city["jurisdiction_id"]
                from_id = row["jurisdiction_id"]
                target_type = city.get("jurisdiction_type") or "municipality"
                already = _city_has_channel(cur, table, city_id, url_key)

                action = {
                    "action": "delete_duplicate" if already else "move_to_place",
                    "table": table,
                    "from_id": from_id,
                    "to_id": city_id,
                    "to_jurisdiction_type": target_type,
                    "parsed_place": place,
                    "place_kind": place_kind,
                    "channel_title": row.get("channel_title"),
                    "youtube_channel_url": row.get("youtube_channel_url"),
                }
                actions.append(action)

                if dry_run:
                    if already:
                        stats["deleted_duplicate"] += 1
                    else:
                        stats["moved_to_city"] += 1
                    continue

                if table == "intermediate.int_events_channels":
                    if not already:
                        upsert_bronze_jurisdiction_youtube_verified(
                            database_url,
                            jurisdiction_id=city_id,
                            state_code=str(row["state_code"]),
                            jurisdiction_type=target_type,
                            jurisdiction_name=city["name"],
                            website_url=city.get("website_url") or row.get("website_url"),
                            rows=[_row_to_verified_payload(row, city)],
                            mark_primary_jurisdiction_id=None,
                        )
                        stats["moved_to_city"] += 1
                    else:
                        stats["deleted_duplicate"] += 1
                    cur.execute(
                        "DELETE FROM intermediate.int_events_channels WHERE id = %s",
                        (row["id"],),
                    )
                else:
                    if already:
                        cur.execute(
                            "DELETE FROM intermediate.int_events_channels_candidates WHERE id = %s",
                            (row["id"],),
                        )
                        stats["deleted_duplicate"] += 1
                    else:
                        cur.execute(
                            """
                            UPDATE intermediate.int_events_channels_candidates
                            SET jurisdiction_id = %s,
                                jurisdiction_type = %s,
                                website_url = COALESCE(NULLIF(BTRIM(%s), ''), website_url),
                                rejection_reason = COALESCE(rejection_reason, 'local_place_jurisdiction_mismatch'),
                                loaded_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                city_id,
                                target_type,
                                city.get("website_url") or "",
                                row["id"],
                            ),
                        )
                        stats["moved_to_city"] += 1

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    stats["actions"] = actions  # type: ignore[assignment]
    return stats


def main() -> int:
    load_dotenv(_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument(
        "--table",
        choices=("verified", "candidates", "both"),
        default="both",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-actions", type=int, default=50, help="Print first N actions")
    args = parser.parse_args()

    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1

    state_codes = [s.strip().upper() for s in (args.states or "").split(",") if s.strip()] or None
    tables: list[tuple[str, str]] = []
    if args.table in ("verified", "both"):
        tables.append(("verified", "intermediate.int_events_channels"))
    if args.table in ("candidates", "both"):
        tables.append(("candidates", "intermediate.int_events_channels_candidates"))

    combined: dict[str, Any] = {}
    for label, tbl in tables:
        stats = remap_table(dbu, table=tbl, state_codes=state_codes, dry_run=args.dry_run)
        actions = stats.pop("actions", [])
        combined[label] = stats
        for action in actions[: args.limit_actions]:
            print(json.dumps(action, default=str))
        if len(actions) > args.limit_actions:
            print(f"... and {len(actions) - args.limit_actions} more {label} actions")

    print(json.dumps(combined, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

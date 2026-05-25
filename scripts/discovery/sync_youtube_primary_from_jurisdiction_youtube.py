#!/usr/bin/env python3
"""
Promote one primary YouTube channel per jurisdiction onto ``*_scraped`` tables.

``intermediate.int_events_channels`` is the **golden** table: verified county/municipality channels.
above the pilot insert threshold (default 0.5) is kept. County/municipality scraped
tables should expose **one** high-confidence primary for downstream loaders (e.g.
``load_youtube_events_to_postgres.py --channel-source counties-scraped``).

This script reads pilot rows, applies ``pick_primary_youtube_channel``, and updates
``youtube_channel_url`` / ``youtube_channel_selection_*`` on
``bronze_jurisdictions_{counties,municipalities}_scraped`` (by ``geoid``).

Usage (repo root):
  .venv/bin/python scripts/discovery/sync_youtube_primary_from_jurisdiction_youtube.py \\
    --states GA --min-confidence 0.7
  .venv/bin/python scripts/discovery/sync_youtube_primary_from_jurisdiction_youtube.py \\
    --states AL,GA,IN,MA,WA,WI --counties-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url
from scripts.discovery.youtube_primary_channel import pick_primary_youtube_channel

_COUNTIES = "bronze.bronze_jurisdictions_counties_scraped"
_MUNICIPALITIES = "bronze.bronze_jurisdictions_municipalities_scraped"


def _channel_dict(row: tuple[Any, ...], colnames: list[str]) -> dict[str, Any]:
    d = dict(zip(colnames, row, strict=True))
    return {
        "channel_url": d.get("youtube_channel_url"),
        "youtube_channel_url": d.get("youtube_channel_url"),
        "discovery_method": d.get("discovery_method"),
        "youtube_channel_selection_method": d.get("discovery_method"),
        "official_meeting_confidence": d.get("official_meeting_confidence"),
        "video_count": d.get("video_count"),
        "subscriber_count": d.get("subscriber_count"),
        "channel_title": d.get("channel_title"),
    }


def sync_primary_youtube_to_scraped(
    database_url: str,
    *,
    state_codes: list[str] | None = None,
    jurisdiction_types: tuple[str, ...] = ("county", "municipality"),
    min_confidence: float = 0.7,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Pick primary channel per jurisdiction from ``int_events_channels`` and
    upsert columns on the matching ``*_scraped`` row.
    """
    try:
        import psycopg2
    except ModuleNotFoundError as exc:
        raise SystemExit("psycopg2 required") from exc

    type_filter = list(jurisdiction_types)
    state_clause = ""
    params: list[Any] = [min_confidence, type_filter]
    if state_codes:
        state_clause = " AND j.state_code = ANY(%s)"
        params.append([s.upper() for s in state_codes])

    sql = f"""
        SELECT
            j.jurisdiction_id,
            j.geoid,
            j.jurisdiction_type::text AS jurisdiction_type,
            y.youtube_channel_url,
            y.discovery_method,
            y.official_meeting_confidence,
            y.video_count,
            y.subscriber_count,
            y.channel_title
        FROM intermediate.int_events_channels y
        INNER JOIN intermediate.int_jurisdictions j
            ON j.jurisdiction_id = y.jurisdiction_id
        WHERE COALESCE(y.official_meeting_confidence, 0) >= %s
          AND j.jurisdiction_type::text = ANY(%s)
          {state_clause}
        ORDER BY j.jurisdiction_id, y.loaded_at DESC
    """

    stats = {"jurisdictions": 0, "updated_counties": 0, "updated_municipalities": 0, "skipped_no_primary": 0}
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colnames = [d[0] for d in cur.description]
            by_jurisdiction: dict[str, list[dict[str, Any]]] = {}
            meta: dict[str, tuple[str, str]] = {}
            for row in cur.fetchall():
                d = dict(zip(colnames, row, strict=True))
                jid = str(d["jurisdiction_id"])
                by_jurisdiction.setdefault(jid, []).append(_channel_dict(row, colnames))
                meta[jid] = (str(d["geoid"]), str(d["jurisdiction_type"]))

            for jid, channels in by_jurisdiction.items():
                stats["jurisdictions"] += 1
                url, method, conf = pick_primary_youtube_channel(channels)
                if not url:
                    stats["skipped_no_primary"] += 1
                    continue
                geoid, jtype = meta[jid]
                tbl = _COUNTIES if jtype == "county" else _MUNICIPALITIES
                if jtype not in ("county", "municipality"):
                    stats["skipped_no_primary"] += 1
                    continue
                if dry_run:
                    print(f"{jtype} {geoid}: {url} ({method}, {conf})")
                    if jtype == "county":
                        stats["updated_counties"] += 1
                    else:
                        stats["updated_municipalities"] += 1
                    continue
                cur.execute(
                    f"""
                    UPDATE {tbl}
                    SET youtube_channel_url = %s,
                        youtube_channel_selection_method = %s,
                        youtube_channel_selection_confidence = %s,
                        discovered_at = NOW()
                    WHERE geoid = %s
                    """,
                    (url, method, conf, geoid),
                )
                if cur.rowcount:
                    if jtype == "county":
                        stats["updated_counties"] += cur.rowcount
                    else:
                        stats["updated_municipalities"] += cur.rowcount
        if not dry_run:
            conn.commit()
    finally:
        conn.close()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="Single USPS code")
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument("--counties-only", action="store_true")
    parser.add_argument("--municipalities-only", action="store_true")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Only consider pilot channels at or above this official_meeting_confidence (default: 0.7)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.counties_only and args.municipalities_only:
        print("Use at most one of --counties-only and --municipalities-only", file=sys.stderr)
        return 1

    state_codes: list[str] = []
    if args.states:
        state_codes = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    elif args.state:
        state_codes = [args.state.strip().upper()]

    include_types: tuple[str, ...]
    if args.counties_only:
        include_types = ("county",)
    elif args.municipalities_only:
        include_types = ("municipality",)
    else:
        include_types = ("county", "municipality")

    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1

    stats = sync_primary_youtube_to_scraped(
        dbu,
        state_codes=state_codes or None,
        jurisdiction_types=include_types,
        min_confidence=args.min_confidence,
        dry_run=args.dry_run,
    )
    print(json.dumps({"min_confidence": args.min_confidence, **stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

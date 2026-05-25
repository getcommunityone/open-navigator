#!/usr/bin/env python3
"""
Consolidate verified YouTube channels into ``bronze.bronze_jurisdiction_youtube``.

Sources:
- ``bronze.bronze_jurisdictions_{counties,municipalities}_scraped`` primary columns
  (often ``verified_bronze_events_youtube`` from events catalog)
- ``bronze.bronze_jurisdiction_youtube_candidates`` rows marked ``is_verified``

After consolidation, optionally sync primaries back to ``*_scraped`` via
``sync_youtube_primary_from_jurisdiction_youtube.py``.

Usage:
  .venv/bin/python scripts/discovery/consolidate_jurisdiction_youtube_channels.py --states GA
  .venv/bin/python scripts/discovery/consolidate_jurisdiction_youtube_channels.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.bronze_jurisdiction_youtube_persist import (  # noqa: E402
    upsert_bronze_jurisdiction_youtube_verified,
)
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url  # noqa: E402


def _fetch_scraped_primaries(database_url: str, state_codes: list[str] | None) -> list[dict]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    state_clause = ""
    params: list = []
    if state_codes:
        state_clause = " AND j.state_code = ANY(%s)"
        params.append([s.upper() for s in state_codes])

    sql = f"""
        SELECT
            j.jurisdiction_id,
            j.state_code,
            j.jurisdiction_type::text AS jurisdiction_type,
            s.youtube_channel_url,
            s.youtube_channel_id,
            s.youtube_channel_selection_method AS discovery_method,
            s.youtube_channel_selection_confidence AS official_meeting_confidence,
            s.homepage_url AS website_url
        FROM intermediate.int_jurisdictions j
        JOIN bronze.bronze_jurisdictions_counties_scraped s ON s.geoid = j.geoid
        WHERE j.jurisdiction_type::text = 'county'
          AND s.youtube_channel_url IS NOT NULL
          AND BTRIM(s.youtube_channel_url) <> ''
          {state_clause}
        UNION ALL
        SELECT
            j.jurisdiction_id,
            j.state_code,
            j.jurisdiction_type::text,
            s.youtube_channel_url,
            s.youtube_channel_id,
            s.youtube_channel_selection_method,
            s.youtube_channel_selection_confidence,
            s.homepage_url
        FROM intermediate.int_jurisdictions j
        JOIN bronze.bronze_jurisdictions_municipalities_scraped s ON s.geoid = j.geoid
        WHERE j.jurisdiction_type::text = 'municipality'
          AND s.youtube_channel_url IS NOT NULL
          AND BTRIM(s.youtube_channel_url) <> ''
          {state_clause}
    """
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params + params if state_codes else [])
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def consolidate(
    database_url: str,
    *,
    state_codes: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    rows = _fetch_scraped_primaries(database_url, state_codes)
    stats = {"scraped_primaries": len(rows), "upserted": 0, "skipped_low_conf": 0}
    by_jurisdiction: dict[str, list[dict]] = {}
    for row in rows:
        conf = float(row.get("official_meeting_confidence") or 0.0)
        if conf < 0.55 and not str(row.get("discovery_method") or "").startswith(
            "verified_bronze"
        ):
            stats["skipped_low_conf"] += 1
            continue
        jid = str(row["jurisdiction_id"])
        method = str(row.get("discovery_method") or "events_catalog")
        source = "events_catalog" if "verified_bronze" in method else method
        payload = {
            "youtube_channel_url": row["youtube_channel_url"],
            "youtube_channel_id": row.get("youtube_channel_id"),
            "discovery_method": method,
            "official_meeting_confidence": conf or 0.95,
            "source": source,
            "is_primary": True,
            "back_links_to_jurisdiction_website": True,
            "state_code": row["state_code"],
            "jurisdiction_type": row["jurisdiction_type"],
            "website_url": row.get("website_url"),
        }
        by_jurisdiction.setdefault(jid, []).append(payload)

    if dry_run:
        for jid, chans in sorted(by_jurisdiction.items())[:25]:
            print(jid, chans[0]["youtube_channel_url"], chans[0].get("discovery_method"))
        stats["upserted"] = sum(len(v) for v in by_jurisdiction.values())
        return stats

    for jid, chans in by_jurisdiction.items():
        stats["upserted"] += upsert_bronze_jurisdiction_youtube_verified(
            database_url,
            jurisdiction_id=jid,
            state_code=str(chans[0].get("state_code") or ""),
            jurisdiction_type=str(chans[0].get("jurisdiction_type") or ""),
            website_url=chans[0].get("website_url"),
            rows=chans,
            mark_primary_jurisdiction_id=jid,
        )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state_codes = [s.strip().upper() for s in (args.states or "").split(",") if s.strip()] or None
    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1
    stats = consolidate(dbu, state_codes=state_codes, dry_run=args.dry_run)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

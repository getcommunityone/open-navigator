#!/usr/bin/env python3
"""
Backfill ``channel_purpose`` and optionally demote non-meeting channels from canonical.

Usage:
  .venv/bin/python scripts/discovery/backfill_youtube_channel_purpose.py --dry-run
  .venv/bin/python scripts/discovery/backfill_youtube_channel_purpose.py --demote-non-meeting
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url
from scripts.discovery.youtube_channel_purpose import classify_channel_purpose
from scripts.discovery.youtube_channel_verification import (
    qualifies_for_bronze_jurisdiction_youtube,
)


def main() -> int:
    load_dotenv(_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", choices=("verified", "candidates", "both"), default="both")
    parser.add_argument(
        "--demote-non-meeting",
        action="store_true",
        help="Delete verified rows that no longer pass purpose-aware verification",
    )
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

    stats = {"tagged": 0, "demoted": 0}
    conn = psycopg2.connect(dbu)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for tbl in tables:
                cur.execute(
                    f"""
                    SELECT y.*, j.name AS jurisdiction_name
                    FROM {tbl} y
                    LEFT JOIN intermediate.int_jurisdictions j
                      ON j.jurisdiction_id = y.jurisdiction_id
                    WHERE y.youtube_channel_url IS NOT NULL
                      AND BTRIM(y.youtube_channel_url) <> ''
                    """
                )
                for row in cur.fetchall():
                    purpose = classify_channel_purpose(
                        channel_title=str(row.get("channel_title") or ""),
                        channel_description=str(row.get("channel_description") or ""),
                        jurisdiction_type=str(row.get("jurisdiction_type") or ""),
                    )
                    if args.dry_run:
                        print(
                            json.dumps(
                                {
                                    "table": tbl,
                                    "jurisdiction_id": row["jurisdiction_id"],
                                    "channel_title": row.get("channel_title"),
                                    "channel_purpose": purpose,
                                },
                                default=str,
                            )
                        )
                    else:
                        cur.execute(
                            f"UPDATE {tbl} SET channel_purpose = %s, loaded_at = NOW() WHERE id = %s",
                            (purpose, row["id"]),
                        )
                    stats["tagged"] += 1

                    if (
                        args.demote_non_meeting
                        and tbl == "intermediate.int_events_channels"
                    ):
                        row_dict = dict(row)
                        row_dict["channel_purpose"] = purpose
                        ok = qualifies_for_bronze_jurisdiction_youtube(
                            row_dict,
                            jurisdiction_type=str(row.get("jurisdiction_type") or ""),
                            jurisdiction_name=str(row.get("jurisdiction_name") or ""),
                            jurisdiction_state_code=str(row.get("state_code") or ""),
                            jurisdiction_homepage=str(row.get("website_url") or ""),
                        )
                        if not ok:
                            if args.dry_run:
                                print(
                                    f"DEMOTE {row['jurisdiction_id']}: {row.get('channel_title')!r} ({purpose})"
                                )
                            else:
                                cur.execute(
                                    "DELETE FROM intermediate.int_events_channels WHERE id = %s",
                                    (row["id"],),
                                )
                            stats["demoted"] += 1
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

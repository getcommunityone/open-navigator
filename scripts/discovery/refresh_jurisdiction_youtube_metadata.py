#!/usr/bin/env python3
"""
Re-fetch YouTube About-page metadata for bronze channel rows.

Fixes junk tab titles (``Home``, ``Videos``), missing ``channel_description``, and
refreshes ``external_links`` / ``jurisdiction_website_back_links``.

Usage:
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py --dry-run
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py --states AL
  .venv/bin/python scripts/discovery/refresh_jurisdiction_youtube_metadata.py \\
      --jurisdiction-id huntsville_0137000 --cookies youtube_cookies.txt
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
    if not row.get("jurisdiction_website_back_links") and row.get("back_links_to_jurisdiction_website"):
        return True
    return False


def main() -> int:
    load_dotenv(_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument("--jurisdiction-id", action="append", default=[])
    parser.add_argument("--table", choices=("verified", "candidates", "both"), default="both")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cookies", default="youtube_cookies.txt")
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
    conn = psycopg2.connect(dbu)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for tbl in tables:
                clauses = ["youtube_channel_url IS NOT NULL", "BTRIM(youtube_channel_url) <> ''"]
                params: list = []
                if state_codes:
                    clauses.append("state_code = ANY(%s)")
                    params.append(state_codes)
                if jids:
                    clauses.append("jurisdiction_id = ANY(%s)")
                    params.append(jids)
                sql = f"""
                    SELECT id, jurisdiction_id, state_code, website_url, youtube_channel_url,
                           channel_title, channel_description, jurisdiction_website_back_links,
                           back_links_to_jurisdiction_website, discovery_method
                    FROM {tbl} y
                    WHERE {' AND '.join(clauses)}
                    ORDER BY loaded_at DESC
                """
                if args.limit:
                    sql += " LIMIT %s"
                    params.append(int(args.limit))
                cur.execute(sql, params)
                rows = list(cur.fetchall())

                for row in rows:
                    if not _needs_refresh(row):
                        skipped += 1
                        continue
                    name = row["jurisdiction_id"].rsplit("_", 1)[0].replace("_", " ")
                    try:
                        enriched = enrich_channel(
                            channel={
                                "channel_url": row["youtube_channel_url"],
                                "channel_title": row.get("channel_title"),
                                "channel_description": row.get("channel_description"),
                                "discovery_method": row.get("discovery_method"),
                            },
                            jurisdiction_name=name,
                            jurisdiction_state_code=row["state_code"],
                            jurisdiction_homepage=row.get("website_url") or "",
                            cookies_file=args.cookies,
                        )
                    except Exception as exc:
                        failed += 1
                        print(f"FAIL {row['jurisdiction_id']}: {exc}")
                        continue

                    new_title = enriched.get("channel_title") or row.get("channel_title")
                    new_desc = enriched.get("channel_description") or row.get("channel_description")
                    back_links = enriched.get("jurisdiction_website_back_links") or []
                    if args.dry_run:
                        print(
                            f"{tbl} {row['jurisdiction_id']}: "
                            f"{row.get('channel_title')!r} -> {new_title!r}; "
                            f"desc={'yes' if new_desc else 'no'}; "
                            f"back_links={back_links}"
                        )
                        updated += 1
                        continue

                    cur.execute(
                        f"""
                        UPDATE {tbl}
                        SET channel_title = %s,
                            channel_description = %s,
                            external_links = %s::jsonb,
                            jurisdiction_website_back_links = %s::jsonb,
                            back_links_to_jurisdiction_website = %s,
                            loaded_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            new_title,
                            new_desc,
                            json.dumps(enriched.get("external_links") or []),
                            json.dumps(back_links),
                            bool(enriched.get("back_links_to_jurisdiction_website")),
                            row["id"],
                        ),
                    )
                    updated += 1
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    print(json.dumps({"updated": updated, "skipped": skipped, "failed": failed}, indent=2))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Merge meetings-scrape YouTube channels from ``intermediate.int_jurisdiction_meetings_scrape_youtube_channels``
into ``intermediate.int_events_channels_candidates`` and ``intermediate.int_events_channels``.

Prerequisites::

  .venv/bin/python scripts/discovery/load_scraped_meetings_manifests_to_bronze.py --state AL
  ./scripts/dbt.sh run --select int_jurisdictions int_jurisdiction_meetings_scrape_youtube_channels

Examples::

  .venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_meetings_scrape.py --dry-run
  .venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_meetings_scrape.py --states AL
  .venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_meetings_scrape.py --enrich --cookies youtube_cookies.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
from loguru import logger

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.discovery.bronze_jurisdiction_youtube_persist import (  # noqa: E402
    insert_bronze_jurisdiction_youtube_candidates,
    upsert_bronze_jurisdiction_youtube_verified,
)
from scripts.discovery.int_youtube_channel_metadata import cache_from_enriched_row  # noqa: E402
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url  # noqa: E402
from scripts.discovery.youtube_channel_purpose import classify_channel_purpose  # noqa: E402
from scrapers.discovery.youtube_channel_verification import (  # noqa: E402
    DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
    rejection_reason_for_channel,
)
from core_lib.jurisdictions.jurisdiction_id import ensure_canonical_jurisdiction_id  # noqa: E402

MEETINGS_SCRAPE_SYNC_BATCH_ID = uuid.UUID("a0000000-0000-4000-8000-000000000002")

_FETCH_SQL = """
SELECT
    ms.jurisdiction_id,
    ms.jurisdiction_name,
    ms.state_code,
    ms.jurisdiction_type,
    ms.homepage_url,
    ms.channel_url,
    ms.channel_id,
    ms.confidence_score,
    ms.discovery_method,
    ms.discovered_on,
    ms.link_type,
    ms.manifest_scraped_at,
    iw.website_url AS int_website_url
FROM intermediate.int_jurisdiction_meetings_scrape_youtube_channels ms
LEFT JOIN intermediate.int_jurisdiction_websites iw
    ON iw.jurisdiction_id = ms.jurisdiction_id
WHERE (%s::text[] IS NULL OR ms.state_code = ANY(%s::text[]))
ORDER BY ms.state_code, ms.jurisdiction_id, ms.channel_url_norm
"""


def _existing_candidate_keys(database_url: str) -> set[tuple[str, str]]:
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT jurisdiction_id, youtube_channel_url
                FROM intermediate.int_events_channels_candidates
                WHERE youtube_channel_url IS NOT NULL
                  AND BTRIM(youtube_channel_url) <> ''
                """
            )
            return {(str(r[0]), str(r[1])) for r in cur.fetchall()}
    finally:
        conn.close()


def fetch_meetings_scrape_channels(
    database_url: str,
    *,
    state_codes: list[str] | None,
) -> list[dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    states = [s.upper() for s in state_codes] if state_codes else None
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_FETCH_SQL, (states, states))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _build_row(raw: dict[str, Any]) -> dict[str, Any]:
    jtype = str(raw.get("jurisdiction_type") or "")
    title = str(raw.get("channel_title") or "")
    desc = str(raw.get("channel_description") or "")
    conf = float(raw.get("official_meeting_confidence") or raw.get("confidence_score") or 0.0)
    method = str(raw.get("discovery_method") or "website_scrape")
    external_links = raw.get("external_links") or []
    if not isinstance(external_links, list):
        external_links = []

    purpose = classify_channel_purpose(
        channel_title=title,
        channel_description=desc,
        jurisdiction_type=jtype,
    )
    row: dict[str, Any] = {
        "youtube_channel_url": raw["channel_url"],
        "youtube_channel_id": raw.get("channel_id") or raw.get("youtube_channel_id"),
        "channel_url": raw["channel_url"],
        "channel_id": raw.get("channel_id") or raw.get("youtube_channel_id"),
        "channel_title": title or None,
        "channel_description": desc or None,
        "subscriber_count": raw.get("subscriber_count"),
        "video_count": raw.get("video_count"),
        "view_count": raw.get("view_count"),
        "discovery_method": method,
        "official_meeting_confidence": conf,
        "external_links": external_links,
        "back_links_to_jurisdiction_website": bool(raw.get("back_links_to_jurisdiction_website")),
        "jurisdiction_website_back_links": raw.get("jurisdiction_website_back_links") or [],
        "channel_purpose": purpose,
        "source": "meetings_scrape",
        "scrape_batch_id": str(MEETINGS_SCRAPE_SYNC_BATCH_ID),
        "raw_row": {
            "sync_source": "int_jurisdiction_meetings_scrape_youtube_channels",
            "discovered_on": raw.get("discovered_on"),
            "link_type": raw.get("link_type"),
            "confidence_score": conf,
            "discovery_method": method,
        },
    }
    rejection = rejection_reason_for_channel(
        row,
        jurisdiction_type=jtype,
        jurisdiction_name=str(raw.get("jurisdiction_name") or ""),
        jurisdiction_state_code=str(raw.get("state_code") or ""),
        jurisdiction_homepage=str(raw.get("website_url") or raw.get("int_website_url") or ""),
    )
    row["rejection_reason"] = rejection
    row["is_verified"] = rejection is None
    return row


def _maybe_enrich_rows(
    rows: list[dict[str, Any]],
    *,
    cookies_file: str | None,
    sleep: float,
) -> None:
    from scripts.datasources.jurisdiction_pilot.youtube_channel_enrich import enrich_channel

    session = requests.Session()
    for raw in rows:
        try:
            enriched = enrich_channel(
                channel={
                    "channel_url": raw["channel_url"],
                    "youtube_channel_url": raw["channel_url"],
                    "youtube_channel_id": raw.get("channel_id"),
                    "discovery_method": raw.get("discovery_method"),
                },
                jurisdiction_name=str(raw.get("jurisdiction_name") or raw["jurisdiction_id"]),
                jurisdiction_state_code=str(raw.get("state_code") or ""),
                jurisdiction_homepage=str(raw.get("website_url") or raw.get("int_website_url") or ""),
                jurisdiction_type=str(raw.get("jurisdiction_type") or ""),
                session=session,
                cookies_file=cookies_file,
            )
            raw["channel_title"] = enriched.get("channel_title")
            raw["channel_description"] = enriched.get("channel_description")
            raw["channel_id"] = enriched.get("youtube_channel_id") or raw.get("channel_id")
            raw["subscriber_count"] = enriched.get("subscriber_count")
            raw["video_count"] = enriched.get("video_count")
            raw["view_count"] = enriched.get("view_count")
            raw["external_links"] = enriched.get("external_links") or []
            raw["back_links_to_jurisdiction_website"] = enriched.get("back_links_to_jurisdiction_website")
            raw["jurisdiction_website_back_links"] = enriched.get("jurisdiction_website_back_links") or []
            raw["official_meeting_confidence"] = enriched.get("official_meeting_confidence") or raw.get(
                "confidence_score"
            )
        except Exception as exc:
            logger.warning("Enrich failed for {} {}: {}", raw.get("jurisdiction_id"), raw.get("channel_url"), exc)
        if sleep > 0:
            time.sleep(sleep)


def sync_from_meetings_scrape(
    database_url: str,
    *,
    state_codes: list[str] | None = None,
    dry_run: bool = False,
    enrich: bool = False,
    cookies_file: str | None = None,
    sleep: float = 0.5,
    min_confidence: float = DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
) -> dict[str, int]:
    pairs = fetch_meetings_scrape_channels(database_url, state_codes=state_codes)
    stats = {
        "pairs_fetched": len(pairs),
        "candidates_inserted": 0,
        "candidates_skipped_existing": 0,
        "verified_upserted": 0,
        "verified_rejected": 0,
        "jurisdictions_touched": 0,
    }
    if not pairs:
        return stats

    if enrich:
        _maybe_enrich_rows(pairs, cookies_file=cookies_file, sleep=sleep)

    existing_candidates = _existing_candidate_keys(database_url)
    candidates_by_jurisdiction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    verified_by_jurisdiction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta_by_jurisdiction: dict[str, dict[str, Any]] = {}

    for raw in pairs:
        jtype = str(raw.get("jurisdiction_type") or "")
        jid = ensure_canonical_jurisdiction_id(
            str(raw["jurisdiction_id"]),
            jurisdiction_type=jtype,
            name=str(raw.get("jurisdiction_name") or ""),
            database_url=database_url,
        )
        raw["website_url"] = raw.get("int_website_url") or raw.get("homepage_url")
        row = _build_row(raw)
        key = (jid, str(row["youtube_channel_url"]))
        meta_by_jurisdiction[jid] = {
            "state_code": raw.get("state_code"),
            "jurisdiction_type": raw.get("jurisdiction_type"),
            "jurisdiction_name": raw.get("jurisdiction_name"),
            "website_url": raw.get("website_url"),
        }
        if key in existing_candidates:
            stats["candidates_skipped_existing"] += 1
        else:
            candidates_by_jurisdiction[jid].append(row)
            stats["candidates_inserted"] += 1

        if row["is_verified"] and float(row.get("official_meeting_confidence") or 0) >= min_confidence:
            verified_by_jurisdiction[jid].append(row)
        else:
            stats["verified_rejected"] += 1

    stats["jurisdictions_touched"] = len(meta_by_jurisdiction)

    if dry_run:
        stats["verified_upserted"] = sum(len(v) for v in verified_by_jurisdiction.values())
        for jid, rows in sorted(verified_by_jurisdiction.items())[:10]:
            for row in rows[:2]:
                logger.info(
                    "[dry-run] {} {} conf={:.2f} purpose={} verified={}",
                    jid,
                    row["youtube_channel_url"],
                    float(row.get("official_meeting_confidence") or 0),
                    row.get("channel_purpose"),
                    row.get("is_verified"),
                )
        return stats

    import psycopg2

    meta_conn = psycopg2.connect(database_url) if enrich else None
    try:
        for jid, rows in candidates_by_jurisdiction.items():
            if not rows:
                continue
            meta = meta_by_jurisdiction[jid]
            insert_bronze_jurisdiction_youtube_candidates(
                database_url,
                scrape_batch_id=str(MEETINGS_SCRAPE_SYNC_BATCH_ID),
                jurisdiction_id=jid,
                state_code=str(meta.get("state_code") or ""),
                jurisdiction_type=str(meta.get("jurisdiction_type") or ""),
                jurisdiction_name=str(meta.get("jurisdiction_name") or ""),
                website_url=meta.get("website_url"),
                rows=rows,
            )

        for jid, rows in verified_by_jurisdiction.items():
            meta = meta_by_jurisdiction[jid]
            stats["verified_upserted"] += upsert_bronze_jurisdiction_youtube_verified(
                database_url,
                scrape_batch_id=str(MEETINGS_SCRAPE_SYNC_BATCH_ID),
                jurisdiction_id=jid,
                state_code=str(meta.get("state_code") or ""),
                jurisdiction_type=str(meta.get("jurisdiction_type") or ""),
                jurisdiction_name=str(meta.get("jurisdiction_name") or ""),
                website_url=meta.get("website_url"),
                rows=rows,
                mark_primary_jurisdiction_id=jid,
            )
            if meta_conn:
                for row in rows:
                    cid = row.get("youtube_channel_id") or row.get("channel_id")
                    if cid:
                        cache_from_enriched_row(
                            meta_conn,
                            channel_id=str(cid),
                            enriched=row,
                            channel_url=row.get("youtube_channel_url"),
                        )
        if meta_conn:
            meta_conn.commit()
    finally:
        if meta_conn:
            meta_conn.close()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", help="Comma-separated USPS codes")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Scrape YouTube About pages before upsert (titles, back-links, purpose)",
    )
    parser.add_argument("--cookies", default="youtube_cookies.txt")
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
    )
    args = parser.parse_args()

    state_codes = [s.strip().upper() for s in (args.states or "").split(",") if s.strip()] or None
    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1

    stats = sync_from_meetings_scrape(
        dbu,
        state_codes=state_codes,
        dry_run=args.dry_run,
        enrich=args.enrich,
        cookies_file=args.cookies if args.enrich else None,
        sleep=args.sleep,
        min_confidence=args.min_confidence,
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

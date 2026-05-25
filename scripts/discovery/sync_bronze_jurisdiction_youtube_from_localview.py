#!/usr/bin/env python3
"""
Merge LocalView channel → jurisdiction mappings from ``intermediate.int_events_channels``
into ``bronze.bronze_jurisdiction_youtube_candidates`` and ``bronze.bronze_jurisdiction_youtube``.

The dbt int layer already resolves LocalView geography
(``int_localview_jurisdiction_geography`` → ``int_localview_channel_geography`` →
``int_events_channels``). This script was missing: existing LocalView link scripts only
update ``bronze_events_youtube`` / ``bronze_events_channels``.

Prerequisites::

  ./scripts/dbt.sh run --select int_events_localview int_localview_jurisdiction_geography \\
      int_localview_channel_geography int_jurisdictions int_events_channels

Examples::

  .venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_localview.py --dry-run
  .venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_localview.py --states AL,GA
  .venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_localview.py
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.discovery.bronze_jurisdiction_youtube_persist import (  # noqa: E402
    insert_bronze_jurisdiction_youtube_candidates,
    upsert_bronze_jurisdiction_youtube_verified,
)
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url  # noqa: E402
from scripts.jurisdictions.jurisdiction_id import ensure_canonical_jurisdiction_id  # noqa: E402
from scripts.discovery.youtube_channel_purpose import classify_channel_purpose  # noqa: E402
from scripts.discovery.youtube_channel_verification import (  # noqa: E402
    DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
    rejection_reason_for_channel,
)

# Stable batch id for LocalView sync rows (scrape_batch_id is nullable on verified table).
LOCALVIEW_SYNC_BATCH_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")

_FETCH_SQL = """
WITH channel_juris AS (
    SELECT
        ec.channel_id,
        COALESCE(
            NULLIF(BTRIM(ec.channel_url), ''),
            'https://www.youtube.com/channel/' || ec.channel_id
        ) AS channel_url,
        ec.channel_title,
        ec.channel_description,
        ec.subscriber_count,
        ec.video_count,
        ec.view_count,
        ec.discovery_method,
        ec.confidence_score,
        ec.channel_external_links,
        j.elem->>'jurisdiction_id' AS jurisdiction_id,
        j.elem->>'jurisdiction_name' AS jurisdiction_name,
        j.elem->>'state_code' AS state_code,
        j.elem->>'jurisdiction_type' AS jurisdiction_type
    FROM intermediate.int_events_channels ec
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(ec.jurisdictions, '[]'::jsonb)) AS j(elem)
    WHERE ec.in_localview IS TRUE
      AND ec.jurisdictions IS NOT NULL
      AND jsonb_array_length(ec.jurisdictions) > 0
      AND NULLIF(BTRIM(j.elem->>'jurisdiction_id'), '') IS NOT NULL
      AND NULLIF(BTRIM(ec.channel_id), '') IS NOT NULL
)
SELECT
    cj.channel_id,
    cj.channel_url,
    cj.channel_title,
    cj.channel_description,
    cj.subscriber_count,
    cj.video_count,
    cj.view_count,
    cj.discovery_method,
    cj.confidence_score,
    cj.channel_external_links,
    cj.jurisdiction_id,
    cj.jurisdiction_name,
    cj.state_code,
    cj.jurisdiction_type,
    iw.website_url
FROM channel_juris cj
LEFT JOIN intermediate.int_jurisdiction_websites iw
    ON iw.jurisdiction_id = cj.jurisdiction_id
WHERE (%s::text[] IS NULL OR cj.state_code = ANY(%s::text[]))
ORDER BY cj.state_code, cj.jurisdiction_id, cj.channel_id
"""


def _existing_candidate_keys(database_url: str) -> set[tuple[str, str]]:
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT jurisdiction_id, youtube_channel_url
                FROM bronze.bronze_jurisdiction_youtube_candidates
                WHERE discovery_method LIKE 'derived_from_localview%'
                   OR discovery_method = 'localview'
                """
            )
            return {(str(r[0]), str(r[1])) for r in cur.fetchall()}
    finally:
        conn.close()


def _build_row(raw: dict[str, Any]) -> dict[str, Any]:
    jtype = str(raw.get("jurisdiction_type") or "")
    title = str(raw.get("channel_title") or "")
    desc = str(raw.get("channel_description") or "")
    conf = float(raw.get("confidence_score") or 0.0)
    method = str(raw.get("discovery_method") or "derived_from_localview")
    external_links = raw.get("channel_external_links")
    if isinstance(external_links, str):
        try:
            external_links = json.loads(external_links)
        except json.JSONDecodeError:
            external_links = []
    if not isinstance(external_links, list):
        external_links = []

    purpose = classify_channel_purpose(
        channel_title=title,
        channel_description=desc,
        jurisdiction_type=jtype,
    )
    row: dict[str, Any] = {
        "youtube_channel_url": raw["channel_url"],
        "youtube_channel_id": raw["channel_id"],
        "channel_url": raw["channel_url"],
        "channel_id": raw["channel_id"],
        "channel_title": title or None,
        "channel_description": desc or None,
        "subscriber_count": raw.get("subscriber_count"),
        "video_count": raw.get("video_count"),
        "view_count": raw.get("view_count"),
        "discovery_method": method,
        "official_meeting_confidence": conf,
        "external_links": external_links,
        "back_links_to_jurisdiction_website": False,
        "jurisdiction_website_back_links": [],
        "channel_purpose": purpose,
        "source": "localview",
        "scrape_batch_id": str(LOCALVIEW_SYNC_BATCH_ID),
        "raw_row": {
            "sync_source": "int_events_channels",
            "in_localview": True,
            "confidence_score": conf,
            "discovery_method": method,
        },
    }
    rejection = rejection_reason_for_channel(
        row,
        jurisdiction_type=jtype,
        jurisdiction_name=str(raw.get("jurisdiction_name") or ""),
        jurisdiction_state_code=str(raw.get("state_code") or ""),
        jurisdiction_homepage=str(raw.get("website_url") or ""),
    )
    row["rejection_reason"] = rejection
    row["is_verified"] = rejection is None
    return row


def fetch_localview_channel_pairs(
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


def sync_from_int_events_channels(
    database_url: str,
    *,
    state_codes: list[str] | None = None,
    dry_run: bool = False,
    min_confidence: float = DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
) -> dict[str, int]:
    pairs = fetch_localview_channel_pairs(database_url, state_codes=state_codes)
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
        if stats["verified_upserted"]:
            logger.info(
                "[dry-run] sample verified upserts (first 10 jurisdiction/channel pairs):"
            )
            shown = 0
            for jid, rows in sorted(verified_by_jurisdiction.items()):
                for row in rows:
                    logger.info(
                        "  {} {} conf={:.2f} purpose={}",
                        jid,
                        row["youtube_channel_url"],
                        float(row.get("official_meeting_confidence") or 0),
                        row.get("channel_purpose"),
                    )
                    shown += 1
                    if shown >= 10:
                        break
                if shown >= 10:
                    break
        return stats

    for jid, rows in candidates_by_jurisdiction.items():
        if not rows:
            continue
        meta = meta_by_jurisdiction[jid]
        insert_bronze_jurisdiction_youtube_candidates(
            database_url,
            scrape_batch_id=str(LOCALVIEW_SYNC_BATCH_ID),
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
            scrape_batch_id=str(LOCALVIEW_SYNC_BATCH_ID),
            jurisdiction_id=jid,
            state_code=str(meta.get("state_code") or ""),
            jurisdiction_type=str(meta.get("jurisdiction_type") or ""),
            jurisdiction_name=str(meta.get("jurisdiction_name") or ""),
            website_url=meta.get("website_url"),
            rows=rows,
        )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", help="Comma-separated USPS codes (optional filter)")
    parser.add_argument("--dry-run", action="store_true", help="Count and sample only; no writes")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
        help="Minimum confidence for verified upserts",
    )
    args = parser.parse_args()

    state_codes = [s.strip().upper() for s in (args.states or "").split(",") if s.strip()] or None
    database_url = resolve_database_url()
    if not database_url:
        logger.error("No database URL configured")
        return 1

    logger.info(
        "Sync LocalView int_events_channels → bronze_jurisdiction_youtube* (dry_run={})",
        args.dry_run,
    )
    stats = sync_from_int_events_channels(
        database_url,
        state_codes=state_codes,
        dry_run=args.dry_run,
        min_confidence=args.min_confidence,
    )
    logger.info("Done: {}", json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

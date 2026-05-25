#!/usr/bin/env python3
"""
Consolidate verified YouTube channels into ``intermediate.int_events_channels``.

Sources (all states by default; optional ``--states`` filter):
- ``bronze.bronze_jurisdictions_{counties,municipalities}_scraped`` primary columns
- ``intermediate.int_events_channels_candidates`` rows with ``is_verified = true``
- ``bronze.bronze_events_youtube`` catalog (primary channel by video count) for gaps

After consolidation, optionally sync primaries back to ``*_scraped`` via
``sync_youtube_primary_from_jurisdiction_youtube.py``.

Usage:
  .venv/bin/python scripts/discovery/consolidate_jurisdiction_youtube_channels.py
  .venv/bin/python scripts/discovery/consolidate_jurisdiction_youtube_channels.py --states MA,AL
  .venv/bin/python scripts/discovery/consolidate_jurisdiction_youtube_channels.py --dry-run
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

from scripts.discovery.bronze_jurisdiction_youtube_persist import (  # noqa: E402
    upsert_bronze_jurisdiction_youtube_verified,
)
from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url  # noqa: E402
from scripts.discovery.int_youtube_channel_metadata import metadata_dict_for_channel  # noqa: E402
from scripts.discovery.youtube_channel_verification import (  # noqa: E402
    DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
    events_catalog_auto_confidence_cap,
    qualifies_for_bronze_jurisdiction_youtube,
)

_MIN_CONFIDENCE = DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE
_GOLDEN_TYPES = ("county", "municipality")


def _state_filter_clause(state_codes: list[str] | None, *, alias: str = "j") -> tuple[str, list]:
    if not state_codes:
        return "", []
    return f" AND {alias}.state_code = ANY(%s)", [[s.upper() for s in state_codes]]


def _enrich_channel_ids(database_url: str, rows: list[dict]) -> None:
    """Fill ``youtube_channel_id`` from bronze catalog when missing."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    need = [
        r
        for r in rows
        if (r.get("youtube_channel_url") or "").strip()
        and not (str(r.get("youtube_channel_id") or "").strip().startswith("UC"))
    ]
    if not need:
        return

    jids = sorted({str(r["jurisdiction_id"]) for r in need})
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT jurisdiction_id, channel_id, channel_url, COUNT(*) AS n
                FROM bronze.bronze_events_youtube
                WHERE jurisdiction_id = ANY(%s)
                  AND channel_id IS NOT NULL
                  AND BTRIM(channel_id) LIKE 'UC%%'
                GROUP BY jurisdiction_id, channel_id, channel_url
                """,
                (jids,),
            )
            by_jurisdiction: dict[str, list[dict]] = {}
            for rec in cur.fetchall():
                by_jurisdiction.setdefault(str(rec["jurisdiction_id"]), []).append(dict(rec))
    finally:
        conn.close()

    for row in need:
        jid = str(row["jurisdiction_id"])
        catalog = by_jurisdiction.get(jid) or []
        if not catalog:
            continue
        url = (row.get("youtube_channel_url") or "").strip().rstrip("/").lower()
        matched = None
        for rec in catalog:
            cu = (rec.get("channel_url") or "").strip().rstrip("/").lower()
            if url and cu and (url in cu or cu in url):
                matched = rec
                break
        if matched is None:
            matched = max(catalog, key=lambda r: int(r.get("n") or 0))
        row["youtube_channel_id"] = matched.get("channel_id")


def _attach_metadata(database_url: str, rows: list[dict]) -> None:
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        for row in rows:
            cid = (row.get("youtube_channel_id") or "").strip()
            if not cid:
                continue
            meta = metadata_dict_for_channel(conn, cid)
            if not meta:
                continue
            row["channel_title"] = meta.get("channel_title") or row.get("channel_title")
            row["channel_description"] = meta.get("channel_description")
            row["subscriber_count"] = meta.get("subscriber_count")
            row["video_count"] = meta.get("video_count")
            row["view_count"] = meta.get("view_count")
    finally:
        conn.close()


def _fetch_scraped_primaries(
    database_url: str, state_codes: list[str] | None
) -> list[dict]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    state_clause, params = _state_filter_clause(state_codes)

    sql = f"""
        SELECT
            j.jurisdiction_id,
            j.name AS jurisdiction_name,
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
            j.name AS jurisdiction_name,
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


def _fetch_verified_candidates(
    database_url: str, state_codes: list[str] | None
) -> list[dict]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    state_clause, params = _state_filter_clause(state_codes, alias="j")

    sql = f"""
        SELECT DISTINCT ON (c.jurisdiction_id, c.youtube_channel_url)
            c.jurisdiction_id,
            j.name AS jurisdiction_name,
            j.state_code,
            COALESCE(NULLIF(BTRIM(c.jurisdiction_type), ''), j.jurisdiction_type::text)
                AS jurisdiction_type,
            c.youtube_channel_url,
            c.youtube_channel_id,
            c.channel_title,
            c.channel_description,
            c.subscriber_count,
            c.video_count,
            c.view_count,
            c.latest_upload,
            c.discovery_method,
            c.official_meeting_confidence,
            c.website_url,
            c.back_links_to_jurisdiction_website,
            c.external_links,
            c.jurisdiction_website_back_links,
            c.channel_purpose,
            c.scrape_batch_id,
            c.scraped_at
        FROM intermediate.int_events_channels_candidates c
        INNER JOIN intermediate.int_jurisdictions j
            ON j.jurisdiction_id = c.jurisdiction_id
        WHERE c.is_verified IS TRUE
          AND c.youtube_channel_url IS NOT NULL
          AND BTRIM(c.youtube_channel_url) <> ''
          AND COALESCE(c.official_meeting_confidence, 0) >= %s
          AND COALESCE(NULLIF(BTRIM(c.jurisdiction_type), ''), j.jurisdiction_type::text)
              IN ('county', 'municipality')
          {state_clause}
        ORDER BY
            c.jurisdiction_id,
            c.youtube_channel_url,
            c.official_meeting_confidence DESC NULLS LAST,
            c.scraped_at DESC NULLS LAST
    """
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, [_MIN_CONFIDENCE, *params])
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _fetch_bronze_catalog_primaries(
    database_url: str,
    state_codes: list[str] | None,
    *,
    exclude_jurisdiction_ids: set[str] | None = None,
) -> list[dict]:
    """Best-effort primary channel from existing ``bronze_events_youtube`` rows."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    state_clause, params = _state_filter_clause(state_codes, alias="j")
    exclude = exclude_jurisdiction_ids or set()
    extra = ""
    extra_params: list[Any] = []
    if exclude:
        extra = " AND y.jurisdiction_id <> ALL(%s)"
        extra_params.append(sorted(exclude))

    sql = f"""
        WITH channel_counts AS (
            SELECT
                y.jurisdiction_id,
                j.state_code,
                y.jurisdiction_type,
                y.channel_id,
                y.channel_url,
                COUNT(*) AS video_n
            FROM bronze.bronze_events_youtube y
            INNER JOIN intermediate.int_jurisdictions j
                ON j.jurisdiction_id = y.jurisdiction_id
            WHERE y.jurisdiction_type IN ('county', 'municipality')
              AND y.channel_id IS NOT NULL
              AND BTRIM(y.channel_id) LIKE 'UC%%'
              AND y.jurisdiction_id IS NOT NULL
              {state_clause}
              {extra}
            GROUP BY y.jurisdiction_id, j.state_code, y.jurisdiction_type,
                     y.channel_id, y.channel_url
        ),
        ranked AS (
            SELECT
                cc.*,
                ROW_NUMBER() OVER (
                    PARTITION BY cc.jurisdiction_id
                    ORDER BY cc.video_n DESC, cc.channel_id
                ) AS rn
            FROM channel_counts cc
        )
        SELECT
            r.jurisdiction_id,
            j.name AS jurisdiction_name,
            r.state_code,
            r.jurisdiction_type,
            r.channel_url AS youtube_channel_url,
            r.channel_id AS youtube_channel_id
        FROM ranked r
        INNER JOIN intermediate.int_jurisdictions j
            ON j.jurisdiction_id = r.jurisdiction_id
        WHERE r.rn = 1
    """
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, [*params, *extra_params])
            out: list[dict] = []
            for rec in cur.fetchall():
                row = dict(rec)
                row["discovery_method"] = "verified_bronze_events_youtube"
                row["official_meeting_confidence"] = _MIN_CONFIDENCE
                row["website_url"] = None
                out.append(row)
            return out
    finally:
        conn.close()


def _payload_from_row(
    row: dict,
    *,
    default_primary: bool = False,
) -> dict | None:
    channel_url = (row.get("youtube_channel_url") or "").strip()
    if not channel_url:
        return None
    method = str(row.get("discovery_method") or "events_catalog")
    conf = events_catalog_auto_confidence_cap(
        method,
        float(row.get("official_meeting_confidence") or 0.0),
    )
    if conf < _MIN_CONFIDENCE and not str(method).startswith("verified_bronze"):
        return None
    eff_conf = max(conf, _MIN_CONFIDENCE) if str(method).startswith("verified_bronze") else conf
    if eff_conf < _MIN_CONFIDENCE:
        return None
    source = "events_catalog" if "verified_bronze" in method else method
    return {
        "youtube_channel_url": channel_url,
        "youtube_channel_id": row.get("youtube_channel_id"),
        "channel_title": row.get("channel_title"),
        "channel_description": row.get("channel_description"),
        "subscriber_count": row.get("subscriber_count"),
        "video_count": row.get("video_count"),
        "view_count": row.get("view_count"),
        "discovery_method": method,
        "official_meeting_confidence": eff_conf,
        "source": source,
        "is_primary": bool(row.get("is_primary")) or default_primary,
        "back_links_to_jurisdiction_website": row.get(
            "back_links_to_jurisdiction_website"
        ),
        "external_links": row.get("external_links"),
        "jurisdiction_website_back_links": row.get("jurisdiction_website_back_links"),
        "channel_purpose": row.get("channel_purpose"),
        "state_code": row.get("state_code"),
        "jurisdiction_type": row.get("jurisdiction_type"),
        "website_url": row.get("website_url"),
        "scrape_batch_id": row.get("scrape_batch_id"),
    }


def _merge_channel(
    by_jurisdiction: dict[str, list[dict]],
    row: dict,
    payload: dict,
) -> None:
    jid = str(row["jurisdiction_id"])
    url = payload["youtube_channel_url"]
    existing = by_jurisdiction.get(jid) or []
    for item in existing:
        if item.get("youtube_channel_url") == url:
            if (payload.get("official_meeting_confidence") or 0) >= (
                item.get("official_meeting_confidence") or 0
            ):
                item.update(payload)
            return
    existing.append(payload)
    by_jurisdiction[jid] = existing


def consolidate(
    database_url: str,
    *,
    state_codes: list[str] | None = None,
    dry_run: bool = False,
    include_bronze_catalog: bool = True,
) -> dict[str, int]:
    stats: dict[str, int] = {
        "scraped_primaries": 0,
        "verified_candidates": 0,
        "bronze_catalog": 0,
        "jurisdictions_upserted": 0,
        "channels_upserted": 0,
        "skipped_low_conf": 0,
        "skipped_verification": 0,
        "skipped_no_channel_id": 0,
    }
    by_jurisdiction: dict[str, list[dict]] = {}

    scraped = _fetch_scraped_primaries(database_url, state_codes)
    stats["scraped_primaries"] = len(scraped)
    _enrich_channel_ids(database_url, scraped)
    _attach_metadata(database_url, scraped)

    for row in scraped:
        payload = _payload_from_row(row, default_primary=True)
        if payload is None:
            stats["skipped_low_conf"] += 1
            continue
        if not qualifies_for_bronze_jurisdiction_youtube(
            payload,
            jurisdiction_type=str(row.get("jurisdiction_type") or ""),
            jurisdiction_name=str(row.get("jurisdiction_name") or ""),
            jurisdiction_state_code=str(row.get("state_code") or ""),
            jurisdiction_homepage=str(row.get("website_url") or ""),
        ):
            stats["skipped_verification"] += 1
            continue
        _merge_channel(by_jurisdiction, row, payload)

    verified = _fetch_verified_candidates(database_url, state_codes)
    stats["verified_candidates"] = len(verified)
    _enrich_channel_ids(database_url, verified)
    _attach_metadata(database_url, verified)

    for row in verified:
        payload = _payload_from_row(row, default_primary=False)
        if payload is None:
            stats["skipped_low_conf"] += 1
            continue
        # Trust candidate audit flag — already passed discovery verification.
        _merge_channel(by_jurisdiction, row, payload)

    if include_bronze_catalog:
        have_jids = set(by_jurisdiction.keys())
        bronze_rows = _fetch_bronze_catalog_primaries(
            database_url,
            state_codes,
            exclude_jurisdiction_ids=have_jids,
        )
        stats["bronze_catalog"] = len(bronze_rows)
        _attach_metadata(database_url, bronze_rows)
        for row in bronze_rows:
            payload = _payload_from_row(row, default_primary=True)
            if payload is None:
                stats["skipped_low_conf"] += 1
                continue
            # Trust existing bronze catalog (prior loader runs).
            _merge_channel(by_jurisdiction, row, payload)

    if dry_run:
        for jid, chans in sorted(by_jurisdiction.items())[:40]:
            cid = chans[0].get("youtube_channel_id") or "?"
            print(jid, cid, chans[0]["youtube_channel_url"], chans[0].get("discovery_method"))
        stats["channels_upserted"] = sum(len(v) for v in by_jurisdiction.values())
        stats["jurisdictions_upserted"] = len(by_jurisdiction)
        return stats

    for jid, chans in by_jurisdiction.items():
        ready = [
            c
            for c in chans
            if str(c.get("youtube_channel_id") or "").strip().startswith("UC")
        ]
        if not ready:
            stats["skipped_no_channel_id"] += 1
            continue
        if not any(c.get("is_primary") for c in ready):
            ready[0]["is_primary"] = True
        stats["jurisdictions_upserted"] += 1
        stats["channels_upserted"] += upsert_bronze_jurisdiction_youtube_verified(
            database_url,
            jurisdiction_id=jid,
            state_code=str(ready[0].get("state_code") or ""),
            jurisdiction_type=str(ready[0].get("jurisdiction_type") or ""),
            website_url=ready[0].get("website_url"),
            rows=ready,
            mark_primary_jurisdiction_id=jid,
        )

    # Back-compat key
    stats["upserted"] = stats["channels_upserted"]
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--states",
        help="Optional comma-separated USPS filter (default: all states)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-bronze-catalog",
        action="store_true",
        help="Do not backfill from bronze.bronze_events_youtube",
    )
    args = parser.parse_args()

    state_codes = [s.strip().upper() for s in (args.states or "").split(",") if s.strip()] or None
    dbu = resolve_database_url()
    if not dbu:
        print("No database URL", file=sys.stderr)
        return 1
    stats = consolidate(
        dbu,
        state_codes=state_codes,
        dry_run=args.dry_run,
        include_bronze_catalog=not args.no_bronze_catalog,
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

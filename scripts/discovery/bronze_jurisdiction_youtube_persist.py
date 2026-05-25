"""
Persist YouTube channel discovery rows to Neon bronze tables.

- ``bronze.bronze_jurisdiction_youtube_candidates`` — every probe (audit / review).
- ``bronze.bronze_jurisdiction_youtube`` — verified channels only (canonical).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc, assignment]

from scripts.discovery.youtube_channel_verification import canonical_source_from_row
from scripts.jurisdictions.jurisdiction_id import ensure_canonical_jurisdiction_id


def _norm_jurisdiction_type(value: Any) -> str | None:
    s = str(value or "").strip().lower()
    return s[:64] if s else None


def _row_values(
    r: Dict[str, Any],
    *,
    scrape_batch_id: str,
    jurisdiction_id: str,
    state_code_norm: str,
    jurisdiction_type: str | None,
    ocd_id: str | None,
    website_url: str | None,
    scraped_default: datetime,
) -> tuple[Any, ...] | None:
    channel_url = (r.get("youtube_channel_url") or r.get("channel_url") or "").strip()
    if not channel_url:
        return None
    raw = r.get("raw_row")
    if raw is None:
        raw = {k: v for k, v in r.items() if k not in ("scraped_at", "rejection_reason", "is_verified")}
    scraped_at = r.get("scraped_at")
    if isinstance(scraped_at, datetime):
        sa_val = scraped_at
    elif isinstance(scraped_at, str) and scraped_at.strip():
        try:
            sa_val = datetime.fromisoformat(scraped_at.strip().replace("Z", "+00:00"))
        except ValueError:
            sa_val = scraped_default
    else:
        sa_val = scraped_default
    return (
        scrape_batch_id,
        jurisdiction_id,
        _norm_jurisdiction_type(r.get("jurisdiction_type") or jurisdiction_type),
        state_code_norm,
        ocd_id,
        (website_url or "")[:4096] or None,
        channel_url[:4096],
        (r.get("youtube_channel_id") or r.get("channel_id") or "")[:128] or None,
        (r.get("channel_title") or "")[:512] or None,
        _as_int(r.get("subscriber_count")),
        _as_int(r.get("video_count")),
        _as_int(r.get("view_count")),
        (str(r.get("latest_upload") or ""))[:64] or None,
        (r.get("discovery_method") or "")[:64] or None,
        json.dumps(raw, default=str),
        sa_val,
        (r.get("channel_description") or None),
        _as_bool(r.get("back_links_to_jurisdiction_website")),
        _as_float(r.get("official_meeting_confidence")),
        json.dumps(r.get("external_links") or []),
        json.dumps(r.get("jurisdiction_website_back_links") or []),
        (str(r.get("channel_purpose") or "")[:64] or None),
    )


def insert_bronze_jurisdiction_youtube_candidates(
    database_url: str,
    *,
    scrape_batch_id: str,
    jurisdiction_id: str,
    state_code: str,
    jurisdiction_type: str | None = None,
    jurisdiction_name: str | None = None,
    ocd_id: str | None = None,
    website_url: str | None,
    rows: List[Dict[str, Any]],
) -> int:
    """Insert audit rows (all candidates). Returns number inserted."""
    if not rows or not database_url or psycopg2 is None:
        return 0
    scraped_default = datetime.now(timezone.utc)
    state_code_norm = (state_code or "").strip().upper()[:2]
    jurisdiction_type_norm = _norm_jurisdiction_type(jurisdiction_type)
    canonical_jurisdiction_id = ensure_canonical_jurisdiction_id(
        jurisdiction_id,
        jurisdiction_type=jurisdiction_type_norm,
        name=jurisdiction_name,
        database_url=database_url,
    )
    inserted = 0
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            for r in rows:
                base = _row_values(
                    r,
                    scrape_batch_id=scrape_batch_id,
                    jurisdiction_id=canonical_jurisdiction_id,
                    state_code_norm=state_code_norm,
                    jurisdiction_type=jurisdiction_type,
                    ocd_id=ocd_id,
                    website_url=website_url,
                    scraped_default=scraped_default,
                )
                if base is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO bronze.bronze_jurisdiction_youtube_candidates (
                        scrape_batch_id, jurisdiction_id, jurisdiction_type, state_code, ocd_id, website_url,
                        youtube_channel_url, youtube_channel_id, channel_title,
                        subscriber_count, video_count, view_count, latest_upload,
                        discovery_method, raw_row, scraped_at,
                        channel_description, back_links_to_jurisdiction_website,
                        official_meeting_confidence, external_links,
                        jurisdiction_website_back_links,
                        channel_purpose,
                        rejection_reason, is_verified
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                        %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s
                    )
                    """,
                    (
                        *base,
                        (r.get("rejection_reason") or None),
                        bool(r.get("is_verified")),
                    ),
                )
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted


def upsert_bronze_jurisdiction_youtube_verified(
    database_url: str,
    *,
    scrape_batch_id: str | None = None,
    jurisdiction_id: str,
    state_code: str,
    jurisdiction_type: str | None = None,
    jurisdiction_name: str | None = None,
    ocd_id: str | None = None,
    website_url: str | None,
    rows: List[Dict[str, Any]],
    mark_primary_jurisdiction_id: str | None = None,
) -> int:
    """Upsert verified channels into canonical table. Returns rows touched."""
    if not rows or not database_url or psycopg2 is None:
        return 0
    scraped_default = datetime.now(timezone.utc)
    state_code_norm = (state_code or "").strip().upper()[:2]
    jurisdiction_type_norm = _norm_jurisdiction_type(jurisdiction_type)
    canonical_jurisdiction_id = ensure_canonical_jurisdiction_id(
        jurisdiction_id,
        jurisdiction_type=jurisdiction_type_norm,
        name=jurisdiction_name,
        database_url=database_url,
    )
    primary_id = mark_primary_jurisdiction_id
    if primary_id:
        primary_id = ensure_canonical_jurisdiction_id(
            primary_id,
            jurisdiction_type=jurisdiction_type_norm,
            name=jurisdiction_name,
            database_url=database_url,
        )
    touched = 0
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            for r in rows:
                batch_id = r.get("scrape_batch_id") or scrape_batch_id
                base = _row_values(
                    r,
                    scrape_batch_id=str(batch_id or "00000000-0000-0000-0000-000000000000"),
                    jurisdiction_id=canonical_jurisdiction_id,
                    state_code_norm=state_code_norm,
                    jurisdiction_type=jurisdiction_type,
                    ocd_id=ocd_id,
                    website_url=website_url,
                    scraped_default=scraped_default,
                )
                if base is None:
                    continue
                source = canonical_source_from_row(r)
                is_primary = canonical_jurisdiction_id == primary_id and bool(
                    r.get("is_primary")
                )
                cur.execute(
                    """
                    INSERT INTO bronze.bronze_jurisdiction_youtube (
                        scrape_batch_id, jurisdiction_id, jurisdiction_type, state_code, ocd_id, website_url,
                        youtube_channel_url, youtube_channel_id, channel_title,
                        subscriber_count, video_count, view_count, latest_upload,
                        discovery_method, raw_row, scraped_at,
                        channel_description, back_links_to_jurisdiction_website,
                        official_meeting_confidence, external_links,
                        jurisdiction_website_back_links,
                        channel_purpose,
                        source, is_primary, verified_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                        %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, NOW()
                    )
                    ON CONFLICT (jurisdiction_id, youtube_channel_url)
                    DO UPDATE SET
                        jurisdiction_type = COALESCE(EXCLUDED.jurisdiction_type,
                                                     bronze.bronze_jurisdiction_youtube.jurisdiction_type),
                        youtube_channel_id = COALESCE(EXCLUDED.youtube_channel_id,
                                                      bronze.bronze_jurisdiction_youtube.youtube_channel_id),
                        channel_title = COALESCE(
                            NULLIF(EXCLUDED.channel_title, ''),
                            bronze.bronze_jurisdiction_youtube.channel_title
                        ),
                        subscriber_count = EXCLUDED.subscriber_count,
                        video_count = EXCLUDED.video_count,
                        view_count = EXCLUDED.view_count,
                        latest_upload = EXCLUDED.latest_upload,
                        discovery_method = EXCLUDED.discovery_method,
                        channel_description = COALESCE(
                            NULLIF(EXCLUDED.channel_description, ''),
                            bronze.bronze_jurisdiction_youtube.channel_description
                        ),
                        back_links_to_jurisdiction_website = EXCLUDED.back_links_to_jurisdiction_website,
                        official_meeting_confidence = EXCLUDED.official_meeting_confidence,
                        external_links = EXCLUDED.external_links,
                        jurisdiction_website_back_links = EXCLUDED.jurisdiction_website_back_links,
                        channel_purpose = COALESCE(
                            NULLIF(EXCLUDED.channel_purpose, ''),
                            bronze.bronze_jurisdiction_youtube.channel_purpose
                        ),
                        source = EXCLUDED.source,
                        is_primary = EXCLUDED.is_primary OR bronze.bronze_jurisdiction_youtube.is_primary,
                        verified_at = NOW(),
                        loaded_at = NOW()
                    """,
                    (
                        base[0] if str(base[0]) != "00000000-0000-0000-0000-000000000000" else None,
                        *base[1:],
                        source,
                        is_primary,
                    ),
                )
                touched += 1
        conn.commit()
    finally:
        conn.close()
    return touched


# Backward-compatible alias (pilot previously wrote audit rows here).
def insert_bronze_jurisdiction_youtube(
    database_url: str,
    *,
    scrape_batch_id: str,
    jurisdiction_id: str,
    state_code: str,
    ocd_id: str | None = None,
    website_url: str | None,
    rows: List[Dict[str, Any]],
) -> int:
    """Deprecated: writes verified rows only. Use candidates + upsert_verified."""
    return upsert_bronze_jurisdiction_youtube_verified(
        database_url,
        scrape_batch_id=scrape_batch_id,
        jurisdiction_id=jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=None,
        ocd_id=ocd_id,
        website_url=website_url,
        rows=rows,
    )


def _as_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "t", "1", "yes", "y"):
        return True
    if s in ("false", "f", "0", "no", "n"):
        return False
    return None

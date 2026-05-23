"""
Insert rows into ``bronze.bronze_jurisdiction_youtube`` (Neon migration 039).

One row per (jurisdiction × discovered channel). The runner is expected to dedupe
duplicate channel URLs within a single batch before calling this helper.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc, assignment]


def insert_bronze_jurisdiction_youtube(
    database_url: str,
    *,
    scrape_batch_id: str,
    jurisdiction_id: str,
    state_code: str,
    website_url: str | None,
    rows: List[Dict[str, Any]],
) -> int:
    """
    Bulk-insert YouTube channel rows for one jurisdiction. Returns number inserted.

    Each ``row`` may include: ``youtube_channel_url`` (required), ``youtube_channel_id``,
    ``channel_title``, ``subscriber_count``, ``video_count``, ``view_count``,
    ``latest_upload``, ``discovery_method``, ``confidence``, ``raw_row`` (dict),
    ``scraped_at`` (ISO str optional).
    """
    if not rows or not database_url or psycopg2 is None:
        return 0
    scraped_default = datetime.now(timezone.utc)
    state_code_norm = (state_code or "").strip().upper()[:2]
    inserted = 0
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            for r in rows:
                channel_url = (r.get("youtube_channel_url") or "").strip()
                if not channel_url:
                    continue
                raw = r.get("raw_row")
                if raw is None:
                    raw = {k: v for k, v in r.items() if k not in ("scraped_at",)}
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
                cur.execute(
                    """
                    INSERT INTO bronze.bronze_jurisdiction_youtube (
                        scrape_batch_id,
                        jurisdiction_id,
                        state_code,
                        website_url,
                        youtube_channel_url,
                        youtube_channel_id,
                        channel_title,
                        subscriber_count,
                        video_count,
                        view_count,
                        latest_upload,
                        discovery_method,
                        confidence,
                        raw_row,
                        scraped_at,
                        channel_description,
                        back_links_to_jurisdiction_website,
                        official_meeting_confidence,
                        external_links
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                        %s, %s, %s, %s::jsonb
                    )
                    """,
                    (
                        scrape_batch_id,
                        jurisdiction_id,
                        state_code_norm,
                        (website_url or "")[:4096] or None,
                        channel_url[:4096],
                        (r.get("youtube_channel_id") or r.get("channel_id") or "")[:128] or None,
                        (r.get("channel_title") or "")[:512] or None,
                        _as_int(r.get("subscriber_count")),
                        _as_int(r.get("video_count")),
                        _as_int(r.get("view_count")),
                        (str(r.get("latest_upload") or ""))[:64] or None,
                        (r.get("discovery_method") or "")[:64] or None,
                        _as_float(r.get("confidence")),
                        json.dumps(raw, default=str),
                        sa_val,
                        (r.get("channel_description") or None),
                        _as_bool(r.get("back_links_to_jurisdiction_website")),
                        _as_float(r.get("official_meeting_confidence")),
                        json.dumps(r.get("external_links") or []),
                    ),
                )
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted


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

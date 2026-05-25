"""
Build per-state YouTube URL mapping rollups by policy category for the dashboard export.
"""

from __future__ import annotations

from typing import Any

from scripts.datasources.jurisdictions.state_acs_mapping_quality import US_STATES
from scripts.discovery.state_youtube_category_classifier import (
    STATE_YOUTUBE_CATEGORIES,
    pick_best_channel_for_category,
)

_STATE_NAME_BY_CODE = {code: name for code, name, _fips in US_STATES}


def _registry_table_exists(cur) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'intermediate'
              AND table_name = 'int_events_channels_registry'
        ) AS ok
        """
    )
    return bool(cur.fetchone()["ok"])


def _events_channels_search_exists(cur) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'events_channels_search'
        ) AS ok
        """
    )
    return bool(cur.fetchone()["ok"])


def _fetch_registry_channels(cur) -> list[dict[str, Any]]:
    if _registry_table_exists(cur):
        cur.execute(
            """
            SELECT state_code::text AS state_code,
                   channel_id::text AS channel_id,
                   channel_url::text AS youtube_channel_url,
                   channel_title::text AS channel_title,
                   channel_description::text AS channel_description,
                   channel_type::text AS channel_type,
                   discovery_method::text AS discovery_method,
                   confidence_score::double precision AS confidence_score
            FROM intermediate.int_events_channels_registry
            WHERE state_code IS NOT NULL
              AND BTRIM(COALESCE(channel_url, '')) <> ''
              AND COALESCE(flagged_as_junk, FALSE) = FALSE
            """
        )
        return [dict(r) for r in cur.fetchall()]

    if _events_channels_search_exists(cur):
        cur.execute(
            """
            SELECT state_code::text AS state_code,
                   channel_id::text AS channel_id,
                   channel_url::text AS youtube_channel_url,
                   channel_title::text AS channel_title,
                   channel_description::text AS channel_description,
                   channel_type::text AS channel_type,
                   discovery_method::text AS discovery_method,
                   confidence_score::double precision AS confidence_score
            FROM public.events_channels_search
            WHERE state_code IS NOT NULL
              AND BTRIM(COALESCE(channel_url, '')) <> ''
              AND COALESCE(flagged_as_junk, FALSE) = FALSE
            """
        )
        return [dict(r) for r in cur.fetchall()]

    return []


def build_state_youtube_category_rollup(cur) -> dict[str, Any]:
    channels = _fetch_registry_channels(cur)
    by_state: dict[str, list[dict[str, Any]]] = {}
    for ch in channels:
        code = str(ch.get("state_code") or "").upper()
        if len(code) != 2:
            continue
        by_state.setdefault(code, []).append(ch)

    by_category: dict[str, list[dict[str, Any]]] = {
        cat: [] for cat in STATE_YOUTUBE_CATEGORIES
    }

    for code, name, _fips in US_STATES:
        state_channels = by_state.get(code, [])
        for category in STATE_YOUTUBE_CATEGORIES:
            pick = pick_best_channel_for_category(
                state_channels,
                state_name=name,
                state_code=code,
                category=category,
            )
            row: dict[str, Any] = {
                "state_code": code,
                "state_name": name,
                "category": category,
                "mapped": pick is not None,
            }
            if pick:
                row.update(
                    {
                        "youtube_channel_url": pick.get("youtube_channel_url"),
                        "channel_id": pick.get("channel_id"),
                        "channel_title": pick.get("channel_title"),
                        "channel_type": pick.get("channel_type"),
                        "discovery_method": pick.get("discovery_method"),
                        "match_score": pick.get("match_score"),
                        "confidence_score": pick.get("confidence_score"),
                    }
                )
            by_category[category].append(row)

    summary: dict[str, dict[str, Any]] = {}
    total = len(US_STATES)
    for category in STATE_YOUTUBE_CATEGORIES:
        mapped = sum(1 for r in by_category[category] if r.get("mapped"))
        summary[category] = {
            "total_states": total,
            "mapped": mapped,
            "missing": total - mapped,
            "pct_mapped": round(100.0 * mapped / total, 1) if total else None,
        }

    source = (
        "intermediate.int_events_channels_registry"
        if _registry_table_exists(cur)
        else (
            "public.events_channels_search"
            if _events_channels_search_exists(cur)
            else None
        )
    )

    return {
        "categories": list(STATE_YOUTUBE_CATEGORIES),
        "by_category": by_category,
        "summary": summary,
        "explained": {
            "source_table": source,
            "categories": {
                "overall": "Official / general state government YouTube channel.",
                "public_health": "State health department or public health agency channel.",
                "education": "State education department or state board of education channel.",
                "transportation": "State DOT or transportation department channel.",
            },
            "classification": (
                "Keyword scoring on channel title/description; local county/city/school "
                "meeting channels are excluded from agency categories."
            ),
        },
    }

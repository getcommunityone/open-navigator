"""Live YouTube channel + bronze video diagnostics for jurisdiction mapping quality."""

from __future__ import annotations

from typing import Any, Optional

from scripts.datasources.jurisdictions.jurisdiction_mapping_queries import (
    ENTITY_SLICE_WHERE,
    VALID_ENTITIES,
)


def build_youtube_coverage_where_asyncpg(
    entity: str,
    *,
    state_code: str | None = None,
    param_start: int = 1,
) -> tuple[str, list[object], int]:
    """WHERE clause for live YouTube coverage counts (optional state scope)."""
    if entity not in VALID_ENTITIES:
        raise ValueError(f"entity must be one of {sorted(VALID_ENTITIES)}")
    if entity in {"state", "schools"}:
        raise ValueError("YouTube coverage applies to counties, cities, and towns only.")

    parts = [f"({ENTITY_SLICE_WHERE[entity]})"]
    params: list[object] = []
    n = param_start
    st = (state_code or "").strip().upper()
    if st:
        if len(st) != 2:
            raise ValueError("state_code must be a 2-letter USPS code when provided.")
        parts.append(f"UPPER(TRIM(a.state_code::text)) = UPPER(TRIM(${n}::text))")
        params.append(st)
        n += 1
    return " AND ".join(parts), params, n


def build_youtube_diagnostics_where_asyncpg(
    entity: str,
    *,
    state_code: str,
    name_search: str | None = None,
    param_start: int = 1,
) -> tuple[str, list[object], int]:
    if entity not in VALID_ENTITIES:
        raise ValueError(f"entity must be one of {sorted(VALID_ENTITIES)}")
    if entity in {"state", "schools"}:
        raise ValueError("YouTube diagnostics apply to counties, cities, and towns only.")
    st = (state_code or "").strip().upper()
    if len(st) != 2:
        raise ValueError("state_code is required (2-letter USPS code).")

    parts = [f"({ENTITY_SLICE_WHERE[entity]})", f"UPPER(TRIM(a.state_code::text)) = UPPER(TRIM(${param_start}::text))"]
    params: list[object] = [st]
    n = param_start + 1
    if name_search:
        parts.append(f"a.name ILIKE ${n}")
        params.append(f"%{name_search.strip()}%")
        n += 1
    return " AND ".join(parts), params, n


def compute_youtube_gap_reason(row: dict[str, Any]) -> tuple[str, str]:
    """
    Return ``(reason_code, human_label)`` explaining missing or low bronze video counts.

    Golden channel = non-blank ``youtube_channel_url`` in ``intermediate.int_events_channels``
    (surfaced as ``has_youtube_channel`` on ``jurisdiction_mapping_analysis``).
    """
    has_golden = bool(row.get("has_youtube_channel"))
    n_bronze = int(row.get("n_bronze_videos") or 0)
    n_candidates = int(row.get("n_candidates") or 0)
    n_verified_candidates = int(row.get("n_verified_candidates") or 0)

    if has_golden and n_bronze > 0:
        return (
            "golden_channel_has_videos",
            "Golden channel mapped in int_events_channels; bronze has cataloged videos.",
        )
    if has_golden and n_bronze == 0:
        return (
            "golden_channel_no_bronze_videos",
            "Channel URL in int_events_channels but no rows in bronze.bronze_events_youtube — run load_youtube_events.",
        )
    if not has_golden and n_verified_candidates > 0:
        return (
            "verified_candidates_not_promoted",
            "Verified candidate(s) exist but no golden int_events_channels row — run consolidate_jurisdiction_youtube_channels.",
        )
    if not has_golden and n_candidates > 0:
        return (
            "candidates_not_verified",
            "Discovery found channel candidate(s) but none verified — review candidates or re-scrape.",
        )
    return (
        "no_channel_discovered",
        "No golden channel and no candidates — run jurisdiction YouTube discovery (scrape_priority_states / channel finder).",
    )


def golden_channel_match_sql(*, g_alias: str = "g", a_alias: str = "a") -> str:
    """
    Match ``int_events_channels`` rows to ``jurisdiction_mapping_analysis``.

    Golden URLs use ``youtube_channel_url`` (not ``website_url``). Rows are keyed by
    legacy ids such as ``cobb_13067`` while analysis uses ``county_13067`` — also match
    on Census GEOID suffix + ``jurisdiction_type``.
    """
    return f"""(
        {g_alias}.jurisdiction_id = {a_alias}.jurisdiction_id
        OR (
            NULLIF(BTRIM({a_alias}.geoid::text), '') IS NOT NULL
            AND {g_alias}.jurisdiction_type = {a_alias}.jurisdiction_type
            AND RIGHT({g_alias}.jurisdiction_id, LENGTH(BTRIM({a_alias}.geoid::text)))
                = BTRIM({a_alias}.geoid::text)
        )
    )"""


def jurisdiction_row_match_sql(*, y_alias: str = "y", a_alias: str = "a") -> str:
    """Same id / GEOID logic for ``bronze_events_youtube`` jurisdiction_id."""
    return f"""(
        {y_alias}.jurisdiction_id = {a_alias}.jurisdiction_id
        OR (
            NULLIF(BTRIM({a_alias}.geoid::text), '') IS NOT NULL
            AND RIGHT({y_alias}.jurisdiction_id, LENGTH(BTRIM({a_alias}.geoid::text)))
                = BTRIM({a_alias}.geoid::text)
        )
    )"""


_GOLDEN_MATCH = golden_channel_match_sql()
_CAND_MATCH = golden_channel_match_sql(g_alias="c", a_alias="a")
_BRONZE_MATCH = jurisdiction_row_match_sql()

YOUTUBE_COVERAGE_SUMMARY_SQL = f"""
    SELECT
        COUNT(*)::bigint AS total,
        COUNT(*) FILTER (WHERE COALESCE(golden_cnt.n_golden_channel_rows, 0) > 0)::bigint
            AS with_youtube_channel
    FROM public.jurisdiction_mapping_analysis a
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::bigint AS n_golden_channel_rows
        FROM intermediate.int_events_channels g
        WHERE {_GOLDEN_MATCH}
          AND g.youtube_channel_url IS NOT NULL
          AND BTRIM(g.youtube_channel_url) <> ''
    ) golden_cnt ON TRUE
"""

# Per-state rollup: same join shape as YOUTUBE_COVERAGE_SUMMARY_SQL, grouped by state_code.
# Replaces the static ``youtube_entity_state_rollup`` block in jurisdiction_mapping_quality.json
# for the dashboard — JSON goes stale whenever int_events_channels is reloaded.
YOUTUBE_STATE_ROLLUP_SQL = f"""
    SELECT
        UPPER(BTRIM(a.state_code::text)) AS state_code,
        COUNT(*)::bigint AS total_jurisdictions,
        COUNT(*) FILTER (WHERE COALESCE(golden_cnt.n_golden_channel_rows, 0) > 0)::bigint
            AS with_youtube_channel
    FROM public.jurisdiction_mapping_analysis a
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::bigint AS n_golden_channel_rows
        FROM intermediate.int_events_channels g
        WHERE {_GOLDEN_MATCH}
          AND g.youtube_channel_url IS NOT NULL
          AND BTRIM(g.youtube_channel_url) <> ''
    ) golden_cnt ON TRUE
"""

YOUTUBE_DIAGNOSTICS_ROW_SQL = f"""
    SELECT
        a.jurisdiction_id::text AS jurisdiction_id,
        a.name::text AS name,
        a.state_code::text AS state_code,
        a.jurisdiction_type::text AS jurisdiction_type,
        a.geoid::text AS geoid,
        a.acs_total_population::bigint AS acs_total_population,
        a.primary_website_url::text AS primary_website_url,
        COALESCE(a.has_primary_website, FALSE) AS has_primary_website,
        (COALESCE(golden_cnt.n_golden_channel_rows, 0) > 0) AS has_youtube_channel,
        golden_pick.youtube_channel_url::text AS youtube_channel_url,
        golden_pick.youtube_channel_id::text AS youtube_channel_id,
        golden_pick.discovery_method::text AS youtube_discovery_method,
        COALESCE(golden_cnt.n_golden_channel_rows, 0)::bigint AS n_golden_channel_rows,
        COALESCE(cand.n_candidates, 0)::bigint AS n_candidates,
        COALESCE(cand.n_verified_candidates, 0)::bigint AS n_verified_candidates,
        COALESCE(br.n_bronze_videos, 0)::bigint AS n_bronze_videos,
        COALESCE(cand_list.candidate_channels, '[]'::jsonb) AS candidate_channels,
        COALESCE(golden.golden_channels, '[]'::jsonb) AS golden_channels
    FROM public.jurisdiction_mapping_analysis a
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::bigint AS n_golden_channel_rows
        FROM intermediate.int_events_channels g
        WHERE {_GOLDEN_MATCH}
          AND g.youtube_channel_url IS NOT NULL
          AND BTRIM(g.youtube_channel_url) <> ''
    ) golden_cnt ON TRUE
    LEFT JOIN LATERAL (
        SELECT
            g.youtube_channel_url,
            g.youtube_channel_id,
            g.discovery_method
        FROM intermediate.int_events_channels g
        WHERE {_GOLDEN_MATCH}
          AND g.youtube_channel_url IS NOT NULL
          AND BTRIM(g.youtube_channel_url) <> ''
        ORDER BY
            CASE WHEN COALESCE(g.is_primary, FALSE) THEN 0 ELSE 1 END,
            g.verified_at DESC NULLS LAST,
            g.loaded_at DESC NULLS LAST,
            g.id DESC
        LIMIT 1
    ) golden_pick ON TRUE
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::bigint AS n_bronze_videos
        FROM bronze.bronze_events_youtube y
        WHERE {_BRONZE_MATCH}
    ) br ON TRUE
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*)::bigint AS n_candidates,
            COUNT(*) FILTER (WHERE COALESCE(c.is_verified, FALSE))::bigint AS n_verified_candidates
        FROM intermediate.int_events_channels_candidates c
        WHERE {_CAND_MATCH}
          AND c.youtube_channel_url IS NOT NULL
          AND BTRIM(c.youtube_channel_url) <> ''
    ) cand ON TRUE
    LEFT JOIN LATERAL (
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'youtube_channel_url', sub.youtube_channel_url,
                    'youtube_channel_id', sub.youtube_channel_id,
                    'channel_title', sub.channel_title,
                    'is_verified', COALESCE(sub.is_verified, FALSE),
                    'discovery_method', sub.discovery_method,
                    'official_meeting_confidence', sub.official_meeting_confidence,
                    'rejection_reason', sub.rejection_reason
                )
                ORDER BY COALESCE(sub.is_verified, FALSE) DESC,
                         sub.official_meeting_confidence DESC NULLS LAST
            ),
            '[]'::jsonb
        ) AS candidate_channels
        FROM (
            SELECT c.youtube_channel_url,
                   c.youtube_channel_id,
                   c.channel_title,
                   c.is_verified,
                   c.discovery_method,
                   c.official_meeting_confidence,
                   c.rejection_reason
            FROM intermediate.int_events_channels_candidates c
            WHERE {_CAND_MATCH}
              AND c.youtube_channel_url IS NOT NULL
              AND BTRIM(c.youtube_channel_url) <> ''
            ORDER BY COALESCE(c.is_verified, FALSE) DESC,
                     c.official_meeting_confidence DESC NULLS LAST,
                     c.loaded_at DESC NULLS LAST
            LIMIT 8
        ) sub
    ) cand_list ON TRUE
    LEFT JOIN LATERAL (
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'youtube_channel_url', g.youtube_channel_url,
                    'youtube_channel_id', g.youtube_channel_id,
                    'channel_title', g.channel_title,
                    'is_primary', COALESCE(g.is_primary, FALSE),
                    'discovery_method', g.discovery_method,
                    'verified_at', g.verified_at
                )
                ORDER BY CASE WHEN COALESCE(g.is_primary, FALSE) THEN 0 ELSE 1 END,
                         g.verified_at DESC NULLS LAST,
                         g.loaded_at DESC NULLS LAST
            ) FILTER (WHERE g.youtube_channel_url IS NOT NULL),
            '[]'::jsonb
        ) AS golden_channels
        FROM intermediate.int_events_channels g
        WHERE {_GOLDEN_MATCH}
          AND g.youtube_channel_url IS NOT NULL
          AND BTRIM(g.youtube_channel_url) <> ''
    ) golden ON TRUE
"""

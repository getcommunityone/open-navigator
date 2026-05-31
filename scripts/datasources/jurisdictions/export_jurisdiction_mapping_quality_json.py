#!/usr/bin/env python3
"""
Export ``jurisdiction_mapping_quality_summary`` (+ optional counts) to JSON for the
**Jurisdiction mapping quality** dashboard (``web_app/public/data/jurisdiction_mapping_quality.json``).

Also writes capped **drill-down** lists from ``public.jurisdiction_mapping_analysis``:

- ``drilldown.unmapped`` — jurisdictions with no primary URL (sample; see ``unmapped_total``).
- ``drilldown.mapped_url_issues`` — mapped primaries failing static syntax / host heuristics (sample; see ``mapped_url_issues_total``).

**State rollups** for the entity-first dashboard (**State analysis** tab):

- ``entity_state_rollup`` — per-state totals and coverage for four slices aligned with the UI:
  ``county``, ``municipality_incorporated_city`` (cities), ``municipality_towns_and_cdp`` (towns/CDP/other),
  ``school_district``. Each value is a list of
  ``{ state_code, total_jurisdictions, with_primary_website, pct_with_primary_website }``.

- ``youtube_entity_state_rollup`` — same shape for golden YouTube channel URLs from
  ``intermediate.int_events_channels`` (counties + municipalities only):
  ``{ state_code, total_jurisdictions, with_youtube_channel, pct_with_youtube_channel }``.

- ``state_youtube_category_rollup`` — per-state YouTube URL mapping for policy categories
  (``overall``, ``public_health``, ``education``, ``transportation``) from
  ``intermediate.int_events_channels_registry`` (title/description keyword scoring).

- ``drilldown.missing_youtube`` — sample jurisdictions without ``youtube_channel_url`` in
  ``int_events_channels`` (see ``missing_youtube_total``).

- ``states`` — one row per U.S. state/territory in the ACS list: state-level ACS tiers plus whether the
  **state government** row (``jurisdiction_type = 'state'``) has a primary URL — not a rollup of cities,
  counties, or districts in that state.
  Also ``summary_by_state_population_tier`` and ``summary_by_state_income_level`` (counts of state
  governments with / without portals in each ACS tier).

Optional env caps (defaults in parentheses): ``JURIS_MAPPING_QUALITY_UNMAPPED_CAP`` (2500),
``JURIS_MAPPING_QUALITY_MAPPED_ISSUES_CAP`` (800),
``JURIS_MAPPING_QUALITY_BUCKET_DRILL_CAP`` (500 per ACS bucket for ``entity_acs_unmapped_drill``).

Requires dbt mart tables built:
  ./scripts/dbt.sh run --select jurisdiction_mapping_analysis jurisdiction_mapping_analysis_sources \\
    jurisdiction_mapping_quality_summary jurisdiction_mapping_quality_summary_municipality_places \\
    jurisdiction_mapping_quality_summary_by_acs_population_tier \\
    jurisdiction_mapping_quality_summary_by_acs_income_level

Usage (repo root):

  # State ACS parquets (once per vintage):
  .venv/bin/python scripts/datasources/census/download_census_acs_data.py --geography state --state '*' --year 2022

  .venv/bin/python scripts/datasources/jurisdictions/export_jurisdiction_mapping_quality_json.py

Full unmapped drill-down lists (no JSON cap): ``GET /api/jurisdiction-mapping/unmapped`` (see
``api/routes/jurisdiction_mapping.py``).

Missing YouTube channel drill-down: ``GET /api/jurisdiction-mapping/missing-youtube-channel``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "web_app" / "public" / "data" / "jurisdiction_mapping_quality.json"

from scripts.datasources.jurisdictions.jurisdiction_mapping_queries import (
    ENTITY_SLICE_WHERE,
    MISSING_YOUTUBE_ROW_SELECT,
    UNMAPPED_ROW_SELECT,
    build_missing_youtube_where_psycopg,
    build_unmapped_where_psycopg,
)
from scripts.datasources.jurisdictions.state_acs_mapping_quality import build_states_payload
from scripts.datasources.jurisdictions.state_youtube_category_rollup import (
    build_state_youtube_category_rollup,
)

# Capped lists for dashboard drill-down (keep JSON size reasonable; raise via env if needed).
_UNMAPPED_CAP = int(os.environ.get("JURIS_MAPPING_QUALITY_UNMAPPED_CAP", "2500"))
_MAPPED_ISSUES_CAP = int(os.environ.get("JURIS_MAPPING_QUALITY_MAPPED_ISSUES_CAP", "800"))
_BUCKET_DRILL_CAP = int(os.environ.get("JURIS_MAPPING_QUALITY_BUCKET_DRILL_CAP", "500"))
_MISSING_YOUTUBE_CAP = int(os.environ.get("JURIS_MAPPING_QUALITY_MISSING_YOUTUBE_CAP", "2500"))

_SUMMARY_PRIMARY_FROM_COLS = """
                       primary_from_naco,
                       primary_from_uscm,
                       primary_from_nces_directory,
                       primary_from_gsa,
                       primary_from_league,
                       primary_from_wikidata,
                       primary_from_override"""

_SUMMARY_YOUTUBE_COLS = """
                       with_youtube_channel,
                       pct_with_youtube_channel"""


def _table_column_exists(cur, schema: str, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND column_name = %s
        ) AS ok
        """,
        (schema, table, column),
    )
    return bool(cur.fetchone()["ok"])


def _summary_youtube_select_fragment(enabled: bool) -> str:
    if not enabled:
        return ""
    return ",\n" + _SUMMARY_YOUTUBE_COLS

def _row_dicts(cur) -> list[dict[str, object]]:
    return [{k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()]


def _fetch_unmapped_bucket_rows(
    cur,
    *,
    entity: str,
    tier_col: str,
    bucket: str,
    limit: int,
) -> list[dict[str, object]]:
    tier_kw = (
        {"acs_population_tier": bucket}
        if tier_col == "acs_population_tier"
        else {"acs_income_level": bucket}
    )
    where_sql, params = build_unmapped_where_psycopg(entity, **tier_kw)
    cur.execute(
        f"""
        {UNMAPPED_ROW_SELECT}
        FROM public.jurisdiction_mapping_analysis
        WHERE {where_sql}
        ORDER BY state_code, name
        LIMIT %s
        """,
        (*params, limit),
    )
    return _row_dicts(cur)


def _build_entity_acs_unmapped_drill(
    cur, entity_acs_by_slice: dict[str, dict[str, list[dict[str, object]]]]
) -> dict[str, dict[str, dict[str, list[dict[str, object]]]]]:
    """Per-entity ACS bucket lists — matches table missing counts (capped per bucket)."""
    out: dict[str, dict[str, dict[str, list[dict[str, object]]]]] = {}
    for slice_key in ENTITY_SLICE_WHERE:
        slice_data = entity_acs_by_slice.get(slice_key) or {}
        out[slice_key] = {"by_population_tier": {}, "by_income_level": {}}
        for list_key, tier_col in (
            ("by_population_tier", "acs_population_tier"),
            ("by_income_level", "acs_income_level"),
        ):
            for row in slice_data.get(list_key) or []:
                total = int(row.get("total_jurisdictions") or 0)
                with_url = int(row.get("with_primary_website") or 0)
                missing = max(0, total - with_url)
                if missing <= 0:
                    continue
                bucket = str(row.get("bucket") or "")
                if not bucket:
                    continue
                limit = min(_BUCKET_DRILL_CAP, missing)
                out[slice_key][list_key][bucket] = _fetch_unmapped_bucket_rows(
                    cur,
                    entity=slice_key,
                    tier_col=tier_col,
                    bucket=bucket,
                    limit=limit,
                )
    return out


def _jsonify_value(v: object) -> object:
    """Coerce psycopg2 / Postgres types to JSON-friendly values."""
    if isinstance(v, Decimal):
        if v == v.to_integral_value():
            return int(v)
        return float(v)
    return v


def _json_default(obj: object) -> float | int:
    """Fallback for ``json.dumps`` if any ``Decimal`` slips through."""
    if isinstance(obj, Decimal):
        if obj == obj.to_integral_value():
            return int(obj)
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__!r} is not JSON serializable")


def _db_url() -> str:
    load_dotenv(ROOT / ".env")
    return (
        (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
        or (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
        or (os.getenv("NEON_DATABASE_URL") or "").strip()
        or (os.getenv("DATABASE_URL") or "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def main() -> int:
    url = _db_url()
    conn = psycopg2.connect(url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            summary_has_youtube = _table_column_exists(
                cur, "public", "jurisdiction_mapping_quality_summary", "with_youtube_channel"
            )
            analysis_has_youtube = _table_column_exists(
                cur, "public", "jurisdiction_mapping_analysis", "has_youtube_channel"
            )
            summary_youtube_sql = _summary_youtube_select_fragment(summary_has_youtube)
            if not summary_has_youtube:
                print(
                    "Note: summary marts lack with_youtube_channel — re-run dbt "
                    "jurisdiction_mapping_quality_summary+ after jurisdiction_mapping_analysis.",
                    file=sys.stderr,
                )
            if not analysis_has_youtube:
                print(
                    "Note: jurisdiction_mapping_analysis lacks has_youtube_channel — "
                    "YouTube rollups and missing-channel drill-down will be omitted.",
                    file=sys.stderr,
                )

            cur.execute(
                f"""
                SELECT jurisdiction_type::text AS jurisdiction_type,
                       total_jurisdictions,
                       with_primary_website,
                       pct_with_primary_website,
                       with_primary_url_syntax_ok,
                       pct_with_primary_url_syntax_ok,
                       with_primary_url_passes_basic_checks,
                       pct_with_primary_url_passes_basic_checks,
                       pct_syntax_ok_among_with_primary,
                       pct_basic_checks_ok_among_with_primary,
                       with_primary_url_likely_wrong_host,
                       jurisdictions_touching_naco,
                       jurisdictions_touching_uscm,
                       jurisdictions_touching_nces,
                       jurisdictions_touching_gsa,
                       jurisdictions_touching_league,
                       jurisdictions_touching_wikidata,
                       jurisdictions_touching_override,
                       {_SUMMARY_PRIMARY_FROM_COLS}{summary_youtube_sql},
                       summary_generated_at::text AS summary_generated_at
                FROM public.jurisdiction_mapping_quality_summary
                ORDER BY jurisdiction_type
                """
            )
            summary_by_type = [
                {k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()
            ]

            cur.execute(
                f"""
                SELECT municipality_place_kind::text AS municipality_place_kind,
                       total_jurisdictions,
                       with_primary_website,
                       pct_with_primary_website,
                       with_primary_url_syntax_ok,
                       pct_with_primary_url_syntax_ok,
                       with_primary_url_passes_basic_checks,
                       pct_with_primary_url_passes_basic_checks,
                       pct_syntax_ok_among_with_primary,
                       pct_basic_checks_ok_among_with_primary,
                       with_primary_url_likely_wrong_host,
                       jurisdictions_touching_naco,
                       jurisdictions_touching_uscm,
                       jurisdictions_touching_nces,
                       jurisdictions_touching_gsa,
                       jurisdictions_touching_league,
                       jurisdictions_touching_wikidata,
                       jurisdictions_touching_override,
                       {_SUMMARY_PRIMARY_FROM_COLS}{summary_youtube_sql},
                       summary_generated_at::text AS summary_generated_at
                FROM public.jurisdiction_mapping_quality_summary_municipality_places
                ORDER BY
                    CASE municipality_place_kind
                        WHEN 'incorporated_city' THEN 1
                        WHEN 'census_designated_place' THEN 2
                        WHEN 'incorporated_other' THEN 3
                        WHEN 'unknown' THEN 4
                        ELSE 5
                    END
                """
            )
            summary_municipality_by_place_kind = [
                {k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()
            ]

            cur.execute(
                f"""
                SELECT jurisdiction_type::text AS jurisdiction_type,
                       acs_population_tier::text AS acs_population_tier,
                       total_jurisdictions,
                       with_primary_website,
                       pct_with_primary_website,
                       with_primary_url_syntax_ok,
                       pct_with_primary_url_syntax_ok,
                       with_primary_url_passes_basic_checks,
                       pct_with_primary_url_passes_basic_checks,
                       pct_syntax_ok_among_with_primary,
                       pct_basic_checks_ok_among_with_primary,
                       with_primary_url_likely_wrong_host,
                       jurisdictions_touching_naco,
                       jurisdictions_touching_uscm,
                       jurisdictions_touching_nces,
                       jurisdictions_touching_gsa,
                       jurisdictions_touching_league,
                       jurisdictions_touching_wikidata,
                       jurisdictions_touching_override,
                       {_SUMMARY_PRIMARY_FROM_COLS}{summary_youtube_sql},
                       summary_generated_at::text AS summary_generated_at
                FROM public.jurisdiction_mapping_quality_summary_by_acs_population_tier
                ORDER BY
                    jurisdiction_type,
                    CASE acs_population_tier
                        WHEN 'Very Large (1M+)' THEN 1
                        WHEN 'Large (250k-1M)' THEN 2
                        WHEN 'Mid (50k-250k)' THEN 3
                        WHEN 'Small (15k-50k)' THEN 4
                        WHEN 'Very Small (<15k)' THEN 5
                        ELSE 99
                    END
                """
            )
            summary_by_acs_population_tier = [
                {k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()
            ]

            cur.execute(
                f"""
                SELECT jurisdiction_type::text AS jurisdiction_type,
                       acs_income_level::text AS acs_income_level,
                       total_jurisdictions,
                       with_primary_website,
                       pct_with_primary_website,
                       with_primary_url_syntax_ok,
                       pct_with_primary_url_syntax_ok,
                       with_primary_url_passes_basic_checks,
                       pct_with_primary_url_passes_basic_checks,
                       pct_syntax_ok_among_with_primary,
                       pct_basic_checks_ok_among_with_primary,
                       with_primary_url_likely_wrong_host,
                       jurisdictions_touching_naco,
                       jurisdictions_touching_uscm,
                       jurisdictions_touching_nces,
                       jurisdictions_touching_gsa,
                       jurisdictions_touching_league,
                       jurisdictions_touching_wikidata,
                       jurisdictions_touching_override,
                       {_SUMMARY_PRIMARY_FROM_COLS}{summary_youtube_sql},
                       summary_generated_at::text AS summary_generated_at
                FROM public.jurisdiction_mapping_quality_summary_by_acs_income_level
                ORDER BY
                    jurisdiction_type,
                    CASE acs_income_level
                        WHEN 'High Earner' THEN 1
                        WHEN 'Middle Class' THEN 2
                        WHEN 'Lower Middle' THEN 3
                        WHEN 'Low Income' THEN 4
                        ELSE 99
                    END
                """
            )
            summary_by_acs_income_level = [
                {k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT website_source::text AS website_source,
                       COUNT(DISTINCT jurisdiction_id)::bigint AS distinct_jurisdictions
                FROM public.jurisdiction_mapping_analysis_sources
                GROUP BY website_source
                ORDER BY distinct_jurisdictions DESC
                """
            )
            candidates_by_source = [
                {k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()
            ]

            cur.execute(
                "SELECT COUNT(*)::bigint AS n FROM public.jurisdiction_mapping_analysis_sources"
            )
            n_source_rows = int(_jsonify_value(cur.fetchone()["n"]))

            cur.execute(
                """
                SELECT COUNT(*)::bigint AS n
                FROM public.jurisdiction_mapping_analysis
                WHERE NOT COALESCE(has_primary_website, FALSE)
                """
            )
            unmapped_total = int(_jsonify_value(cur.fetchone()["n"]))

            cur.execute(
                """
                SELECT COUNT(*)::bigint AS n
                FROM public.jurisdiction_mapping_analysis
                WHERE COALESCE(has_primary_website, FALSE)
                  AND (
                      COALESCE(primary_url_syntax_ok, FALSE) = FALSE
                      OR COALESCE(primary_url_likely_wrong_host, FALSE) = TRUE
                      OR COALESCE(primary_url_passes_basic_checks, FALSE) = FALSE
                  )
                """
            )
            mapped_url_issues_total = int(_jsonify_value(cur.fetchone()["n"]))

            cur.execute(
                f"""
                {UNMAPPED_ROW_SELECT}
                FROM public.jurisdiction_mapping_analysis
                WHERE NOT COALESCE(has_primary_website, FALSE)
                ORDER BY jurisdiction_type, state_code, name
                LIMIT %s
                """,
                (_UNMAPPED_CAP,),
            )
            unmapped_sample = _row_dicts(cur)

            cur.execute(
                """
                SELECT jurisdiction_id::text AS jurisdiction_id,
                       name::text AS name,
                       state_code::text AS state_code,
                       jurisdiction_type::text AS jurisdiction_type,
                       geoid::text AS geoid,
                       municipality_place_kind::text AS municipality_place_kind,
                       primary_website_url::text AS primary_website_url,
                       primary_website_source::text AS primary_website_source,
                       primary_url_syntax_ok,
                       primary_url_likely_wrong_host,
                       primary_url_passes_basic_checks
                FROM public.jurisdiction_mapping_analysis
                WHERE COALESCE(has_primary_website, FALSE)
                  AND (
                      COALESCE(primary_url_syntax_ok, FALSE) = FALSE
                      OR COALESCE(primary_url_likely_wrong_host, FALSE) = TRUE
                      OR COALESCE(primary_url_passes_basic_checks, FALSE) = FALSE
                  )
                ORDER BY primary_url_likely_wrong_host DESC NULLS LAST,
                         primary_url_syntax_ok ASC NULLS LAST,
                         jurisdiction_type,
                         state_code,
                         name
                LIMIT %s
                """,
                (_MAPPED_ISSUES_CAP,),
            )
            mapped_url_issues_sample = [
                {k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()
            ]

            def _state_rollup(where_clause: str) -> list[dict[str, object]]:
                cur.execute(
                    f"""
                    SELECT state_code::text AS state_code,
                           COUNT(*)::bigint AS total_jurisdictions,
                           COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE))::bigint
                               AS with_primary_website,
                           CASE
                               WHEN COUNT(*) = 0 THEN NULL
                               ELSE ROUND(
                                   (100.0 * COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE)))
                                   / COUNT(*)::numeric,
                                   1
                               )
                           END AS pct_with_primary_website
                    FROM public.jurisdiction_mapping_analysis
                    WHERE {where_clause}
                    GROUP BY state_code
                    ORDER BY state_code
                    """
                )
                return [{k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()]

            def _youtube_state_rollup(where_clause: str) -> list[dict[str, object]]:
                cur.execute(
                    f"""
                    SELECT state_code::text AS state_code,
                           COUNT(*)::bigint AS total_jurisdictions,
                           COUNT(*) FILTER (WHERE COALESCE(has_youtube_channel, FALSE))::bigint
                               AS with_youtube_channel,
                           CASE
                               WHEN COUNT(*) = 0 THEN NULL
                               ELSE ROUND(
                                   (100.0 * COUNT(*) FILTER (WHERE COALESCE(has_youtube_channel, FALSE)))
                                   / COUNT(*)::numeric,
                                   1
                               )
                           END AS pct_with_youtube_channel
                    FROM public.jurisdiction_mapping_analysis
                    WHERE {where_clause}
                    GROUP BY state_code
                    ORDER BY state_code
                    """
                )
                return [{k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()]

            entity_state_rollup = {
                "county": _state_rollup("jurisdiction_type = 'county'"),
                "municipality_incorporated_city": _state_rollup(
                    "jurisdiction_type = 'municipality' AND municipality_place_kind = 'incorporated_city'"
                ),
                "municipality_towns_and_cdp": _state_rollup(
                    "jurisdiction_type = 'municipality' "
                    "AND municipality_place_kind IN ("
                    "'incorporated_other', 'unknown', 'census_designated_place'"
                    ")"
                ),
                "school_district": _state_rollup("jurisdiction_type = 'school_district'"),
            }

            youtube_entity_state_rollup = (
                {
                    "county": _youtube_state_rollup("jurisdiction_type = 'county'"),
                    "municipality_incorporated_city": _youtube_state_rollup(
                        "jurisdiction_type = 'municipality' AND municipality_place_kind = 'incorporated_city'"
                    ),
                    "municipality_towns_and_cdp": _youtube_state_rollup(
                        "jurisdiction_type = 'municipality' "
                        "AND municipality_place_kind IN ("
                        "'incorporated_other', 'unknown', 'census_designated_place'"
                        ")"
                    ),
                }
                if analysis_has_youtube
                else {
                    "county": [],
                    "municipality_incorporated_city": [],
                    "municipality_towns_and_cdp": [],
                }
            )

            if analysis_has_youtube:
                cur.execute(
                    """
                    SELECT COUNT(*)::bigint AS n
                    FROM public.jurisdiction_mapping_analysis
                    WHERE NOT COALESCE(has_youtube_channel, FALSE)
                      AND jurisdiction_type IN ('county', 'municipality')
                    """
                )
                missing_youtube_total = int(_jsonify_value(cur.fetchone()["n"]))

                cur.execute(
                    f"""
                    {MISSING_YOUTUBE_ROW_SELECT}
                    FROM public.jurisdiction_mapping_analysis
                    WHERE NOT COALESCE(has_youtube_channel, FALSE)
                      AND jurisdiction_type IN ('county', 'municipality')
                    ORDER BY jurisdiction_type, state_code, name
                    LIMIT %s
                    """,
                    (_MISSING_YOUTUBE_CAP,),
                )
                missing_youtube_sample = _row_dicts(cur)
            else:
                missing_youtube_total = 0
                missing_youtube_sample = []

            state_youtube_category_rollup = build_state_youtube_category_rollup(cur)

            def _state_government_mapping() -> list[dict[str, object]]:
                """One row per state government in ``jurisdiction_mapping_analysis`` (portal mapped or not)."""
                cur.execute(
                    """
                    SELECT state_code::text AS state_code,
                           jurisdiction_id::text AS jurisdiction_id,
                           1::bigint AS total_jurisdictions,
                           CASE
                               WHEN COALESCE(has_primary_website, FALSE) THEN 1
                               ELSE 0
                           END::bigint AS with_primary_website,
                           CASE
                               WHEN COALESCE(has_primary_website, FALSE) THEN 100.0
                               ELSE 0.0
                           END AS pct_with_primary_website,
                           primary_website_url::text AS primary_website_url,
                           primary_website_source::text AS primary_website_source,
                           COALESCE(n_website_candidate_rows, 0)::bigint AS n_website_candidate_rows,
                           COALESCE(has_gsa_source, FALSE) AS has_gsa_source,
                           COALESCE(has_override_source, FALSE) AS has_override_source
                    FROM public.jurisdiction_mapping_analysis
                    WHERE jurisdiction_type = 'state'
                    ORDER BY state_code
                    """
                )
                rows = [{k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()]

                cur.execute(
                    """
                    SELECT jurisdiction_id::text AS jurisdiction_id,
                           website_source::text AS website_source,
                           website_url::text AS website_url
                    FROM public.jurisdiction_mapping_analysis_sources
                    WHERE jurisdiction_type = 'state'
                      AND website_url IS NOT NULL
                      AND BTRIM(website_url) <> ''
                    ORDER BY jurisdiction_id, website_source, website_url
                    """
                )
                candidates_by_jid: dict[str, list[dict[str, str]]] = {}
                for r in cur.fetchall():
                    jid = str(r["jurisdiction_id"])
                    candidates_by_jid.setdefault(jid, []).append(
                        {
                            "source": str(r["website_source"]),
                            "url": str(r["website_url"]),
                        }
                    )

                for row in rows:
                    jid = str(row.get("jurisdiction_id") or "")
                    row["website_candidates"] = candidates_by_jid.get(jid, [])
                return rows

            mapping_state_governments = _state_government_mapping()

            def _acs_buckets_for_where(where_clause: str) -> dict[str, list[dict[str, object]]]:
                pop_order = """
                    CASE acs_population_tier
                        WHEN 'Very Large (1M+)' THEN 1
                        WHEN 'Large (250k-1M)' THEN 2
                        WHEN 'Mid (50k-250k)' THEN 3
                        WHEN 'Small (15k-50k)' THEN 4
                        WHEN 'Very Small (<15k)' THEN 5
                        ELSE 99
                    END
                """
                inc_order = """
                    CASE acs_income_level
                        WHEN 'High Earner' THEN 1
                        WHEN 'Middle Class' THEN 2
                        WHEN 'Lower Middle' THEN 3
                        WHEN 'Low Income' THEN 4
                        ELSE 99
                    END
                """

                def _rollup(tier_col: str, order_sql: str) -> list[dict[str, object]]:
                    cur.execute(
                        f"""
                        SELECT {tier_col}::text AS bucket,
                               COUNT(*)::bigint AS total_jurisdictions,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE))::bigint
                                   AS with_primary_website,
                               CASE
                                   WHEN COUNT(*) = 0 THEN NULL
                                   ELSE ROUND(
                                       (100.0 * COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE)))
                                       / COUNT(*)::numeric,
                                       1
                                   )
                               END AS pct_with_primary_website,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE) AND primary_website_source = 'naco')::bigint AS primary_from_naco,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE) AND primary_website_source = 'uscm')::bigint AS primary_from_uscm,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE) AND primary_website_source = 'nces_directory')::bigint AS primary_from_nces_directory,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE) AND primary_website_source = 'gsa')::bigint AS primary_from_gsa,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE) AND primary_website_source = 'league')::bigint AS primary_from_league,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE) AND primary_website_source = 'wikidata')::bigint AS primary_from_wikidata,
                               COUNT(*) FILTER (WHERE COALESCE(has_primary_website, FALSE) AND primary_website_source = 'override')::bigint AS primary_from_override
                        FROM public.jurisdiction_mapping_analysis
                        WHERE ({where_clause}) AND {tier_col} IS NOT NULL
                        GROUP BY {tier_col}
                        ORDER BY {order_sql}
                        """
                    )
                    return [{k: _jsonify_value(v) for k, v in dict(r).items()} for r in cur.fetchall()]

                return {
                    "by_population_tier": _rollup("acs_population_tier", pop_order),
                    "by_income_level": _rollup("acs_income_level", inc_order),
                }

            entity_acs_by_slice = {
                "cities": _acs_buckets_for_where(ENTITY_SLICE_WHERE["cities"]),
                "towns": _acs_buckets_for_where(ENTITY_SLICE_WHERE["towns"]),
                "counties": _acs_buckets_for_where(ENTITY_SLICE_WHERE["counties"]),
                "schools": _acs_buckets_for_where(ENTITY_SLICE_WHERE["schools"]),
            }
            entity_acs_unmapped_drill = _build_entity_acs_unmapped_drill(cur, entity_acs_by_slice)

    finally:
        conn.close()

    state_acs_block = build_states_payload(mapping_state_governments)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_host": url.split("@")[-1] if "@" in url else url,
        "summary_by_type": summary_by_type,
        "summary_municipality_by_place_kind": summary_municipality_by_place_kind,
        "summary_by_acs_population_tier": summary_by_acs_population_tier,
        "summary_by_acs_income_level": summary_by_acs_income_level,
        "candidates_by_source": candidates_by_source,
        "n_source_detail_rows": n_source_rows,
        "sources_explained": {
            "naco": "County association directory (NACo) — https://naco.org/",
            "uscm": "Municipal directory / U.S. Conference of Mayors–style seed (USCM bronze)",
            "nces_directory": "NCES Common Core of Data school district directory",
            "gsa": "GSA .gov domain registry (local agencies)",
            "league": "State municipal league city directories (League of Cities cache)",
            "wikidata": "Wikidata P856 official website from bronze_jurisdictions_{municipalities,counties}_wikidata",
            "override": "Curated seed jurisdiction_website_url_overrides",
        },
        "entity_state_rollup": entity_state_rollup,
        "youtube_entity_state_rollup": youtube_entity_state_rollup,
        "state_youtube_category_rollup": state_youtube_category_rollup,
        "entity_acs_by_slice": entity_acs_by_slice,
        "entity_acs_unmapped_drill": entity_acs_unmapped_drill,
        "entity_acs_bucket_drill_cap": _BUCKET_DRILL_CAP,
        "acs_vintage_year": state_acs_block.get("acs_vintage_year"),
        "acs_source": state_acs_block.get("acs_source"),
        "states": state_acs_block.get("states"),
        "summary_by_state_population_tier": state_acs_block.get("summary_by_state_population_tier"),
        "summary_by_state_income_level": state_acs_block.get("summary_by_state_income_level"),
        "state_population_tiers_explained": state_acs_block.get("state_population_tiers_explained"),
        "state_income_levels_explained": state_acs_block.get("state_income_levels_explained"),
        "drilldown": {
            "unmapped_total": unmapped_total,
            "unmapped_sample_limit": _UNMAPPED_CAP,
            "unmapped": unmapped_sample,
            "mapped_url_issues_total": mapped_url_issues_total,
            "mapped_url_issues_sample_limit": _MAPPED_ISSUES_CAP,
            "mapped_url_issues": mapped_url_issues_sample,
            "mapped_url_fields_explained": {
                "primary_url_syntax_ok": "False = primary URL fails static shape check (http(s), non-empty dotted hostname, min length). Not HTTP reachability.",
                "primary_url_likely_wrong_host": "True = hostname matches social/wiki deny heuristics (Facebook, Wikipedia, etc.) — worth human review.",
                "primary_url_passes_basic_checks": "False = fails syntax OR hits wrong-host heuristic. True = passes both static checks.",
            },
            "unmapped_context_explained": {
                "n_website_candidate_rows": "Raw website candidate rows merged from directories (still may not win source-priority primary pick).",
                "has_*_source": "True if at least one candidate row exists from that directory for this jurisdiction.",
                "acs_population_tier": "ACS B01003 size bucket when joined; null if no ACS row.",
                "acs_income_level": "ACS B19013 income bucket when joined; null if missing income.",
            },
            "missing_youtube_total": missing_youtube_total,
            "missing_youtube_sample_limit": _MISSING_YOUTUBE_CAP,
            "missing_youtube": missing_youtube_sample,
            "missing_youtube_explained": {
                "source_table": "intermediate.int_events_channels — golden verified county/municipality YouTube channel URLs.",
                "has_youtube_channel": "True when a non-blank youtube_channel_url exists for the jurisdiction (prefers is_primary).",
            },
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

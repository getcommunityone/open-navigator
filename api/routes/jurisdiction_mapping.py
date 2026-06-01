"""
Jurisdiction mapping quality drill-down (live Postgres).

Serves full unmapped lists for the Data explorer mapping dashboard — not capped like
``web_app/public/data/jurisdiction_mapping_quality.json``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from api.routes.stats_neon import get_db_pool
from scripts.datasources.jurisdictions.jurisdiction_mapping_queries import (
    MISSING_YOUTUBE_ROW_SELECT,
    UNMAPPED_ROW_SELECT,
    VALID_ENTITIES,
    build_missing_youtube_where_asyncpg,
    build_unmapped_where_asyncpg,
)

router = APIRouter(prefix="/jurisdiction-mapping", tags=["jurisdiction-mapping"])

_MAX_LIMIT = 50_000


class UnmappedJurisdictionRow(BaseModel):
    jurisdiction_id: str
    name: str
    state_code: str
    jurisdiction_type: str
    geoid: Optional[str] = None
    municipality_place_kind: Optional[str] = None
    n_website_candidate_rows: int = 0
    has_naco_source: bool = False
    has_uscm_source: bool = False
    has_nces_directory_source: bool = False
    has_gsa_source: bool = False
    has_league_source: bool = False
    has_wikidata_source: bool = False
    has_override_source: bool = False
    acs_population_tier: Optional[str] = None
    acs_income_level: Optional[str] = None


class UnmappedJurisdictionsResponse(BaseModel):
    entity: str
    state_code: Optional[str] = None
    acs_population_tier: Optional[str] = None
    acs_income_level: Optional[str] = None
    total: int = Field(description="Matching rows in jurisdiction_mapping_analysis")
    limit: int
    offset: int
    rows: List[UnmappedJurisdictionRow]


def _row_to_model(row: Any) -> UnmappedJurisdictionRow:
    d = dict(row)
    return UnmappedJurisdictionRow(
        jurisdiction_id=str(d["jurisdiction_id"]),
        name=str(d["name"]),
        state_code=str(d["state_code"]),
        jurisdiction_type=str(d["jurisdiction_type"]),
        geoid=d.get("geoid"),
        municipality_place_kind=d.get("municipality_place_kind"),
        n_website_candidate_rows=int(d.get("n_website_candidate_rows") or 0),
        has_naco_source=bool(d.get("has_naco_source")),
        has_uscm_source=bool(d.get("has_uscm_source")),
        has_nces_directory_source=bool(d.get("has_nces_directory_source")),
        has_gsa_source=bool(d.get("has_gsa_source")),
        has_league_source=bool(d.get("has_league_source")),
        has_wikidata_source=bool(d.get("has_wikidata_source")),
        has_override_source=bool(d.get("has_override_source")),
        acs_population_tier=d.get("acs_population_tier"),
        acs_income_level=d.get("acs_income_level"),
    )


@router.get("/unmapped", response_model=UnmappedJurisdictionsResponse)
async def list_unmapped_jurisdictions(
    entity: str = Query(
        ...,
        description="Dashboard slice: state, cities, towns, counties, or schools",
    ),
    state_code: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="USPS state code (e.g. AL)",
    ),
    acs_population_tier: Optional[str] = Query(
        None,
        description="ACS population bucket label (exact match)",
    ),
    acs_income_level: Optional[str] = Query(
        None,
        description="ACS income bucket label (exact match)",
    ),
    limit: int = Query(10_000, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """
    Jurisdictions with no primary website URL in ``jurisdiction_mapping_analysis``.

  Used by mapping-quality drill-downs (per state, ACS bucket, or entity slice).
    """
    entity_key = entity.strip().lower()
    if entity_key not in VALID_ENTITIES:
        raise HTTPException(
            status_code=400,
            detail=f"entity must be one of: {', '.join(sorted(VALID_ENTITIES))}",
        )

    try:
        where_sql, where_params, next_idx = build_unmapped_where_asyncpg(
            entity_key,
            state_code=state_code,
            acs_population_tier=acs_population_tier,
            acs_income_level=acs_income_level,
            param_start=1,
        )
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)::bigint
                FROM public.jurisdiction_mapping_analysis
                WHERE {where_sql}
                """,
                *where_params,
            )
            limit_idx = next_idx
            offset_idx = next_idx + 1
            rows_raw = await conn.fetch(
                f"""
                {UNMAPPED_ROW_SELECT}
                FROM public.jurisdiction_mapping_analysis
                WHERE {where_sql}
                ORDER BY state_code, jurisdiction_type, name
                LIMIT ${limit_idx} OFFSET ${offset_idx}
                """,
                *where_params,
                limit,
                offset,
            )
        rows = [_row_to_model(r) for r in rows_raw]
        return UnmappedJurisdictionsResponse(
            entity=entity_key,
            state_code=state_code.strip().upper() if state_code else None,
            acs_population_tier=acs_population_tier.strip() if acs_population_tier else None,
            acs_income_level=acs_income_level.strip() if acs_income_level else None,
            total=int(total or 0),
            limit=limit,
            offset=offset,
            rows=rows,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("list_unmapped_jurisdictions failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class MissingYoutubeChannelRow(BaseModel):
    jurisdiction_id: str
    name: str
    state_code: str
    jurisdiction_type: str
    geoid: Optional[str] = None
    municipality_place_kind: Optional[str] = None
    primary_website_url: Optional[str] = None
    has_primary_website: bool = False
    n_youtube_channel_rows: int = 0
    acs_population_tier: Optional[str] = None
    acs_income_level: Optional[str] = None


class MissingYoutubeChannelsResponse(BaseModel):
    entity: str
    state_code: Optional[str] = None
    acs_population_tier: Optional[str] = None
    acs_income_level: Optional[str] = None
    total: int = Field(description="Matching rows in jurisdiction_mapping_analysis")
    limit: int
    offset: int
    rows: List[MissingYoutubeChannelRow]


def _missing_youtube_row_to_model(row: Any) -> MissingYoutubeChannelRow:
    d = dict(row)
    return MissingYoutubeChannelRow(
        jurisdiction_id=str(d["jurisdiction_id"]),
        name=str(d["name"]),
        state_code=str(d["state_code"]),
        jurisdiction_type=str(d["jurisdiction_type"]),
        geoid=d.get("geoid"),
        municipality_place_kind=d.get("municipality_place_kind"),
        primary_website_url=d.get("primary_website_url"),
        has_primary_website=bool(d.get("has_primary_website")),
        n_youtube_channel_rows=int(d.get("n_youtube_channel_rows") or 0),
        acs_population_tier=d.get("acs_population_tier"),
        acs_income_level=d.get("acs_income_level"),
    )


@router.get("/missing-youtube-channel", response_model=MissingYoutubeChannelsResponse)
async def list_missing_youtube_channels(
    entity: str = Query(
        ...,
        description="Dashboard slice: cities, towns, or counties (county/municipality only)",
    ),
    state_code: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="USPS state code (e.g. AL)",
    ),
    acs_population_tier: Optional[str] = Query(
        None,
        description="ACS population bucket label (exact match)",
    ),
    acs_income_level: Optional[str] = Query(
        None,
        description="ACS income bucket label (exact match)",
    ),
    limit: int = Query(10_000, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """
    County / municipality jurisdictions with no golden ``youtube_channel_url`` in
    ``intermediate.int_events_channels`` (via ``jurisdiction_mapping_analysis.has_youtube_channel``).
    """
    entity_key = entity.strip().lower()
    if entity_key not in VALID_ENTITIES:
        raise HTTPException(
            status_code=400,
            detail=f"entity must be one of: {', '.join(sorted(VALID_ENTITIES))}",
        )
    if entity_key in {"state", "schools"}:
        raise HTTPException(
            status_code=400,
            detail="YouTube channel coverage applies to counties and municipalities only (cities, towns, counties).",
        )

    try:
        where_sql, where_params, next_idx = build_missing_youtube_where_asyncpg(
            entity_key,
            state_code=state_code,
            acs_population_tier=acs_population_tier,
            acs_income_level=acs_income_level,
            param_start=1,
        )
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)::bigint
                FROM public.jurisdiction_mapping_analysis
                WHERE {where_sql}
                """,
                *where_params,
            )
            limit_idx = next_idx
            offset_idx = next_idx + 1
            rows_raw = await conn.fetch(
                f"""
                {MISSING_YOUTUBE_ROW_SELECT}
                FROM public.jurisdiction_mapping_analysis
                WHERE {where_sql}
                ORDER BY state_code, jurisdiction_type, name
                LIMIT ${limit_idx} OFFSET ${offset_idx}
                """,
                *where_params,
                limit,
                offset,
            )
        rows = [_missing_youtube_row_to_model(r) for r in rows_raw]
        return MissingYoutubeChannelsResponse(
            entity=entity_key,
            state_code=state_code.strip().upper() if state_code else None,
            acs_population_tier=acs_population_tier.strip() if acs_population_tier else None,
            acs_income_level=acs_income_level.strip() if acs_income_level else None,
            total=int(total or 0),
            limit=limit,
            offset=offset,
            rows=rows,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("list_missing_youtube_channels failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class YoutubeChannelGoldenRow(BaseModel):
    youtube_channel_url: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    channel_title: Optional[str] = None
    is_primary: bool = False
    discovery_method: Optional[str] = None
    verified_at: Optional[str] = None


class YoutubeChannelCandidateRow(BaseModel):
    youtube_channel_url: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    channel_title: Optional[str] = None
    is_verified: bool = False
    discovery_method: Optional[str] = None
    official_meeting_confidence: Optional[float] = None
    rejection_reason: Optional[str] = None


class YoutubeChannelDiagnosticsRow(BaseModel):
    jurisdiction_id: str
    name: str
    state_code: str
    jurisdiction_type: str
    geoid: Optional[str] = None
    acs_total_population: Optional[int] = None
    primary_website_url: Optional[str] = None
    has_primary_website: bool = False
    has_youtube_channel: bool = False
    youtube_channel_url: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    youtube_discovery_method: Optional[str] = None
    n_golden_channel_rows: int = 0
    n_candidates: int = 0
    n_verified_candidates: int = 0
    n_bronze_videos: int = 0
    gap_reason_code: str
    gap_reason_label: str
    golden_channels: List[YoutubeChannelGoldenRow] = Field(default_factory=list)
    candidate_channels: List[YoutubeChannelCandidateRow] = Field(default_factory=list)


class YoutubeChannelCoverageResponse(BaseModel):
    entity: str
    state_code: Optional[str] = None
    total: int
    with_youtube_channel: int
    pct_with_youtube_channel: float
    source: str = Field(
        default="live_int_events_channels",
        description="Counts join intermediate.int_events_channels (not stale JSON export).",
    )


class YoutubeStateRollupRow(BaseModel):
    state_code: str
    total_jurisdictions: int
    with_youtube_channel: int
    pct_with_youtube_channel: Optional[float] = None


class YoutubeStateRollupResponse(BaseModel):
    """
    Per-state YouTube channel coverage for one entity slice. Replaces the static
    ``youtube_entity_state_rollup`` block in ``jurisdiction_mapping_quality.json``,
    which goes stale whenever ``int_events_channels`` is reloaded.
    """
    entity: str
    rows: List[YoutubeStateRollupRow]
    source: str = Field(
        default="live_int_events_channels",
        description="Counts join intermediate.int_events_channels (not stale JSON export).",
    )


class YoutubeChannelDiagnosticsResponse(BaseModel):
    entity: str
    state_code: str
    name_search: Optional[str] = None
    total: int
    rows: List[YoutubeChannelDiagnosticsRow]
    explained: Dict[str, str] = Field(
        default_factory=lambda: {
            "golden_table": "intermediate.int_events_channels",
            "candidates_table": "intermediate.int_events_channels_candidates",
            "bronze_videos": "bronze.bronze_event_youtube",
            "has_youtube_channel": (
                "True when intermediate.int_events_channels has a non-blank "
                "youtube_channel_url for this jurisdiction (matched by jurisdiction_id "
                "or GEOID suffix + jurisdiction_type — not website_url)."
            ),
            "website_url": (
                "int_events_channels.website_url is the jurisdiction portal used during "
                "discovery; golden mapping is youtube_channel_url only."
            ),
        }
    )


def _diag_row_to_model(row: Any) -> YoutubeChannelDiagnosticsRow:
    from scripts.datasources.jurisdictions.youtube_channel_diagnostics import (
        compute_youtube_gap_reason,
    )

    d = dict(row)
    code, label = compute_youtube_gap_reason(d)
    golden_raw = d.get("golden_channels")
    cand_raw = d.get("candidate_channels")
    if isinstance(golden_raw, str):
        import json

        golden_raw = json.loads(golden_raw)
    if isinstance(cand_raw, str):
        import json

        cand_raw = json.loads(cand_raw)
    golden_list = golden_raw if isinstance(golden_raw, list) else []
    cand_list = cand_raw if isinstance(cand_raw, list) else []

    return YoutubeChannelDiagnosticsRow(
        jurisdiction_id=str(d["jurisdiction_id"]),
        name=str(d["name"]),
        state_code=str(d["state_code"]),
        jurisdiction_type=str(d["jurisdiction_type"]),
        geoid=d.get("geoid"),
        acs_total_population=(int(d["acs_total_population"]) if d.get("acs_total_population") is not None else None),
        primary_website_url=d.get("primary_website_url"),
        has_primary_website=bool(d.get("has_primary_website")),
        has_youtube_channel=bool(d.get("has_youtube_channel")),
        youtube_channel_url=d.get("youtube_channel_url"),
        youtube_channel_id=d.get("youtube_channel_id"),
        youtube_discovery_method=d.get("youtube_discovery_method"),
        n_golden_channel_rows=int(d.get("n_golden_channel_rows") or 0),
        n_candidates=int(d.get("n_candidates") or 0),
        n_verified_candidates=int(d.get("n_verified_candidates") or 0),
        n_bronze_videos=int(d.get("n_bronze_videos") or 0),
        gap_reason_code=code,
        gap_reason_label=label,
        golden_channels=[YoutubeChannelGoldenRow(**x) for x in golden_list if isinstance(x, dict)],
        candidate_channels=[YoutubeChannelCandidateRow(**x) for x in cand_list if isinstance(x, dict)],
    )


@router.get("/youtube-channel-coverage", response_model=YoutubeChannelCoverageResponse)
async def youtube_channel_coverage(
    entity: str = Query(..., description="counties, cities, or towns"),
    state_code: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="Optional USPS state code (national totals when omitted)",
    ),
):
    """
    Live golden-channel coverage from ``intermediate.int_events_channels`` (GEOID-aware match).
    Use when ``jurisdiction_mapping_quality.json`` lacks ``with_youtube_channel`` (dbt not rebuilt).
    """
    from scripts.datasources.jurisdictions.youtube_channel_diagnostics import (
        YOUTUBE_COVERAGE_SUMMARY_SQL,
        build_youtube_coverage_where_asyncpg,
    )

    entity_key = entity.strip().lower()
    if entity_key not in VALID_ENTITIES:
        raise HTTPException(
            status_code=400,
            detail=f"entity must be one of: {', '.join(sorted(VALID_ENTITIES))}",
        )
    if entity_key in {"state", "schools"}:
        raise HTTPException(
            status_code=400,
            detail="YouTube channel coverage applies to counties and municipalities only.",
        )

    try:
        where_sql, where_params, _ = build_youtube_coverage_where_asyncpg(
            entity_key,
            state_code=state_code,
            param_start=1,
        )
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                {YOUTUBE_COVERAGE_SUMMARY_SQL}
                WHERE {where_sql}
                """,
                *where_params,
            )
        total = int((row["total"] if row else 0) or 0)
        with_ch = int((row["with_youtube_channel"] if row else 0) or 0)
        pct = round(100.0 * with_ch / total, 2) if total > 0 else 0.0
        st = state_code.strip().upper() if state_code else None
        return YoutubeChannelCoverageResponse(
            entity=entity_key,
            state_code=st,
            total=total,
            with_youtube_channel=with_ch,
            pct_with_youtube_channel=pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("youtube_channel_coverage failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/youtube-state-rollup", response_model=YoutubeStateRollupResponse)
async def youtube_state_rollup(
    entity: str = Query(..., description="counties, cities, or towns"),
):
    """
    Per-state YouTube channel coverage for one entity slice.

    Live source-of-truth for the dashboard's per-state rollup. Replaces the
    static ``youtube_entity_state_rollup`` block in ``jurisdiction_mapping_quality.json``,
    which goes stale whenever ``intermediate.int_events_channels`` is reloaded.
    """
    from scripts.datasources.jurisdictions.youtube_channel_diagnostics import (
        YOUTUBE_STATE_ROLLUP_SQL,
        build_youtube_coverage_where_asyncpg,
    )

    entity_key = entity.strip().lower()
    if entity_key not in VALID_ENTITIES:
        raise HTTPException(
            status_code=400,
            detail=f"entity must be one of: {', '.join(sorted(VALID_ENTITIES))}",
        )
    if entity_key in {"state", "schools"}:
        raise HTTPException(
            status_code=400,
            detail="YouTube state rollup applies to counties and municipalities only.",
        )

    try:
        # No state filter — we want every state grouped.
        where_sql, where_params, _ = build_youtube_coverage_where_asyncpg(
            entity_key,
            state_code=None,
            param_start=1,
        )
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows_raw = await conn.fetch(
                f"""
                {YOUTUBE_STATE_ROLLUP_SQL}
                WHERE {where_sql}
                GROUP BY 1
                ORDER BY 1
                """,
                *where_params,
            )
        rows: List[YoutubeStateRollupRow] = []
        for r in rows_raw:
            total = int(r["total_jurisdictions"] or 0)
            with_ch = int(r["with_youtube_channel"] or 0)
            pct = round(100.0 * with_ch / total, 2) if total > 0 else None
            rows.append(
                YoutubeStateRollupRow(
                    state_code=str(r["state_code"]),
                    total_jurisdictions=total,
                    with_youtube_channel=with_ch,
                    pct_with_youtube_channel=pct,
                )
            )
        return YoutubeStateRollupResponse(entity=entity_key, rows=rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("youtube_state_rollup failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/youtube-channel-diagnostics", response_model=YoutubeChannelDiagnosticsResponse)
async def list_youtube_channel_diagnostics(
    entity: str = Query(..., description="counties, cities, or towns"),
    state_code: str = Query(..., min_length=2, max_length=2, description="USPS state code (required)"),
    name_search: Optional[str] = Query(
        None,
        description="Case-insensitive substring on jurisdiction name (e.g. dekalb)",
    ),
    limit: int = Query(500, ge=1, le=2000),
):
    """
  Per-jurisdiction YouTube pipeline status: golden ``int_events_channels``, candidates,
  and ``bronze_event_youtube`` video counts — explains missing videos vs missing URLs.
    """
    from scripts.datasources.jurisdictions.youtube_channel_diagnostics import (
        YOUTUBE_DIAGNOSTICS_ROW_SQL,
        build_youtube_diagnostics_where_asyncpg,
    )

    entity_key = entity.strip().lower()
    if entity_key not in VALID_ENTITIES:
        raise HTTPException(
            status_code=400,
            detail=f"entity must be one of: {', '.join(sorted(VALID_ENTITIES))}",
        )

    try:
        where_sql, where_params, next_idx = build_youtube_diagnostics_where_asyncpg(
            entity_key,
            state_code=state_code,
            name_search=name_search,
            param_start=1,
        )
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)::bigint
                FROM public.jurisdiction_mapping_analysis a
                WHERE {where_sql}
                """,
                *where_params,
            )
            limit_idx = next_idx
            rows_raw = await conn.fetch(
                f"""
                {YOUTUBE_DIAGNOSTICS_ROW_SQL}
                WHERE {where_sql}
                ORDER BY a.name
                LIMIT ${limit_idx}
                """,
                *where_params,
                limit,
            )
        rows = [_diag_row_to_model(r) for r in rows_raw]
        st = state_code.strip().upper()
        return YoutubeChannelDiagnosticsResponse(
            entity=entity_key,
            state_code=st,
            name_search=name_search.strip() if name_search else None,
            total=int(total or 0),
            rows=rows,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("list_youtube_channel_diagnostics failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

"""
Jurisdiction mapping quality drill-down (live Postgres).

Serves full unmapped lists for the Data explorer mapping dashboard — not capped like
``frontend/public/data/jurisdiction_mapping_quality.json``.
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

"""
HiFLD / infrastructure points from bronze.bronze_locations.

Used by map layers (cluster map) for hospitals, places of worship, law enforcement, etc.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from api.routes.stats_neon import get_db_pool

router = APIRouter(prefix="/locations", tags=["locations"])

_MAX_LIMIT = 50_000

# Common organization_type values from load_hifld_to_postgres.py
KNOWN_ORG_TYPES = frozenset(
    {
        "place_of_worship",
        "hospital",
        "law_enforcement",
        "school",
        "fire_station",
        "government_building",
        "other",
    }
)


class LocationPoint(BaseModel):
    id: int
    name: Optional[str] = None
    organization_type: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    state: Optional[str] = None


class LocationsResponse(BaseModel):
    state: Optional[str] = None
    types: List[str] = Field(default_factory=list)
    total: int
    limit: int
    locations: List[LocationPoint]


def _parse_types(types: Optional[str]) -> List[str]:
    if not types or not types.strip():
        return []
    parsed = [t.strip().lower().replace("-", "_") for t in types.split(",") if t.strip()]
    unknown = [t for t in parsed if t not in KNOWN_ORG_TYPES]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown types: {', '.join(unknown)}. "
            f"Known: {', '.join(sorted(KNOWN_ORG_TYPES))}",
        )
    return parsed


async def _table_exists(conn) -> bool:
    row = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'bronze'
              AND table_name = 'bronze_locations'
        )
        """
    )
    return bool(row)


@router.get("", response_model=LocationsResponse)
async def list_locations(
    state: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="USPS state code (e.g. AL)",
    ),
    types: Optional[str] = Query(
        None,
        description="Comma-separated organization_type values, e.g. hospital,place_of_worship",
    ),
    limit: int = Query(10_000, ge=1, le=_MAX_LIMIT),
):
    """
    Map-ready points from ``bronze.bronze_locations`` (HiFLD and similar sources).

    Example::

        GET /api/locations?state=AL&types=hospital,place_of_worship&limit=50000
    """
    type_list = _parse_types(types)
    state_code = state.strip().upper() if state else None

    where_parts = [
        "latitude IS NOT NULL",
        "longitude IS NOT NULL",
    ]
    params: list = []
    idx = 1

    if state_code:
        where_parts.append(f"UPPER(TRIM(state)) = ${idx}")
        params.append(state_code)
        idx += 1

    if type_list:
        where_parts.append(f"organization_type = ANY(${idx}::text[])")
        params.append(type_list)
        idx += 1

    where_sql = " AND ".join(where_parts)
    limit_idx = idx
    params.append(limit)

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if not await _table_exists(conn):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "bronze.bronze_locations not found. "
                        "Run: python scripts/datasources/hifld/load_hifld_to_postgres.py"
                    ),
                )

            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)::bigint
                FROM bronze.bronze_locations
                WHERE {where_sql}
                """,
                *params[:-1],
            )

            rows = await conn.fetch(
                f"""
                SELECT
                    id,
                    name,
                    organization_type,
                    latitude::float8 AS latitude,
                    longitude::float8 AS longitude,
                    city,
                    state
                FROM bronze.bronze_locations
                WHERE {where_sql}
                ORDER BY organization_type, state, city, name
                LIMIT ${limit_idx}
                """,
                *params,
            )

        locations = [
            LocationPoint(
                id=int(r["id"]),
                name=r["name"],
                organization_type=str(r["organization_type"]),
                latitude=float(r["latitude"]),
                longitude=float(r["longitude"]),
                city=r["city"],
                state=r["state"],
            )
            for r in rows
        ]

        return LocationsResponse(
            state=state_code,
            types=type_list,
            total=int(total or 0),
            limit=limit,
            locations=locations,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("list_locations failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

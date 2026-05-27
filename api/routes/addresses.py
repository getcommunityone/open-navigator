"""
Property / parcel addresses from ``bronze.bronze_addresses``.

Source: Esri FeatureServer / MapServer attribute harvest (returnGeometry=false)
of county assessor parcel data. Carries situs + owner + parcel attributes, not
geometry — so this API is keyed off identifiers (serial id, source_record_id,
parcel number) rather than lat/lng radius searches.

Used by the property-click drilldown: the frontend maps a parcel polygon (with
its source parcel number or record id) to the full address row here.

See: scripts/deployment/neon/migrations/074_create_bronze_addresses.sql
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from api.routes.stats_neon import get_db_pool

router = APIRouter(prefix="/addresses", tags=["addresses"])

# Per-request safety net: list endpoints are paged, but a runaway scan would be
# expensive on the bronze table (parcel harvests can run into millions of rows).
_MAX_LIST_LIMIT = 5_000


class AddressDetail(BaseModel):
    """One parcel/property record from ``bronze.bronze_addresses``."""

    id: int
    source_dataset: str
    source_record_id: str
    state_code: str
    county_fips: Optional[str] = None
    county_name: Optional[str] = None
    jurisdiction_id: Optional[str] = None

    owner_name: Optional[str] = None

    # Situs (where the property is) — both pieces and a pre-joined display string.
    situs_location: Optional[str] = None
    street_number: Optional[str] = None
    street_line1: Optional[str] = None
    street_line2: Optional[str] = None
    city: Optional[str] = None
    state_abbr: Optional[str] = None
    postal_code: Optional[str] = None
    situs_full: Optional[str] = None

    parcel_number: Optional[str] = None
    parcel_number_formatted: Optional[str] = None
    appraised_value: Optional[int] = None
    tax_class: Optional[str] = None

    data_source: str
    esri_endpoint: Optional[str] = None
    # `include_raw=true` is required to populate this — the JSONB blob can be
    # large (full Esri attribute dump) so we drop it by default.
    raw_attributes: Optional[Dict[str, Any]] = None
    loaded_at: Optional[str] = None


class AddressListResponse(BaseModel):
    state: Optional[str] = None
    county_fips: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    total: int = Field(..., description="Matching rows before LIMIT.")
    limit: int
    offset: int
    addresses: List[AddressDetail]


_SELECT_COLUMNS_NO_RAW = """
    id,
    source_dataset,
    source_record_id,
    state_code,
    county_fips,
    county_name,
    jurisdiction_id,
    owner_name,
    situs_location,
    street_number,
    street_line1,
    street_line2,
    city,
    state_abbr,
    postal_code,
    situs_full,
    parcel_number,
    parcel_number_formatted,
    appraised_value,
    tax_class,
    data_source,
    esri_endpoint,
    NULL::jsonb AS raw_attributes,
    loaded_at
"""

_SELECT_COLUMNS_WITH_RAW = _SELECT_COLUMNS_NO_RAW.replace(
    "NULL::jsonb AS raw_attributes", "raw_attributes"
)


def _row_to_address(row) -> AddressDetail:
    return AddressDetail(
        id=int(row["id"]),
        source_dataset=str(row["source_dataset"]),
        source_record_id=str(row["source_record_id"]),
        state_code=str(row["state_code"]),
        county_fips=row["county_fips"],
        county_name=row["county_name"],
        jurisdiction_id=row["jurisdiction_id"],
        owner_name=row["owner_name"],
        situs_location=row["situs_location"],
        street_number=row["street_number"],
        street_line1=row["street_line1"],
        street_line2=row["street_line2"],
        city=row["city"],
        state_abbr=row["state_abbr"],
        postal_code=row["postal_code"],
        situs_full=row["situs_full"],
        parcel_number=row["parcel_number"],
        parcel_number_formatted=row["parcel_number_formatted"],
        appraised_value=(int(row["appraised_value"]) if row["appraised_value"] is not None else None),
        tax_class=row["tax_class"],
        data_source=str(row["data_source"]),
        esri_endpoint=row["esri_endpoint"],
        raw_attributes=row["raw_attributes"],
        loaded_at=(row["loaded_at"].isoformat() if row["loaded_at"] is not None else None),
    )


async def _table_exists(conn) -> bool:
    row = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'bronze' AND table_name = 'bronze_addresses'
        )
        """
    )
    return bool(row)


async def _ensure_table(conn) -> None:
    """Raises 503 with a hint to run the migration if the table is missing."""
    if not await _table_exists(conn):
        raise HTTPException(
            status_code=503,
            detail=(
                "bronze.bronze_addresses not found. Apply migration: "
                "scripts/deployment/neon/migrations/074_create_bronze_addresses.sql"
            ),
        )


@router.get("/{address_id}", response_model=AddressDetail)
async def get_address_by_id(
    address_id: int,
    include_raw: bool = Query(
        False, description="Include the raw Esri attribute JSON blob in the response."
    ),
):
    """
    Look up a single property/parcel by its internal ``bronze_addresses.id``.

    This is the primary "property-click → details" endpoint. The frontend
    typically gets the id by clicking a parcel polygon whose attributes
    include the bronze id (or by resolving via ``/addresses/by-parcel`` when
    only a parcel number is available).
    """
    select_cols = _SELECT_COLUMNS_WITH_RAW if include_raw else _SELECT_COLUMNS_NO_RAW
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await _ensure_table(conn)
        row = await conn.fetchrow(
            f"""
            SELECT {select_cols}
            FROM bronze.bronze_addresses
            WHERE id = $1
            """,
            address_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Address id={address_id} not found.")
    return _row_to_address(row)


@router.get("/by-parcel/lookup", response_model=AddressDetail)
async def get_address_by_parcel(
    state: str = Query(..., min_length=2, max_length=2, description="USPS state code (e.g. AL)"),
    parcel: str = Query(..., min_length=1, description="parcel_number_formatted as it appears in bronze"),
    include_raw: bool = Query(False),
):
    """
    Resolve a parcel number to its address record.

    Uses the ``(state_code, parcel_number_formatted)`` index (see migration 074),
    so this is the fast path when the polygon click only has a parcel number,
    not the bronze internal id. State code is required because parcel numbers
    are not nationally unique.
    """
    select_cols = _SELECT_COLUMNS_WITH_RAW if include_raw else _SELECT_COLUMNS_NO_RAW
    state_upper = state.strip().upper()
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await _ensure_table(conn)
        row = await conn.fetchrow(
            f"""
            SELECT {select_cols}
            FROM bronze.bronze_addresses
            WHERE state_code = $1
              AND parcel_number_formatted = $2
            LIMIT 1
            """,
            state_upper,
            parcel,
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No address found for state={state_upper} parcel={parcel}",
        )
    return _row_to_address(row)


@router.get("/by-source/lookup", response_model=AddressDetail)
async def get_address_by_source(
    source_dataset: str = Query(..., description="The harvest source dataset key."),
    source_record_id: str = Query(..., description="The id within the source dataset."),
    include_raw: bool = Query(False),
):
    """
    Resolve a ``(source_dataset, source_record_id)`` pair. This is the
    canonical natural-key lookup (UNIQUE constraint on the table) and is
    the right path when the polygon click can carry the source attributes
    directly.
    """
    select_cols = _SELECT_COLUMNS_WITH_RAW if include_raw else _SELECT_COLUMNS_NO_RAW
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await _ensure_table(conn)
        row = await conn.fetchrow(
            f"""
            SELECT {select_cols}
            FROM bronze.bronze_addresses
            WHERE source_dataset = $1 AND source_record_id = $2
            """,
            source_dataset,
            source_record_id,
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No address found for source_dataset={source_dataset} record_id={source_record_id}",
        )
    return _row_to_address(row)


@router.get("/search", response_model=AddressListResponse)
async def search_addresses(
    q: str = Query(..., min_length=3, description="Free-text query (matched against situs_full / street_line1 / city)."),
    state: Optional[str] = Query(None, min_length=2, max_length=2, description="USPS state code."),
    limit: int = Query(20, ge=1, le=200),
):
    """
    Free-text address search — for the property-pin click flow.

    The bronze table has no geometry, so we can't resolve a lat/lng pin to
    a parcel row directly. Instead we ILIKE-match the situs/street string
    from the geocoder. Provide ``state`` whenever possible to constrain the
    scan and avoid cross-state false positives.

    Returns the same envelope as the listing endpoint so callers can reuse
    the rendering. Empty list (200) means "no parcel match" — distinct from
    a 503 (table missing) or 4xx (bad query).
    """
    state_upper = state.strip().upper() if state else None
    # Extract a likely-house-number prefix to tighten ILIKE matches (e.g.
    # "5617 Lakeridge..." → "5617"). Helps when the user pastes a full
    # display_name like "5617 Lakeridge Court, Tuscaloosa, AL 35406, USA".
    head = q.strip().split(",", 1)[0].strip()
    where_parts = [
        "(situs_full ILIKE $1 OR street_line1 ILIKE $1 OR street_number || ' ' || street_line1 ILIKE $1)",
    ]
    params: list = [f"%{head}%"]
    idx = 2
    if state_upper:
        where_parts.append(f"state_code = ${idx}")
        params.append(state_upper)
        idx += 1
    where_sql = " AND ".join(where_parts)

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await _ensure_table(conn)
        total = await conn.fetchval(
            f"SELECT COUNT(*)::bigint FROM bronze.bronze_addresses WHERE {where_sql}",
            *params,
        )
        rows = await conn.fetch(
            f"""
            SELECT {_SELECT_COLUMNS_NO_RAW}
            FROM bronze.bronze_addresses
            WHERE {where_sql}
            ORDER BY state_code, situs_full NULLS LAST, id
            LIMIT ${idx}
            """,
            *params,
            limit,
        )

    return AddressListResponse(
        state=state_upper,
        county_fips=None,
        jurisdiction_id=None,
        total=int(total or 0),
        limit=limit,
        offset=0,
        addresses=[_row_to_address(r) for r in rows],
    )


@router.get("", response_model=AddressListResponse)
async def list_addresses(
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    county_fips: Optional[str] = Query(
        None, min_length=3, max_length=5, description="3-digit county FIPS or 5-digit GEOID."
    ),
    jurisdiction_id: Optional[str] = Query(None),
    owner_q: Optional[str] = Query(
        None, description="Free-text owner_name search (uses the GIN tsvector index)."
    ),
    limit: int = Query(200, ge=1, le=_MAX_LIST_LIMIT),
    offset: int = Query(0, ge=0),
):
    """
    Paged list of parcels within a jurisdiction filter.

    At least one of ``state``, ``county_fips``, ``jurisdiction_id``, or
    ``owner_q`` must be provided — an unfiltered scan of the bronze table
    is rejected (it would table-scan millions of rows).

    Example::

        GET /api/addresses?state=AL&county_fips=01125&limit=200
        GET /api/addresses?state=AL&owner_q=university
    """
    if not (state or county_fips or jurisdiction_id or owner_q):
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: state, county_fips, jurisdiction_id, owner_q.",
        )

    where_parts: List[str] = []
    params: list = []
    idx = 1

    state_upper = state.strip().upper() if state else None
    if state_upper:
        where_parts.append(f"state_code = ${idx}")
        params.append(state_upper)
        idx += 1

    if county_fips:
        fips = county_fips.strip()
        # Accept either '125' (3-digit county part) or '01125' (5-digit GEOID).
        # Stored as county_fips VARCHAR(5), values vary by loader — match both.
        if len(fips) == 5:
            where_parts.append(f"county_fips = ${idx}")
            params.append(fips)
            idx += 1
        else:
            where_parts.append(f"(county_fips = ${idx} OR county_fips LIKE '%' || ${idx})")
            params.append(fips)
            idx += 1

    if jurisdiction_id:
        where_parts.append(f"jurisdiction_id = ${idx}")
        params.append(jurisdiction_id)
        idx += 1

    if owner_q:
        # Uses idx_bronze_addresses_owner GIN index from the migration.
        where_parts.append(
            f"to_tsvector('english', coalesce(owner_name, '')) @@ plainto_tsquery('english', ${idx})"
        )
        params.append(owner_q)
        idx += 1

    where_sql = " AND ".join(where_parts) if where_parts else "TRUE"

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await _ensure_table(conn)

        total = await conn.fetchval(
            f"SELECT COUNT(*)::bigint FROM bronze.bronze_addresses WHERE {where_sql}",
            *params,
        )

        limit_idx = idx
        offset_idx = idx + 1
        rows = await conn.fetch(
            f"""
            SELECT {_SELECT_COLUMNS_NO_RAW}
            FROM bronze.bronze_addresses
            WHERE {where_sql}
            ORDER BY state_code, county_fips NULLS LAST, situs_full NULLS LAST, id
            LIMIT ${limit_idx} OFFSET ${offset_idx}
            """,
            *params,
            limit,
            offset,
        )

    return AddressListResponse(
        state=state_upper,
        county_fips=county_fips,
        jurisdiction_id=jurisdiction_id,
        total=int(total or 0),
        limit=limit,
        offset=offset,
        addresses=[_row_to_address(r) for r in rows],
    )

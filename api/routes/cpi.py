"""CPI (Bureau of Labor Statistics) read endpoint for the frontend inflation toggle.

Reads ``public.cpi_annual`` (the civic serving mart over
``staging.stg_bls__cpi_annual`` -> ``bronze.bronze_bls_cpi``, loaded by
``ingestion.bls.cpi``) and returns a flat
``{year: index_value}`` map plus the latest year — exactly the shape the
frontend ``useInflationToggle`` / ``deflate()`` utility consumes to convert
nominal dollars to constant dollars of the latest year.

One national series is intentional: the same yardstick is applied to every
geography so cross-place "real dollar" comparisons stay comparable.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict

import psycopg2
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

router = APIRouter()

# DB URL priority mirrors api/database.py so prod resolves to Neon, not
# localhost: NEON_DATABASE_URL_DEV (local dev) -> NEON_DATABASE_URL (prod Neon)
# -> DATABASE_URL -> local fallback. The earlier dev-only single-var lookup fell
# through to localhost in prod, which (combined with CPI being absent from the
# Neon serving schema) was a source of the production 500s.
DB_URL = os.getenv(
    "NEON_DATABASE_URL_DEV",
    os.getenv(
        "NEON_DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:password@localhost:5433/open_navigator",
        ),
    ),
)

# CPI updates monthly; a 6-hour TTL is loose enough that the cost-per-request
# is negligible while still keeping any same-day reloads cheap.
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = timedelta(hours=6)


@router.get("/cpi/annual")
def cpi_annual(
    series_id: str = Query(
        "CUUR0000SA0",
        description=(
            "BLS series identifier. Default CUUR0000SA0 = CPI-U NSA, "
            "all items, U.S. city average — the standard deflator the "
            "frontend real-dollar toggle uses across every geography."
        ),
    ),
) -> Dict[str, Any]:
    cached = _CACHE.get(series_id)
    if cached and datetime.utcnow() - cached["fetched_at"] < _CACHE_TTL:
        return cached["payload"]

    try:
        conn = psycopg2.connect(DB_URL)
        try:
            cur = conn.cursor()
            # public.cpi_annual is the civic serving relation (mirrored to Neon
            # prod); the staging view is gold/dev-only and never reaches Neon.
            cur.execute(
                """
                SELECT year, index_value, from_official_annual
                FROM public.cpi_annual
                WHERE series_id = %s
                ORDER BY year
                """,
                (series_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    except psycopg2.Error as e:
        logger.exception("CPI query failed for series={}", series_id)
        raise HTTPException(status_code=500, detail=f"CPI query failed: {e}") from e

    by_year: Dict[str, float] = {}
    from_official: Dict[str, bool] = {}
    for year, index_value, official in rows:
        key = str(int(year))
        by_year[key] = float(index_value)
        from_official[key] = bool(official)

    latest_year = max((int(y) for y in by_year), default=None)
    payload = {
        "series_id": series_id,
        "latest_year": latest_year,
        "by_year": by_year,
        "from_official_annual": from_official,
    }
    _CACHE[series_id] = {"fetched_at": datetime.utcnow(), "payload": payload}
    return payload

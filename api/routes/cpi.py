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

import asyncio
import os
import re
import time
from typing import Any, Dict, Optional

import psycopg2
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

router = APIRouter()

_DEFAULT_LOCAL_DB_URL = "postgresql://postgres:password@localhost:5433/open_navigator"
_DB_ENV_PRIORITY = (
    "NEON_DATABASE_URL_DEV",
    "NEON_DATABASE_URL",
    "OPEN_NAVIGATOR_DATABASE_URL",
    "DATABASE_URL",
)
_SERIES_ID_PATTERN = r"^[A-Za-z0-9_-]{3,32}$"
_SERIES_ID_RE = re.compile(_SERIES_ID_PATTERN)


def resolve_db_url() -> str:
    """Resolve database URL across dev, Neon production, and standard env vars."""
    for env_key in _DB_ENV_PRIORITY:
        raw = (os.getenv(env_key) or "").strip()
        if raw:
            if raw.startswith("postgres://"):
                return raw.replace("postgres://", "postgresql://", 1)
            return raw
    return _DEFAULT_LOCAL_DB_URL


DB_URL = resolve_db_url()
_INITIAL_DB_URL = DB_URL

# CPI updates monthly; a 6-hour TTL keeps cost-per-request negligible while
# bounding cached entries and avoiding stale/empty cache pollution.
_CACHE_TTL_S: float = 6 * 3600.0
_MAX_CACHE_ENTRIES: int = 32
_CACHE: Dict[str, Dict[str, Any]] = {}
_inflight_locks: Dict[str, asyncio.Lock] = {}


def clear_cpi_cache() -> None:
    """Clear in-memory CPI cache and inflight locks."""
    _CACHE.clear()
    _inflight_locks.clear()


def _active_db_url() -> str:
    if DB_URL != _INITIAL_DB_URL:
        if DB_URL.startswith("postgres://"):
            return DB_URL.replace("postgres://", "postgresql://", 1)
        return DB_URL
    return resolve_db_url()


def _get_cached(series_id: str) -> Optional[Dict[str, Any]]:
    cached = _CACHE.get(series_id)
    if not cached:
        return None
    if time.monotonic() - cached["fetched_at"] >= _CACHE_TTL_S:
        _CACHE.pop(series_id, None)
        return None
    return cached["payload"]


def _set_cached(series_id: str, payload: Dict[str, Any]) -> None:
    now = time.monotonic()
    if len(_CACHE) >= _MAX_CACHE_ENTRIES and series_id not in _CACHE:
        expired = [k for k, v in _CACHE.items() if now - v["fetched_at"] >= _CACHE_TTL_S]
        for k in expired:
            _CACHE.pop(k, None)
        if len(_CACHE) >= _MAX_CACHE_ENTRIES:
            oldest_key = min(_CACHE, key=lambda k: _CACHE[k]["fetched_at"])
            _CACHE.pop(oldest_key, None)
    _CACHE[series_id] = {"fetched_at": now, "payload": payload}


def _fetch_cpi_series_sync(series_id: str) -> list[tuple[Any, Any, Any]]:
    conn = psycopg2.connect(_active_db_url())
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
        return cur.fetchall()
    finally:
        conn.close()


@router.get("/cpi/annual")
async def cpi_annual(
    series_id: str = Query(
        "CUUR0000SA0",
        pattern=_SERIES_ID_PATTERN,
        description=(
            "BLS series identifier. Default CUUR0000SA0 = CPI-U NSA, "
            "all items, U.S. city average — the standard deflator the "
            "frontend real-dollar toggle uses across every geography."
        ),
    ),
) -> Dict[str, Any]:
    clean_series_id = (series_id or "").strip().upper()
    if not _SERIES_ID_RE.match(clean_series_id):
        raise HTTPException(status_code=400, detail="Invalid BLS series_id format")

    cached = _get_cached(clean_series_id)
    if cached is not None:
        return cached

    lock = _inflight_locks.setdefault(clean_series_id, asyncio.Lock())
    try:
        async with lock:
            cached = _get_cached(clean_series_id)
            if cached is not None:
                return cached

            try:
                rows = await asyncio.to_thread(_fetch_cpi_series_sync, clean_series_id)
            except psycopg2.Error as e:
                logger.exception("CPI query failed for series={}", clean_series_id)
                raise HTTPException(status_code=500, detail="CPI query failed") from e

            by_year: Dict[str, float] = {}
            from_official: Dict[str, bool] = {}
            for year, index_value, official in rows:
                key = str(int(year))
                by_year[key] = float(index_value)
                from_official[key] = bool(official)

            latest_year = max((int(y) for y in by_year), default=None)
            payload = {
                "series_id": clean_series_id,
                "latest_year": latest_year,
                "by_year": by_year,
                "from_official_annual": from_official,
            }
            if by_year:
                _set_cached(clean_series_id, payload)
            return payload
    finally:
        if not lock.locked():
            _inflight_locks.pop(clean_series_id, None)

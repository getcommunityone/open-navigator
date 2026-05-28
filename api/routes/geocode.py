"""
Server-side proxy for OpenStreetMap Nominatim geocoding.

Why this exists: the SPA used to call ``nominatim.openstreetmap.org`` directly
from the browser. That fails in two ways:

  1. CORS — Nominatim does not reliably send ``Access-Control-Allow-Origin``,
     and the custom ``User-Agent`` the frontend tried to set is a *forbidden
     header* the browser silently drops, so requests arrive unidentified.
  2. Policy — Nominatim's usage policy caps clients at ~1 req/s and requires a
     real identifying User-Agent / contact. Per-keystroke browser calls trip
     the rate limiter, which then returns header-less error pages → the CORS
     error the user sees.

Proxying through the API fixes both: it's same-origin (no CORS), sets a proper
identifying User-Agent server-side, throttles to <=1 req/s globally, and caches
recent queries so autocomplete bursts collapse to a single upstream call.

Responses are passed through unchanged so the existing frontend parsing
(``lat``, ``lon``, ``display_name``, ``address``, ``osm_type``, ``osm_id``)
keeps working.

NOTE: for production scale, self-host Nominatim or use a paid geocoder — a
single shared 1 req/s budget is a courtesy limit, not a throughput guarantee.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

router = APIRouter(prefix="/geocode", tags=["geocode"])

_NOMINATIM_BASE = "https://nominatim.openstreetmap.org"

# Nominatim's policy requires an identifying User-Agent with contact info.
# Override via env in deploys (e.g. "OpenNavigator/1.0 (ops@example.org)").
_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "OpenNavigator/1.0 (https://github.com/getcommunityone/open-navigator)",
)

# Global throttle: never issue upstream calls faster than this.
_MIN_INTERVAL_S = 1.05
_throttle_lock = asyncio.Lock()
_last_call_ts = 0.0

# Tiny in-memory TTL cache. Autocomplete fires several near-identical queries;
# caching collapses them and shields Nominatim. Keyed by the full request path.
_CACHE_TTL_S = 300.0
_CACHE_MAX = 512
_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Optional[Any]:
    hit = _cache.get(key)
    if not hit:
        return None
    ts, payload = hit
    if time.monotonic() - ts > _CACHE_TTL_S:
        _cache.pop(key, None)
        return None
    return payload


def _cache_put(key: str, payload: Any) -> None:
    if len(_cache) >= _CACHE_MAX:
        # Cheap eviction: drop the oldest entry.
        oldest = min(_cache.items(), key=lambda kv: kv[1][0])[0]
        _cache.pop(oldest, None)
    _cache[key] = (time.monotonic(), payload)


async def _throttled_get(path: str, params: dict[str, str]) -> Any:
    """GET ``{base}{path}`` through the global throttle, with caching + UA."""
    cache_key = f"{path}?{httpx.QueryParams(params)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    global _last_call_ts
    async with _throttle_lock:
        wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_NOMINATIM_BASE}{path}",
                    params=params,
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "application/json",
                    },
                )
        finally:
            _last_call_ts = time.monotonic()

    if resp.status_code == 429:
        raise HTTPException(status_code=429, detail="Geocoder rate-limited; retry shortly.")
    if resp.status_code >= 400:
        logger.warning("Nominatim {} for {}: {}", resp.status_code, path, resp.text[:200])
        raise HTTPException(status_code=502, detail=f"Geocoder error ({resp.status_code}).")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Geocoder returned non-JSON.") from exc

    _cache_put(cache_key, payload)
    return payload


@router.get("/search")
async def geocode_search(
    q: str = Query(..., min_length=3, description="Free-text address / place query."),
    limit: int = Query(6, ge=1, le=20),
    countrycodes: str = Query("us", description="Comma-separated ISO country codes to bias to."),
):
    """
    Forward-geocode a free-text query. Returns Nominatim's JSON array verbatim
    (each item has ``lat``, ``lon``, ``display_name``, ``address``,
    ``osm_type``, ``osm_id`` …). Empty array means no match.
    """
    return await _throttled_get(
        "/search",
        {
            "q": q.strip(),
            "format": "json",
            "addressdetails": "1",
            "countrycodes": countrycodes,
            "limit": str(limit),
        },
    )


@router.get("/reverse")
async def geocode_reverse(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Reverse-geocode a lat/lng to its nearest address (Nominatim JSON object)."""
    return await _throttled_get(
        "/reverse",
        {
            "lat": str(lat),
            "lon": str(lon),
            "format": "json",
            "addressdetails": "1",
        },
    )

#!/usr/bin/env python3
"""Free, idempotent nationwide geocoding backfill for ``public.event_place``.

Reads DISTINCT geocode targets from ``public.event_place`` (pending/null status,
excluding ``place_type='jurisdiction_wide'``) and resolves lat/lon with two FREE,
key-less geocoders, writing the results into the additive cache table
``bronze.place_geocode_cache`` (never mutating ``event_place`` itself):

* ``place_type='street_address'`` -> US Census Bureau batch geocoder
  (:class:`ingestion.geocode.census_batch.CensusBatchGeocoder`), batched.
* everything else -> OpenStreetMap Nominatim (reused from
  ``llm.gemini.enrich_analysis_places._nominatim_geocode``) at 1.1 s/req.

Idempotent / resumable: targets already present in the cache are skipped, so a
re-run only processes the remainder.

Usage:
    python -m ingestion.geocode.backfill_places                 # full nationwide run
    python -m ingestion.geocode.backfill_places --source census --limit 500
    python -m ingestion.geocode.backfill_places --source nominatim --limit 20
    python -m ingestion.geocode.backfill_places --state AL
    python -m ingestion.geocode.backfill_places --prioritize-decisions

Configuration:
    NEON_DATABASE_URL_DEV / OPEN_NAVIGATOR_DATABASE_URL / DATABASE_URL via
    core_lib.db (resolves to the dev warehouse at localhost:5433/open_navigator).
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from llm.gemini.enrich_analysis_places import _nominatim_geocode

from .census_batch import CensusAddress, CensusBatchGeocoder

NOMINATIM_DELAY_S = 1.1
CENSUS_BATCH_SIZE = 5_000
PROGRESS_EVERY = 100


# ---------------------------------------------------------------------------
# Geocode target (one DISTINCT query pulled from event_place).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeocodeTarget:
    geocode_key: str
    query_text: str
    place_type: str
    street_address: str | None
    city: str | None
    state_code: str | None


def normalize_key(query: str) -> str:
    """Canonical cache key: collapsed-whitespace, lowercased query text."""
    return " ".join((query or "").split()).lower()


# ---------------------------------------------------------------------------
# Cache table DDL + upsert.
# ---------------------------------------------------------------------------

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.place_geocode_cache (
        geocode_key    TEXT PRIMARY KEY,
        query_text     TEXT,
        latitude       DOUBLE PRECISION,
        longitude      DOUBLE PRECISION,
        geocode_status TEXT,
        geocode_source TEXT,
        geocoded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """
)

_CREATE_STATUS_IDX_SQL = text(
    """
    CREATE INDEX IF NOT EXISTS idx_place_geocode_cache_status
        ON bronze.place_geocode_cache (geocode_status)
    """
)

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.place_geocode_cache (
        geocode_key, query_text, latitude, longitude,
        geocode_status, geocode_source, geocoded_at
    ) VALUES (
        :geocode_key, :query_text, :latitude, :longitude,
        :geocode_status, :geocode_source, NOW()
    )
    ON CONFLICT (geocode_key) DO UPDATE SET
        query_text     = EXCLUDED.query_text,
        latitude       = EXCLUDED.latitude,
        longitude      = EXCLUDED.longitude,
        geocode_status = EXCLUDED.geocode_status,
        geocode_source = EXCLUDED.geocode_source,
        geocoded_at    = NOW()
    """
)


# DISTINCT pending targets. ``place_type='street_address'`` is mapped to the
# census lane; everything else (and jurisdiction_wide is excluded entirely) to
# the nominatim lane. DISTINCT ON keeps one row per normalized query.
_SELECT_TARGETS_SQL = """
    SELECT DISTINCT ON (lower(coalesce(normalized_address, geocode_query, raw_text)))
        lower(coalesce(normalized_address, geocode_query, raw_text)) AS raw_key,
        coalesce(normalized_address, geocode_query, raw_text)        AS query_text,
        place_type,
        street_address,
        coalesce(place_city, city)              AS city,
        coalesce(place_state_code, state_code)  AS state_code
    FROM public.event_place ep
    WHERE (ep.geocode_status = 'pending' OR ep.geocode_status IS NULL)
      AND ep.place_type <> 'jurisdiction_wide'
      AND coalesce(normalized_address, geocode_query, raw_text) IS NOT NULL
      AND length(trim(coalesce(normalized_address, geocode_query, raw_text))) > 0
      {state_filter}
      {place_type_filter}
      AND NOT EXISTS (
          SELECT 1 FROM bronze.place_geocode_cache c
          WHERE c.geocode_key = lower(coalesce(ep.normalized_address, ep.geocode_query, ep.raw_text))
      )
    ORDER BY lower(coalesce(normalized_address, geocode_query, raw_text))
    {limit_clause}
"""


async def prepare_cache_table() -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        await session.execute(_CREATE_STATUS_IDX_SQL)
    logger.success("Ensured bronze.place_geocode_cache exists")


async def fetch_targets(
    session: AsyncSession,
    *,
    source: str,
    state: str | None,
    limit: int | None,
) -> list[GeocodeTarget]:
    """Pull DISTINCT, not-yet-cached geocode targets for the requested lane."""
    if source == "census":
        place_filter = "AND ep.place_type = 'street_address'"
    elif source == "nominatim":
        place_filter = "AND ep.place_type <> 'street_address'"
    else:  # all
        place_filter = ""

    params: dict[str, object] = {}
    state_filter = ""
    if state:
        state_filter = (
            "AND upper(coalesce(place_state_code, state_code)) = :state"
        )
        params["state"] = state.upper()

    limit_clause = ""
    if limit:
        limit_clause = "LIMIT :limit"
        params["limit"] = limit

    sql = _SELECT_TARGETS_SQL.format(
        state_filter=state_filter,
        place_type_filter=place_filter,
        limit_clause=limit_clause,
    )
    result = await session.execute(text(sql), params)
    targets: list[GeocodeTarget] = []
    for row in result.mappings():
        targets.append(
            GeocodeTarget(
                geocode_key=normalize_key(row["query_text"]),
                query_text=row["query_text"],
                place_type=row["place_type"] or "",
                street_address=row["street_address"],
                city=row["city"],
                state_code=row["state_code"],
            )
        )
    return targets


def _split_lanes(
    targets: list[GeocodeTarget],
) -> tuple[list[GeocodeTarget], list[GeocodeTarget]]:
    census = [t for t in targets if t.place_type == "street_address"]
    nominatim = [t for t in targets if t.place_type != "street_address"]
    return census, nominatim


# ---------------------------------------------------------------------------
# Census lane.
# ---------------------------------------------------------------------------


async def _upsert_results(
    session: AsyncSession, params: list[dict[str, object]]
) -> None:
    if params:
        await session.execute(_UPSERT_SQL, params)


async def run_census(
    targets: list[GeocodeTarget],
    *,
    batch_size: int = CENSUS_BATCH_SIZE,
) -> tuple[int, int]:
    """Geocode street-address targets via the Census batch endpoint.

    Returns ``(ok_count, processed_count)``.
    """
    geocoder = CensusBatchGeocoder()
    ok = 0
    processed = 0
    by_key = {t.geocode_key: t for t in targets}

    for start in range(0, len(targets), batch_size):
        chunk = targets[start : start + batch_size]
        addresses = [
            CensusAddress(
                record_id=t.geocode_key,
                # Prefer the dedicated street_address column; fall back to the
                # full query so the Census parser still gets something usable.
                street=(t.street_address or t.query_text or "").strip()[:100],
                city=(t.city or "").strip()[:50],
                state=(t.state_code or "").strip()[:2],
            )
            for t in chunk
        ]
        try:
            results = geocoder.geocode_batch(addresses)
        except Exception as exc:  # transport/network error — do NOT cache
            # A whole-batch failure is transient (DNS, timeout, 5xx). Caching
            # these as not_found would permanently skip them on resume. Leave
            # them uncached so the next run retries.
            logger.warning(
                "Census batch {}-{} transport error, leaving uncached for retry: {}",
                start,
                start + len(chunk),
                exc,
            )
            processed += len(chunk)
            continue

        params: list[dict[str, object]] = []
        seen: set[str] = set()
        for res in results:
            target = by_key.get(res.record_id)
            if target is None:
                continue
            seen.add(res.record_id)
            if res.matched and res.latitude is not None:
                ok += 1
                params.append(
                    {
                        "geocode_key": target.geocode_key,
                        "query_text": target.query_text,
                        "latitude": res.latitude,
                        "longitude": res.longitude,
                        "geocode_status": "ok",
                        "geocode_source": "census",
                    }
                )
            else:
                params.append(
                    {
                        "geocode_key": target.geocode_key,
                        "query_text": target.query_text,
                        "latitude": None,
                        "longitude": None,
                        "geocode_status": "not_found",
                        "geocode_source": "census",
                    }
                )
        # Any input the service silently dropped -> record as not_found so the
        # run stays idempotent (we never retry it endlessly).
        for target in chunk:
            if target.geocode_key not in seen:
                params.append(
                    {
                        "geocode_key": target.geocode_key,
                        "query_text": target.query_text,
                        "latitude": None,
                        "longitude": None,
                        "geocode_status": "not_found",
                        "geocode_source": "census",
                    }
                )

        async with async_session() as session:
            await _upsert_results(session, params)
        processed += len(chunk)
        logger.info(
            "Census progress: {}/{} processed, {} matched",
            processed,
            len(targets),
            ok,
        )
    return ok, processed


# ---------------------------------------------------------------------------
# Nominatim lane.
# ---------------------------------------------------------------------------


async def run_nominatim(
    targets: list[GeocodeTarget],
    *,
    delay_s: float = NOMINATIM_DELAY_S,
    progress_every: int = PROGRESS_EVERY,
) -> tuple[int, int]:
    """Geocode non-street-address targets via Nominatim at ``delay_s``/req.

    Returns ``(ok_count, processed_count)``.
    """
    ok = 0
    processed = 0
    pending: list[dict[str, object]] = []

    async def _flush() -> None:
        if pending:
            async with async_session() as session:
                await _upsert_results(session, list(pending))
            pending.clear()

    for target in targets:
        transient = False
        try:
            geo = _nominatim_geocode(
                target.query_text,
                city=target.city or "",
                state=target.state_code or "",
                country="us",
            )
        except Exception as exc:  # transport/network error — do NOT cache
            logger.warning("Nominatim error for {!r}: {}", target.query_text, exc)
            geo = None
            transient = True
        time.sleep(delay_s)

        if transient:
            # Leave uncached so the next run retries; only genuine no-match
            # (geo is None without an exception) is recorded as not_found.
            processed += 1
            if processed % progress_every == 0:
                await _flush()
            continue

        if geo and geo.get("latitude") is not None:
            ok += 1
            pending.append(
                {
                    "geocode_key": target.geocode_key,
                    "query_text": target.query_text,
                    "latitude": geo["latitude"],
                    "longitude": geo["longitude"],
                    "geocode_status": "ok",
                    "geocode_source": "nominatim",
                }
            )
        else:
            pending.append(
                {
                    "geocode_key": target.geocode_key,
                    "query_text": target.query_text,
                    "latitude": None,
                    "longitude": None,
                    "geocode_status": "not_found",
                    "geocode_source": "nominatim",
                }
            )
        processed += 1
        if processed % progress_every == 0:
            await _flush()
            logger.info(
                "Nominatim progress: {}/{} processed, {} matched",
                processed,
                len(targets),
                ok,
            )
    await _flush()
    return ok, processed


# ---------------------------------------------------------------------------
# Decision prioritization (stub — see note).
# ---------------------------------------------------------------------------


def prioritize_decisions(targets: list[GeocodeTarget]) -> list[GeocodeTarget]:
    """Reorder so decision-referenced places geocode first.

    NO-OP STUB: the decision -> event_place linkage (``linked_decision_ids`` /
    a decisions place_id set) is owned by a separate agent and is not cheaply
    joinable yet. Returns the input order unchanged; wire in once the link
    table exists.
    """
    logger.info("--prioritize-decisions is a no-op stub (linkage not yet joinable)")
    return targets


# ---------------------------------------------------------------------------
# Orchestration / CLI.
# ---------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> None:
    await prepare_cache_table()

    async with async_session() as session:
        targets = await fetch_targets(
            session, source=args.source, state=args.state, limit=args.limit
        )
    logger.info("Fetched {} not-yet-cached geocode targets", len(targets))
    if args.prioritize_decisions:
        targets = prioritize_decisions(targets)

    census_targets, nominatim_targets = _split_lanes(targets)

    census_ok = nominatim_ok = 0
    if args.source in ("all", "census") and census_targets:
        logger.info("Census lane: {} street-address targets", len(census_targets))
        census_ok, _ = await run_census(census_targets)
        logger.success("Census lane done: {} geocoded ok", census_ok)
    if args.source in ("all", "nominatim") and nominatim_targets:
        logger.info(
            "Nominatim lane: {} targets (~{:.1f} min at {}s/req)",
            len(nominatim_targets),
            len(nominatim_targets) * NOMINATIM_DELAY_S / 60.0,
            NOMINATIM_DELAY_S,
        )
        nominatim_ok, _ = await run_nominatim(nominatim_targets)
        logger.success("Nominatim lane done: {} geocoded ok", nominatim_ok)

    logger.success(
        "Backfill complete: census ok={}, nominatim ok={}",
        census_ok,
        nominatim_ok,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Free idempotent geocoding backfill into bronze.place_geocode_cache"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Cap targets (smoke runs)"
    )
    parser.add_argument(
        "--source",
        choices=["all", "census", "nominatim"],
        default="all",
        help="Which geocoder lane(s) to run",
    )
    parser.add_argument("--state", default=None, help="2-letter state filter (e.g. AL)")
    parser.add_argument(
        "--prioritize-decisions",
        action="store_true",
        help="Order decision-referenced places first (currently a no-op stub)",
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

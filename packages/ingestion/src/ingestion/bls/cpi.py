#!/usr/bin/env python3
"""BLS Consumer Price Index pipeline: land BLS CPI series into bronze.bronze_bls_cpi.

Default series is **CUUR0000SA0** — CPI-U, Not Seasonally Adjusted, All Items,
U.S. City Average. This is the inflation deflator the frontend real-dollar
toggle uses. One national series is intentionally applied uniformly to every
geography: deflating each place by a regional CPI would bake local inflation
into the yardstick and break cross-place "real dollar" comparisons. (No
state/county/ZIP CPI exists at BLS anyway.)

Pipeline shape: ``data/cache/bls/{series_id}__{start}-{end}.json`` holds the
raw BLS API response (FETCH); ``extract()`` melts each (year, period) reading
into one ``BlsCpiRow`` (LAND). Re-runs hit the cache; ``--refresh`` forces a
re-fetch, and the trailing (current-year) cache window is always re-fetched
because BLS publishes the annual-average row (``period='M13'``) only after the
December monthly drops, so a mid-year cache would otherwise lie about being
"complete".

Source: BLS Public Data API v2 — https://api.bls.gov/publicAPI/v2/timeseries/data/

Usage:
    python -m ingestion.bls.cpi                          # 20-year window, fetch + load
    python -m ingestion.bls.cpi --truncate
    python -m ingestion.bls.cpi --no-fetch               # use cache only (offline / replay)
    python -m ingestion.bls.cpi --refresh                # force re-fetch even if cached
    python -m ingestion.bls.cpi --series CUUR0000SA0 --start-year 2000 --end-year 2024

Configuration:
    BLS_API_KEY              — registered key (500 req/day vs 25 unregistered)
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import httpx
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/bls")
DEFAULT_SERIES = "CUUR0000SA0"
BLS_ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# BLS API v2 caps a single request at 20 years of data; chunk longer windows.
MAX_YEARS_PER_REQUEST = 20


def cache_path_for(series_id: str, start_year: int, end_year: int, *, cache_dir: Path = CACHE_DIR) -> Path:
    """Deterministic cache filename for one ``(series_id, start, end)`` window.

    Per-window filenames let re-runs over the same range hit the cache while
    new ranges fetch independently — no global "latest" file to invalidate.
    """
    return cache_dir / f"{series_id}__{start_year}-{end_year}.json"


def _build_request_payload(
    series_id: str, start_year: int, end_year: int, registration_key: str | None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "seriesid": [series_id],
        "startyear": str(start_year),
        "endyear": str(end_year),
        # Annual averages (period='M13') are returned alongside monthly rows;
        # the staging view prefers M13 and falls back to a >=6-month mean.
        "annualaverage": True,
    }
    if registration_key:
        payload["registrationkey"] = registration_key
    return payload


def _window_must_refetch(end_year: int, today: dt.date | None = None) -> bool:
    """Trailing windows that include the current calendar year are never
    "complete" — BLS publishes the annual average only after December — so
    the cache for those windows is treated as stale."""
    now = today or dt.date.today()
    return end_year >= now.year


async def fetch_window(
    client: httpx.AsyncClient,
    series_id: str,
    start_year: int,
    end_year: int,
    registration_key: str | None,
    *,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> Path:
    """Fetch one 20-year-or-shorter window into the cache, return the cache path.

    Skips the HTTP call when a non-stale cache file already exists. Raises
    ``RuntimeError`` if the BLS response status is not ``REQUEST_SUCCEEDED``.
    """
    path = cache_path_for(series_id, start_year, end_year, cache_dir=cache_dir)
    must_refetch = refresh or _window_must_refetch(end_year)
    if path.exists() and not must_refetch:
        logger.info(
            "BLS cache hit: series={} window={}-{} -> {}",
            series_id, start_year, end_year, path,
        )
        return path

    payload = _build_request_payload(series_id, start_year, end_year, registration_key)
    logger.info(
        "BLS fetch: series={} window={}-{} (cache={}, refresh={})",
        series_id, start_year, end_year, path.exists(), refresh,
    )
    r = await client.post(BLS_ENDPOINT, json=payload, timeout=60)
    r.raise_for_status()
    body = r.json()
    status = body.get("status")
    if status != "REQUEST_SUCCEEDED":
        messages = body.get("message", [])
        raise RuntimeError(
            f"BLS request failed: status={status}, messages={messages}"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, sort_keys=True))
    return path


def chunk_windows(start_year: int, end_year: int, *, max_span: int = MAX_YEARS_PER_REQUEST) -> list[tuple[int, int]]:
    """Split ``[start, end]`` into windows of at most ``max_span`` years."""
    out: list[tuple[int, int]] = []
    cur = start_year
    while cur <= end_year:
        wend = min(cur + max_span - 1, end_year)
        out.append((cur, wend))
        cur = wend + 1
    return out


def melt_bls_response(body: dict[str, Any], *, source_version: str) -> Iterable[dict[str, Any]]:
    """Convert one cached BLS response into per-(year, period) raw row dicts."""
    for entry in body.get("Results", {}).get("series", []):
        sid = entry.get("seriesID") or ""
        if not sid:
            continue
        for d in entry.get("data", []) or []:
            try:
                value = float(d["value"])
            except (TypeError, ValueError, KeyError):
                logger.warning("Skipping unparsable BLS row: {}", d)
                continue
            year = int(d["year"])
            period = str(d["period"])
            footnotes = "; ".join(
                (f.get("text") or "")
                for f in (d.get("footnotes") or [])
                if f and f.get("text")
            ) or None
            yield {
                "source": "bls_cpi",
                "source_version": source_version,
                "natural_key": f"{sid}:{year}:{period}",
                "series_id": sid,
                "year": year,
                "period": period,
                "period_name": d.get("periodName"),
                "value": value,
                "footnotes": footnotes,
            }


class BlsCpiRow(RawRow):
    """One CPI observation (monthly or annual-average), validated before upsert."""

    series_id: str = Field(min_length=1, max_length=32)
    year: int
    period: str = Field(min_length=1, max_length=8)
    period_name: str | None = Field(default=None, max_length=32)
    value: float
    footnotes: str | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

# Idempotent: matches the shape applied by migration 077. Re-running this is
# a no-op against a DB that already has the table from the migration.
_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_bls_cpi (
        series_id    VARCHAR(32)   NOT NULL,
        year         INTEGER       NOT NULL,
        period       VARCHAR(8)    NOT NULL,
        period_name  TEXT,
        value        NUMERIC(10,3) NOT NULL,
        footnotes    TEXT,
        loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        last_updated TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        PRIMARY KEY (series_id, year, period)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bronze_bls_cpi_series_year "
        "ON bronze.bronze_bls_cpi (series_id, year)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_bls_cpi")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_bls_cpi
        (series_id, year, period, period_name, value, footnotes, loaded_at, last_updated)
    VALUES
        (:series_id, :year, :period, :period_name, :value, :footnotes, NOW(), NOW())
    ON CONFLICT (series_id, year, period) DO UPDATE SET
        period_name  = EXCLUDED.period_name,
        value        = EXCLUDED.value,
        footnotes    = EXCLUDED.footnotes,
        last_updated = NOW()
    """
)


class BlsCpiPipeline(DataSourcePipeline[BlsCpiRow]):
    source = "bls_cpi"
    batch_size = 500
    row_schema = BlsCpiRow

    def __init__(
        self,
        *,
        series_id: str = DEFAULT_SERIES,
        start_year: int | None = None,
        end_year: int | None = None,
        registration_key: str | None = None,
        cache_dir: Path = CACHE_DIR,
        allow_fetch: bool = True,
        refresh: bool = False,
        limit: int | None = None,
    ):
        today = dt.date.today()
        self._series_id = series_id
        self._start_year = start_year if start_year is not None else today.year - 20
        self._end_year = end_year if end_year is not None else today.year
        self._registration_key = registration_key
        self._cache_dir = cache_dir
        self._allow_fetch = allow_fetch
        self._refresh = refresh
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        windows = chunk_windows(self._start_year, self._end_year)
        paths: list[Path] = []

        if self._allow_fetch:
            async with httpx.AsyncClient() as client:
                for (ws, we) in windows:
                    paths.append(
                        await fetch_window(
                            client,
                            self._series_id,
                            ws,
                            we,
                            self._registration_key,
                            cache_dir=self._cache_dir,
                            refresh=self._refresh,
                        )
                    )
        else:
            # --no-fetch: replay strictly from cache. Missing windows are an error.
            for (ws, we) in windows:
                p = cache_path_for(self._series_id, ws, we, cache_dir=self._cache_dir)
                if not p.exists():
                    raise FileNotFoundError(
                        f"--no-fetch set but cache missing for window {ws}-{we}: {p}"
                    )
                paths.append(p)

        emitted = 0
        for path in paths:
            body = json.loads(path.read_text())
            for row in melt_bls_response(body, source_version=path.stem):
                if self._limit is not None and emitted >= self._limit:
                    return
                # Drop rows that don't match the requested series (defensive —
                # cached files are per-series so this is a no-op in practice).
                if row["series_id"] != self._series_id:
                    continue
                yield row
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[BlsCpiRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "series_id": r.series_id,
                "year": r.year,
                "period": r.period,
                "period_name": r.period_name,
                "value": r.value,
                "footnotes": r.footnotes,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load BLS CPI series into bronze.bronze_bls_cpi"
    )
    parser.add_argument(
        "--series",
        default=DEFAULT_SERIES,
        help="BLS series id (default: %(default)s — CPI-U NSA all items U.S. city avg)",
    )
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument(
        "--registration-key",
        default=None,
        help="BLS API key. Defaults to env BLS_API_KEY.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Use cache only; raise if a window is not cached.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-fetch even when a cache file exists.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads).",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing).")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = BlsCpiPipeline(
        series_id=args.series,
        start_year=args.start_year,
        end_year=args.end_year,
        registration_key=(args.registration_key or os.getenv("BLS_API_KEY") or None),
        allow_fetch=not args.no_fetch,
        refresh=args.refresh,
        limit=args.limit,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

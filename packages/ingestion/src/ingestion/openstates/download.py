"""OpenStates / Plural Policy bulk legislative data downloader.

Instead of thousands of API calls, fetch complete legislative sessions in bulk
from https://data.openstates.org/ (CSV / JSON / monthly PostgreSQL dumps).

Ported from scripts/datasources/openstates/load_openstates_bulk.py to
core_lib.http.BaseAsyncClient. This module is download-only: the load step lives
in ingestion.openstates.people. Follows the ingestion.gsa.download reference
pattern (BaseAsyncClient subclass + per-file cache-freshness reuse into CACHE_DIR).

Data available:
- CSV:  bills & votes per session (/session/csv/{state}/{session_id}.csv)
- JSON: bills with full text       (/session/json/{state}/{session_id}.json.zip)
- PostgreSQL: monthly database dump (/postgres/schema/, /postgres/monthly/)

Usage:
    python -m ingestion.openstates.download --year 2024 --format csv
    python -m ingestion.openstates.download --states AL,CA,TX --format json
    python -m ingestion.openstates.download --postgres --month 2026-04
    python -m ingestion.openstates.download --force
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import httpx
from loguru import logger

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging


CACHE_DIR = Path("data/cache/openstates")
_BASE_URL = "https://data.openstates.org"
_MAX_CACHE_AGE_S = 86_400  # reuse a cache file younger than 24h

# All state codes (plus DC and Puerto Rico).
STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR",
]


class OpenstatesBulkClient(BaseAsyncClient):
    """BaseAsyncClient subclass for the data.openstates.org bulk host."""

    def __init__(self) -> None:
        super().__init__(
            HttpClientConfig(
                base_url=_BASE_URL,
                source="openstates_bulk",
                timeout_s=120.0,
                # Many session files are fetched in sequence; throttle politely.
                rate_limit_per_sec=2.0,
            )
        )


# --- pure helpers (preserved from the original) ---------------------------


def _session_id(state: str, year: int) -> str:
    """Default session identifier: e.g. ('CA', 2024) -> 'ca-2024'."""
    return f"{state.lower()}-{year}"


def _csv_path(state: str, session_id: str) -> str:
    """Relative CSV path: /session/csv/{state}/{session_id}.csv."""
    return f"/session/csv/{state.lower()}/{session_id}.csv"


def _json_path(state: str, session_id: str) -> str:
    """Relative JSON path: /session/json/{state}/{session_id}.json.zip."""
    return f"/session/json/{state.lower()}/{session_id}.json.zip"


def _postgres_schema_path(month: str) -> str:
    return f"/postgres/schema/{month}-schema.pgdump"


def _postgres_data_path(month: str) -> str:
    return f"/postgres/monthly/{month}-public.pgdump"


def _enumerate_sessions(states: list[str], years: list[int]) -> list[tuple[str, int]]:
    """Cartesian product of (state, year) for the requested sessions."""
    return [(state.upper(), year) for state in states for year in years]


def _is_fresh(path: Path) -> bool:
    return path.exists() and (datetime.now().timestamp() - path.stat().st_mtime) < _MAX_CACHE_AGE_S


# --- download --------------------------------------------------------------


async def _fetch_one(
    client: OpenstatesBulkClient,
    *,
    url_path: str,
    out: Path,
    force: bool,
    bound,
) -> Path | None:
    """Fetch a single session file into ``out`` with cache-freshness reuse."""
    if not force and _is_fresh(out):
        bound.info(f"cache_hit {out}")
        return out
    try:
        resp = await client.get(url_path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            bound.warning(f"session not found: {url_path}")
            return None
        bound.error(f"error downloading {url_path}: {exc}")
        return None
    out.write_bytes(resp.content)
    bound.info(f"downloaded {len(resp.content)} bytes -> {out}")
    return out


async def download(
    *,
    force: bool = False,
    states: list[str] | None = None,
    years: list[int] | None = None,
    fmt: str = "csv",
    **params,
) -> list[Path]:
    """Fetch session bulk files into the OpenStates cache.

    Args:
        force: re-download even when a <24h cache file exists.
        states: state codes to fetch (default: all STATES).
        years: session years to fetch (default: the current year).
        fmt: ``"csv"`` or ``"json"`` session files.

    Returns:
        List of paths to files present in the cache (downloaded or reused).
    """
    states = states or STATES
    years = years or [datetime.now().year]
    fmt = fmt.lower()
    bound = logger.bind(source="openstates_bulk")

    sub_dir = CACHE_DIR / fmt
    sub_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    async with OpenstatesBulkClient() as client:
        for state, year in _enumerate_sessions(states, years):
            session_id = _session_id(state, year)
            if fmt == "csv":
                url_path = _csv_path(state, session_id)
                out = sub_dir / f"{session_id}.csv"
            elif fmt == "json":
                url_path = _json_path(state, session_id)
                out = sub_dir / f"{session_id}.json.zip"
            else:
                bound.error(f"unknown format: {fmt}")
                break
            path = await _fetch_one(
                client, url_path=url_path, out=out, force=force, bound=bound
            )
            if path is not None:
                written.append(path)

    bound.info(f"downloaded/reused {len(written)} session files -> {sub_dir}")
    return written


async def download_postgres(
    *,
    month: str | None = None,
    force: bool = False,
) -> list[Path]:
    """Fetch the monthly PostgreSQL schema + data dump into the cache.

    Args:
        month: ``YYYY-MM`` snapshot (default: current month).
        force: re-download even when a <24h cache file exists.

    Returns:
        Paths to the cached dump files (schema, data) that succeeded.
    """
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    bound = logger.bind(source="openstates_bulk")

    pg_dir = CACHE_DIR / "postgres"
    pg_dir.mkdir(parents=True, exist_ok=True)

    targets = [
        (_postgres_schema_path(month), pg_dir / f"{month}-schema.pgdump"),
        (_postgres_data_path(month), pg_dir / f"{month}-public.pgdump"),
    ]

    written: list[Path] = []
    async with OpenstatesBulkClient() as client:
        for url_path, out in targets:
            path = await _fetch_one(
                client, url_path=url_path, out=out, force=force, bound=bound
            )
            if path is not None:
                written.append(path)

    bound.info(f"downloaded/reused {len(written)} postgres dump files -> {pg_dir}")
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download bulk legislative data from OpenStates into data/cache/openstates/"
    )
    parser.add_argument("--year", type=int, action="append", help="Session year(s) to download (repeatable)")
    parser.add_argument(
        "--states",
        help="Comma-separated state codes (e.g. 'AL,CA,TX'). Default: all states",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Session download format (csv or json)",
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Download the monthly PostgreSQL database dump instead",
    )
    parser.add_argument("--month", help="Month for the PostgreSQL dump (YYYY-MM)")
    parser.add_argument("--force", action="store_true", help="Re-download even if a fresh cache exists")
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()

    if args.postgres:
        paths = asyncio.run(download_postgres(month=args.month, force=args.force))
    else:
        states = args.states.split(",") if args.states else None
        years = args.year if args.year else None
        paths = asyncio.run(
            download(force=args.force, states=states, years=years, fmt=args.format)
        )

    logger.info(f"cache files: {len(paths)}")


if __name__ == "__main__":
    main()

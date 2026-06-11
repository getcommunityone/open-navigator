"""
Census ACS property-tax ingestion.

Collects two ACS 5-year variables at **place** and **county** grain and lands
them *wide* into ``bronze.bronze_acs_property_tax``:

    B25103_001E  Median real estate taxes paid (dollars)
    B25077_001E  Median home value (dollars)

The downstream **effective property-tax rate** (taxes ÷ value) is computed in
dbt (``marts/jurisdiction_property_tax_rate``), not here -- per repo rule, all
transformation / ratio logic lives in dbt, ingestion only lands raw values.

This is a focused companion to ``ingestion.census.acs`` (which melts every
cached ACS table into an EAV bronze table). Here we issue exactly the two-column
request the feature needs, e.g.:

    https://api.census.gov/data/2023/acs/acs5
        ?get=NAME,B25103_001E,B25077_001E&for=county:*&in=state:01
    https://api.census.gov/data/2023/acs/acs5
        ?get=NAME,B25103_001E,B25077_001E&for=place:*&in=state:01

Target database: the **local warehouse** (``OPEN_NAVIGATOR_DATABASE_URL`` ->
localhost:5433 open_navigator). We deliberately do NOT use the shared
``core_lib`` async session here because its URL resolution prefers
``NEON_DATABASE_URL_DEV``; bronze belongs on the local warehouse, never the slim
Neon serving mirror.

Usage:
    python -m ingestion.census.property_tax                  # all states, place+county, 2023
    python -m ingestion.census.property_tax --state 01       # Alabama only
    python -m ingestion.census.property_tax --year 2023 --grain county
    python -m ingestion.census.property_tax --truncate       # full reload
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any, Iterable

import httpx
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ACS detail variables we collect (median real estate taxes paid, median home value).
TAXES_VAR = "B25103_001E"
VALUE_VAR = "B25077_001E"

# U.S. states + DC + PR (two-digit FIPS) -- place pulls require a parent state.
STATE_FIPS: tuple[str, ...] = (
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17",
    "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
    "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "44", "45", "46",
    "47", "48", "49", "50", "51", "53", "54", "55", "56", "72",
)

# ACS suppresses small / unreliable cells with jumbo negative sentinels
# (e.g. -666666666, -999999999). Treat anything below this as NULL.
_ACS_NULL_CEILING = -100_000_000


# --------------------------------------------------------------------------- #
# Environment (.env) -- load lazily so a bare ``python -m`` run resolves the
# Census key and the warehouse URL without depending on the FastAPI settings
# object or the Neon-first core_lib session.
# --------------------------------------------------------------------------- #
def _load_dotenv_once() -> None:
    """Populate os.environ from the repo-root .env for any keys not already set."""
    for parent in Path(__file__).resolve().parents:
        env_path = parent / ".env"
        if env_path.is_file():
            for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = val.strip().strip('"').strip("'")
            return


def _census_api_key() -> str | None:
    raw = (os.getenv("CENSUS_API_KEY") or "").strip()
    return raw or None


def _warehouse_async_url() -> str:
    """Resolve the LOCAL warehouse URL (open_navigator) as an asyncpg DSN."""
    url = (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
    if not url:
        # Sensible local default matching CLAUDE.md (localhost:5433 open_navigator).
        url = "postgresql://postgres@localhost:5433/open_navigator"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# --------------------------------------------------------------------------- #
# Bronze DDL
# --------------------------------------------------------------------------- #
_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_acs_property_tax (
        geography_type                 VARCHAR(16) NOT NULL,   -- 'place' | 'county'
        geoid                          VARCHAR(16) NOT NULL,   -- state(2)+place(5) or state(2)+county(3)
        state_fips                     VARCHAR(2)  NOT NULL,
        name                           TEXT,
        acs_vintage_year               INTEGER     NOT NULL,
        median_real_estate_taxes_paid  INTEGER,                -- B25103_001E, NULL if suppressed
        median_home_value              INTEGER,                -- B25077_001E, NULL if suppressed
        loaded_at                      TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (geography_type, geoid, acs_vintage_year)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bapt_geoid ON bronze.bronze_acs_property_tax(geoid)"),
    text("CREATE INDEX IF NOT EXISTS idx_bapt_state ON bronze.bronze_acs_property_tax(state_fips)"),
)

_DELETE_YEAR_SQL = text(
    "DELETE FROM bronze.bronze_acs_property_tax WHERE acs_vintage_year = :year"
)
_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_acs_property_tax")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_acs_property_tax
        (geography_type, geoid, state_fips, name, acs_vintage_year,
         median_real_estate_taxes_paid, median_home_value)
    VALUES
        (:geography_type, :geoid, :state_fips, :name, :acs_vintage_year,
         :median_real_estate_taxes_paid, :median_home_value)
    ON CONFLICT (geography_type, geoid, acs_vintage_year) DO UPDATE SET
        state_fips                    = EXCLUDED.state_fips,
        name                          = EXCLUDED.name,
        median_real_estate_taxes_paid = EXCLUDED.median_real_estate_taxes_paid,
        median_home_value             = EXCLUDED.median_home_value,
        loaded_at                     = NOW()
    """
)


# --------------------------------------------------------------------------- #
# Fetch + parse
# --------------------------------------------------------------------------- #
def _clean_dollar(val: Any) -> int | None:
    """Coerce an ACS estimate cell to a non-negative int, or None when suppressed."""
    if val is None:
        return None
    try:
        n = int(float(str(val).strip()))
    except (TypeError, ValueError):
        return None
    if n < 0 or n <= _ACS_NULL_CEILING:
        return None
    return n


async def _fetch(
    client: httpx.AsyncClient, year: int, geography: str, state: str | None, key: str | None
) -> list[dict[str, Any]]:
    """
    Fetch (NAME, taxes, value) for one geography/state and return tidy bronze rows.

    ``state`` is required for ``place`` (Census nests places under a state);
    ``county`` is pulled nationally in one request when ``state`` is None.
    """
    params: dict[str, str] = {
        "get": f"NAME,{TAXES_VAR},{VALUE_VAR}",
        "for": f"{geography}:*",
    }
    if state is not None:
        params["in"] = f"state:{state}"
    if key:
        params["key"] = key

    url = f"https://api.census.gov/data/{year}/acs/acs5"
    resp = await client.get(url, params=params)
    if resp.status_code in (301, 302, 303, 307, 308):
        loc = (resp.headers.get("location") or "").lower()
        if "invalid_key" in loc:
            raise ValueError(
                "api.census.gov rejected CENSUS_API_KEY (invalid or revoked). "
                "Verify it at https://api.census.gov/data/key_signup.html."
            )
        raise httpx.HTTPStatusError(
            f"Unexpected redirect to {loc!r}", request=resp.request, response=resp
        )
    if resp.status_code == 204:
        return []
    resp.raise_for_status()

    data = resp.json()
    header, *body = data
    idx = {col: i for i, col in enumerate(header)}
    rows: list[dict[str, Any]] = []
    for r in body:
        st = r[idx["state"]]
        geo_code = r[idx[geography]]
        geoid = f"{st}{geo_code}"
        rows.append(
            {
                "geography_type": geography,
                "geoid": geoid,
                "state_fips": st,
                "name": r[idx["NAME"]],
                "acs_vintage_year": year,
                "median_real_estate_taxes_paid": _clean_dollar(r[idx[TAXES_VAR]]),
                "median_home_value": _clean_dollar(r[idx[VALUE_VAR]]),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
async def collect(
    *,
    year: int,
    grains: Iterable[str],
    states: list[str],
    truncate: bool,
) -> int:
    key = _census_api_key()
    if not key:
        logger.warning(
            "No CENSUS_API_KEY found -- using the anonymous tier (lower daily limits)."
        )

    engine = create_async_engine(_warehouse_async_url(), pool_pre_ping=True)
    total = 0
    try:
        async with engine.begin() as conn:
            await conn.execute(_CREATE_SCHEMA_SQL)
            await conn.execute(_CREATE_TABLE_SQL)
            for idx_sql in _CREATE_INDEXES_SQL:
                await conn.execute(idx_sql)
            if truncate:
                await conn.execute(_TRUNCATE_SQL)
            else:
                # idempotent re-load for this vintage
                await conn.execute(_DELETE_YEAR_SQL, {"year": year})

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=False) as client:
            for grain in grains:
                if grain == "county":
                    # National county pull in a single request.
                    logger.info("Fetching county B25103/B25077 (national, {})", year)
                    rows = await _fetch(client, year, "county", None, key)
                    total += await _write(engine, rows)
                    logger.success("county: {} rows", len(rows))
                elif grain == "place":
                    for st in states:
                        rows = await _fetch(client, year, "place", st, key)
                        total += await _write(engine, rows)
                        logger.info("place state {}: {} rows", st, len(rows))
                else:
                    raise ValueError(f"Unknown grain: {grain!r} (expected place|county)")
    finally:
        await engine.dispose()

    logger.success("Loaded {:,} rows into bronze.bronze_acs_property_tax", total)
    return total


async def _write(engine: Any, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    async with engine.begin() as conn:
        await conn.execute(_UPSERT_SQL, rows)
    return len(rows)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Collect ACS median real estate taxes (B25103) + median home "
        "value (B25077) at place + county grain into bronze.bronze_acs_property_tax."
    )
    p.add_argument("--year", type=int, default=2023, help="ACS 5-year vintage (default 2023)")
    p.add_argument(
        "--grain",
        choices=["place", "county", "both"],
        default="both",
        help="Geographic grain to pull (default both)",
    )
    p.add_argument(
        "--state",
        default="*",
        help="2-digit state FIPS for place pulls, or '*' for all states+DC+PR (default *)",
    )
    p.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE the bronze table before loading (default: replace just this vintage)",
    )
    return p


def main() -> None:
    _load_dotenv_once()
    args = build_parser().parse_args()
    grains = ["place", "county"] if args.grain == "both" else [args.grain]
    states = list(STATE_FIPS) if args.state == "*" else [str(args.state).zfill(2)]
    asyncio.run(
        collect(year=args.year, grains=grains, states=states, truncate=args.truncate)
    )


if __name__ == "__main__":
    main()

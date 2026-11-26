#!/usr/bin/env python3
"""BLS QCEW industry pipeline (#1019): land the Quarterly Census of Employment and Wages annual averages for one
industry into bronze.bronze_bls_qcew_industry.

Default industry is NAICS **518210** — "Computing Infrastructure Providers, Data Processing, Web Hosting, and Related
Services", the industry BLS counts data center employment under. The open-data CSV holds every area (national,
state, county, MSA) and ownership for that industry and year: payroll employment, establishments and wages from
employers' unemployment-insurance filings. A cell BLS withholds to protect an employer (``disclosure_code = 'N'``)
lands as-is; staging turns its figures into NULL, never 0.

Pipeline shape: ``data/cache/bls/qcew/{industry}_{year}.csv`` holds the raw download (FETCH); each CSV row becomes
one bronze row (LAND), keyed by (area_fips, own_code, industry_code, size_code, year, qtr). Re-runs hit the cache;
``--refresh`` forces a re-fetch. The newest year is re-fetched when its cache is older than a week, since BLS revises.

Source: https://data.bls.gov/cew/data/api/{year}/a/industry/{industry}.csv (public, no key).

Usage:
    python -m ingestion.bls.qcew                              # 518210, 2020-2024
    python -m ingestion.bls.qcew --years 2023 2024 --refresh
    python -m ingestion.bls.qcew --no-fetch                   # cache only
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import time
from pathlib import Path
from typing import Any

import httpx
from core_lib.db import async_session
from loguru import logger
from sqlalchemy import text

CACHE_DIR = Path("data/cache/bls/qcew")
DEFAULT_INDUSTRY = "518210"
DEFAULT_YEARS = [2020, 2021, 2022, 2023, 2024]
URL = "https://data.bls.gov/cew/data/api/{year}/a/industry/{industry}.csv"
# BLS asks automated clients for a descriptive User-Agent; a generic one, no personal contact (see repo rules).
USER_AGENT = "open-navigator-civic-data/1.0"
STALE_SECONDS = 7 * 24 * 3600

# The CSV columns landed (the rest are location-quotient and contribution fields we don't serve).
COLUMNS = [
    "area_fips", "own_code", "industry_code", "agglvl_code", "size_code", "year", "qtr", "disclosure_code",
    "annual_avg_estabs", "annual_avg_emplvl", "total_annual_wages", "annual_avg_wkly_wage", "avg_annual_pay",
    "oty_annual_avg_emplvl_chg", "oty_annual_avg_emplvl_pct_chg",
]


def cache_path(industry: str, year: int, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / f"{industry}_{year}.csv"


def fetch(industry: str, year: int, *, refresh: bool = False, newest: bool = False, cache_dir: Path = CACHE_DIR) -> Path:
    """Download one year's CSV into the cache unless a usable copy is there; return the path."""
    path = cache_path(industry, year, cache_dir)
    stale = newest and path.exists() and time.time() - path.stat().st_mtime > STALE_SECONDS
    if path.exists() and not refresh and not stale:
        logger.info("QCEW cache hit: {} {}", industry, year)
        return path
    url = URL.format(year=year, industry=industry)
    logger.info("QCEW fetch: {}", url)
    r = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True)
    r.raise_for_status()
    if not r.text.startswith('"area_fips"'):
        raise RuntimeError(f"QCEW {year}: unexpected response (not the CSV header)")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(r.text)
    return path


def parse(csv_text: str) -> list[dict[str, Any]]:
    """CSV text -> bronze rows (strings as published; staging types them)."""
    rows = []
    for rec in csv.DictReader(io.StringIO(csv_text)):
        rows.append({c: (rec.get(c) or None) for c in COLUMNS})
    return rows


_CREATE_SQL = [
    text("CREATE SCHEMA IF NOT EXISTS bronze"),
    text(
        """
        CREATE TABLE IF NOT EXISTS bronze.bronze_bls_qcew_industry (
            area_fips                      VARCHAR(5)  NOT NULL,
            own_code                       VARCHAR(1)  NOT NULL,
            industry_code                  VARCHAR(10) NOT NULL,
            agglvl_code                    VARCHAR(3),
            size_code                      VARCHAR(2)  NOT NULL,
            year                           VARCHAR(4)  NOT NULL,
            qtr                            VARCHAR(1)  NOT NULL,
            disclosure_code                VARCHAR(2),
            annual_avg_estabs              TEXT,
            annual_avg_emplvl              TEXT,
            total_annual_wages             TEXT,
            annual_avg_wkly_wage           TEXT,
            avg_annual_pay                 TEXT,
            oty_annual_avg_emplvl_chg      TEXT,
            oty_annual_avg_emplvl_pct_chg  TEXT,
            source_url                     TEXT        NOT NULL,
            loaded_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (area_fips, own_code, industry_code, size_code, year, qtr)
        )
        """
    ),
]

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_bls_qcew_industry (
        area_fips, own_code, industry_code, agglvl_code, size_code, year, qtr, disclosure_code,
        annual_avg_estabs, annual_avg_emplvl, total_annual_wages, annual_avg_wkly_wage, avg_annual_pay,
        oty_annual_avg_emplvl_chg, oty_annual_avg_emplvl_pct_chg, source_url, loaded_at)
    VALUES (
        :area_fips, :own_code, :industry_code, :agglvl_code, :size_code, :year, :qtr, :disclosure_code,
        :annual_avg_estabs, :annual_avg_emplvl, :total_annual_wages, :annual_avg_wkly_wage, :avg_annual_pay,
        :oty_annual_avg_emplvl_chg, :oty_annual_avg_emplvl_pct_chg, :source_url, NOW())
    ON CONFLICT (area_fips, own_code, industry_code, size_code, year, qtr) DO UPDATE SET
        agglvl_code = EXCLUDED.agglvl_code,
        disclosure_code = EXCLUDED.disclosure_code,
        annual_avg_estabs = EXCLUDED.annual_avg_estabs,
        annual_avg_emplvl = EXCLUDED.annual_avg_emplvl,
        total_annual_wages = EXCLUDED.total_annual_wages,
        annual_avg_wkly_wage = EXCLUDED.annual_avg_wkly_wage,
        avg_annual_pay = EXCLUDED.avg_annual_pay,
        oty_annual_avg_emplvl_chg = EXCLUDED.oty_annual_avg_emplvl_chg,
        oty_annual_avg_emplvl_pct_chg = EXCLUDED.oty_annual_avg_emplvl_pct_chg,
        source_url = EXCLUDED.source_url,
        loaded_at = NOW()
    """
)


async def load(industry: str, years: list[int], *, refresh: bool, fetch_enabled: bool) -> int:
    total = 0
    async with async_session() as session:
        for stmt in _CREATE_SQL:
            await session.execute(stmt)
    newest = max(years)
    for year in sorted(years):
        path = cache_path(industry, year)
        if fetch_enabled:
            path = fetch(industry, year, refresh=refresh, newest=(year == newest))
        elif not path.exists():
            logger.warning("QCEW {} {}: no cache and --no-fetch; skipped", industry, year)
            continue
        rows = parse(path.read_text())
        url = URL.format(year=year, industry=industry)
        for r in rows:
            r["source_url"] = url
        async with async_session() as session:
            for i in range(0, len(rows), 1000):
                await session.execute(_UPSERT_SQL, rows[i : i + 1000])
        logger.success("QCEW {} {}: {:,} rows", industry, year, len(rows))
        total += len(rows)
    return total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load BLS QCEW annual averages for one industry into bronze.")
    ap.add_argument("--industry", default=DEFAULT_INDUSTRY, help="NAICS code (default 518210).")
    ap.add_argument("--years", type=int, nargs="+", default=DEFAULT_YEARS, help="Years to load (default 2020-2024).")
    ap.add_argument("--refresh", action="store_true", help="Re-download even when cached.")
    ap.add_argument("--no-fetch", action="store_true", help="Use cached CSVs only.")
    args = ap.parse_args(argv)
    # The engine reads NEON_DATABASE_URL_DEV (the local warehouse) from the environment; load .env, and refuse the
    # engine's SQLite fallback rather than writing bronze into a stray file.
    from dotenv import load_dotenv

    load_dotenv()
    import os

    if not (os.getenv("NEON_DATABASE_URL_DEV") or os.getenv("DATABASE_URL")):
        logger.error("No warehouse DSN: set NEON_DATABASE_URL_DEV (the local warehouse) in .env")
        return 2
    n = asyncio.run(load(args.industry, args.years, refresh=args.refresh, fetch_enabled=not args.no_fetch))
    logger.success("QCEW load done: {:,} rows", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

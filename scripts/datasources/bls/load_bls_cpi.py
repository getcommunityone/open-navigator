#!/usr/bin/env python3
"""Load BLS Consumer Price Index observations into bronze.bronze_bls_cpi.

Default series is **CUUR0000SA0** — CPI-U, Not Seasonally Adjusted, All Items,
U.S. City Average. This is the inflation deflator the frontend real-dollar
toggle uses. Do NOT mix regional CPI series across geographies: the same dollar
series must be deflated by the same yardstick everywhere, or cross-place
"real" comparisons stop being comparable. One national series, applied
uniformly. (No state-, county-, or ZIP-level CPI exists at BLS anyway.)

Source: BLS Public Data API v2 — https://api.bls.gov/publicAPI/v2/timeseries/data/

``annualaverage=true`` asks BLS to compute and return the annual-average row
(``period='M13'``) alongside the monthly observations, so the staging model
doesn't have to recompute it. NSA (not seasonally adjusted) is the right
choice here: seasonal adjustment only matters month-to-month (it averages out
over a year), and the NSA index is the published number that doesn't get
revised.

Usage::

  # Default: CUUR0000SA0, last 20 years, upsert into bronze
  python scripts/datasources/bls/load_bls_cpi.py

  # Custom range, dry-run
  python scripts/datasources/bls/load_bls_cpi.py \\
    --start-year 2000 --end-year 2024 --dry-run

  # Registered key (recommended; 500 req/day vs 25 unregistered, 50 series/req)
  BLS_API_KEY=... python scripts/datasources/bls/load_bls_cpi.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv
from loguru import logger

DEFAULT_SERIES = "CUUR0000SA0"
BLS_ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# BLS API v2 caps a single request at 20 years of data; chunk longer windows.
MAX_YEARS_PER_REQUEST = 20


def _database_url() -> str:
    load_dotenv()
    return (
        (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
        or (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
        or (os.getenv("NEON_DATABASE_URL") or "").strip()
        or (os.getenv("DATABASE_URL") or "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def fetch_series(
    series_id: str,
    start_year: int,
    end_year: int,
    registration_key: str | None,
) -> list[dict]:
    """Fetch one BLS series across ``[start_year, end_year]``, chunked at the API cap."""
    rows: list[dict] = []
    for window_start in range(start_year, end_year + 1, MAX_YEARS_PER_REQUEST):
        window_end = min(window_start + MAX_YEARS_PER_REQUEST - 1, end_year)
        payload: dict = {
            "seriesid": [series_id],
            "startyear": str(window_start),
            "endyear": str(window_end),
            "annualaverage": True,
        }
        if registration_key:
            payload["registrationkey"] = registration_key
        logger.info(
            "BLS request: series={} years={}-{}", series_id, window_start, window_end
        )
        r = requests.post(
            BLS_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        status = body.get("status")
        if status != "REQUEST_SUCCEEDED":
            messages = body.get("message", [])
            raise RuntimeError(
                f"BLS request failed: status={status}, messages={messages}"
            )
        for entry in body.get("Results", {}).get("series", []):
            sid = entry.get("seriesID")
            for d in entry.get("data", []):
                try:
                    value = float(d["value"])
                except (TypeError, ValueError, KeyError):
                    logger.warning("Skipping unparsable row: {}", d)
                    continue
                rows.append(
                    {
                        "series_id": sid,
                        "year": int(d["year"]),
                        "period": d["period"],
                        "period_name": d.get("periodName"),
                        "value": value,
                        "footnotes": "; ".join(
                            (f.get("text") or "")
                            for f in d.get("footnotes", [])
                            if f and f.get("text")
                        )
                        or None,
                    }
                )
    return rows


UPSERT_SQL = """
    INSERT INTO bronze.bronze_bls_cpi
        (series_id, year, period, period_name, value, footnotes, loaded_at, last_updated)
    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
    ON CONFLICT (series_id, year, period) DO UPDATE
        SET period_name  = EXCLUDED.period_name,
            value        = EXCLUDED.value,
            footnotes    = EXCLUDED.footnotes,
            last_updated = NOW()
"""


def upsert(conn, rows: list[dict]) -> int:
    cur = conn.cursor()
    for r in rows:
        cur.execute(
            UPSERT_SQL,
            (
                r["series_id"],
                r["year"],
                r["period"],
                r["period_name"],
                r["value"],
                r["footnotes"],
            ),
        )
    cur.close()
    return len(rows)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--series",
        default=DEFAULT_SERIES,
        help="BLS series id (default: %(default)s — CPI-U NSA all items US city avg)",
    )
    p.add_argument("--start-year", type=int, default=dt.date.today().year - 20)
    p.add_argument("--end-year", type=int, default=dt.date.today().year)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + print summary; no DB write",
    )
    args = p.parse_args()

    if args.end_year < args.start_year:
        logger.error(
            "--end-year ({}) must be >= --start-year ({})",
            args.end_year,
            args.start_year,
        )
        return 1

    load_dotenv()
    registration_key = (os.getenv("BLS_API_KEY") or "").strip() or None
    if not registration_key:
        logger.warning(
            "BLS_API_KEY not set: requests use the unregistered tier "
            "(25/day; no calculations / annual averages on some endpoints)."
        )

    rows = fetch_series(args.series, args.start_year, args.end_year, registration_key)
    annual = [r for r in rows if r["period"] == "M13"]
    monthly = [r for r in rows if r["period"] != "M13"]
    logger.success(
        "Fetched {} rows ({} annual, {} monthly) for series={} years={}-{}",
        len(rows),
        len(annual),
        len(monthly),
        args.series,
        args.start_year,
        args.end_year,
    )

    if args.dry_run:
        logger.info("[dry-run] First 3 annual rows: {}", annual[:3])
        return 0

    if not rows:
        logger.warning("No rows to upsert; exiting without DB write.")
        return 0

    url = _database_url()
    logger.info("Database: {}", url.split("@")[-1] if "@" in url else url)
    conn = psycopg2.connect(url)
    try:
        conn.autocommit = False
        n = upsert(conn, rows)
        conn.commit()
        logger.success("Upserted {} row(s) into bronze.bronze_bls_cpi", n)
        return 0
    except Exception as e:
        conn.rollback()
        logger.exception("BLS load failed: {}", e)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

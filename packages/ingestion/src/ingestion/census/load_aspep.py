"""Load Census Annual Survey of Public Employment and Payroll (ASPEP) into bronze.

    python -m ingestion.census.load_aspep --years 2019 2021 2023 2024
    python -m ingestion.census.load_aspep --years 2023 --dry-run

Source: U.S. Census Bureau, ASPEP "individual unit files" (public domain, no key):
https://www2.census.gov/programs-surveys/apes/datasets/<year>/<year>_individual_unit_files.zip
One row per government x functional category (item code): full-time and part-time
employees and March payroll (31-day monthly equivalent, dollars). It has NO
per-person pay and no department-head salaries; see the decision page. Non-census years
(not ending in 2 or 7) cover only sampled governments, so a missing government in
those years is "not sampled", not "no employees".

Layouts are fixed-width (Census tech doc, section 1.1 and 1.2). Bronze keeps the raw
values; typing, function names and the jurisdiction match are done in dbt.
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import text

from ..pgutil import get_engine

BASE = "https://www2.census.gov/programs-surveys/apes/datasets"
USER_AGENT = "open-navigator (civic data research; https://github.com/getcommunityone/open-navigator)"
CACHE_DIR = Path("data/cache/census/aspep")
DEFAULT_YEARS = [2019, 2020, 2021, 2023, 2024]
DATA_SOURCE = "Census Bureau ASPEP individual unit files"

UNIT_T = "bronze.bronze_aspep_unit"
EMP_T = "bronze.bronze_aspep_employment"

_DDL = [
    "CREATE SCHEMA IF NOT EXISTS bronze",
    f"""CREATE TABLE IF NOT EXISTS {UNIT_T} (
        survey_year INTEGER NOT NULL,
        unit_id TEXT NOT NULL,
        state_code TEXT,
        unit_type_code TEXT,
        county_code TEXT,
        government_name TEXT,
        census_region_code TEXT,
        county_name TEXT,
        fips_state TEXT,
        fips_county TEXT,
        population_or_enrollment TEXT,
        population_year TEXT,
        data_source TEXT,
        ingestion_date TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (survey_year, unit_id)
    )""",
    f"""CREATE TABLE IF NOT EXISTS {EMP_T} (
        survey_year INTEGER NOT NULL,
        unit_id TEXT NOT NULL,
        item_code TEXT NOT NULL,
        full_time_employees TEXT,
        full_time_employees_flag TEXT,
        full_time_payroll TEXT,
        full_time_payroll_flag TEXT,
        part_time_employees TEXT,
        part_time_employees_flag TEXT,
        part_time_payroll TEXT,
        part_time_payroll_flag TEXT,
        data_source TEXT,
        ingestion_date TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (survey_year, unit_id, item_code)
    )""",
]

_UNIT_COLS = [
    "survey_year", "unit_id", "state_code", "unit_type_code", "county_code", "government_name",
    "census_region_code", "county_name", "fips_state", "fips_county",
    "population_or_enrollment", "population_year", "data_source",
]
_EMP_COLS = [
    "survey_year", "unit_id", "item_code", "full_time_employees", "full_time_employees_flag",
    "full_time_payroll", "full_time_payroll_flag", "part_time_employees",
    "part_time_employees_flag", "part_time_payroll", "part_time_payroll_flag", "data_source",
]


def _upsert(table: str, cols: list[str], keys: list[str]):
    sets = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c not in keys)
    return text(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)}) "
        f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {sets}, ingestion_date = NOW()"
    )


def _s(v: str) -> str | None:
    v = v.strip()
    return v or None


def parse_unit(line: str, year: int) -> dict[str, Any] | None:
    """One 23empid.txt line (Census tech doc 1.2, 1-based positions)."""
    if len(line.strip()) < 100:
        return None
    return {
        "survey_year": year,
        "unit_id": line[0:14],
        "state_code": _s(line[0:2]),
        "unit_type_code": _s(line[2:3]),
        "county_code": _s(line[3:6]),
        "government_name": _s(line[14:78]),
        "census_region_code": _s(line[78:79]),
        "county_name": _s(line[79:109]),
        "fips_state": _s(line[109:111]),
        "fips_county": _s(line[111:114]),
        "population_or_enrollment": _s(line[125:134]),
        "population_year": _s(line[134:136]),
        "data_source": DATA_SOURCE,
    }


def parse_employment(line: str, year: int) -> dict[str, Any] | None:
    """One 23empst.txt line (Census tech doc 1.1)."""
    if len(line.strip()) < 44:
        return None
    return {
        "survey_year": year,
        "unit_id": line[0:14],
        "item_code": line[17:20],
        "full_time_employees": _s(line[20:30]),
        "full_time_employees_flag": _s(line[31:32]),
        "full_time_payroll": _s(line[32:44]),
        "full_time_payroll_flag": _s(line[45:46]),
        "part_time_employees": _s(line[46:56]),
        "part_time_employees_flag": _s(line[57:58]),
        "part_time_payroll": _s(line[58:70]),
        "part_time_payroll_flag": _s(line[71:72]),
        "data_source": DATA_SOURCE,
    }


def fetch_zip(year: int) -> bytes:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"{year}_individual_unit_files.zip"
    if cached.exists():
        return cached.read_bytes()
    url = f"{BASE}/{year}/{year}_individual_unit_files.zip"
    logger.info("Downloading {}", url)
    resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=180, follow_redirects=True)
    resp.raise_for_status()
    cached.write_bytes(resp.content)
    return resp.content


def read_year(year: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    yy = str(year)[2:]
    with zipfile.ZipFile(io.BytesIO(fetch_zip(year))) as z:
        names = {n.lower(): n for n in z.namelist()}
        units_f, emp_f = names[f"{yy}empid.txt"], names[f"{yy}empst.txt"]
        units = [r for r in (parse_unit(ln, year) for ln in z.read(units_f).decode("latin-1").splitlines()) if r]
        emps = [r for r in (parse_employment(ln, year) for ln in z.read(emp_f).decode("latin-1").splitlines()) if r]
    return units, emps


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load Census ASPEP individual unit files")
    p.add_argument("--years", type=int, nargs="+", default=DEFAULT_YEARS)
    p.add_argument("--batch", type=int, default=5000)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    engine = None if a.dry_run else get_engine()
    if engine is not None:
        with engine.begin() as cx:
            for stmt in _DDL:
                cx.execute(text(stmt))

    up_u = _upsert(UNIT_T, _UNIT_COLS, ["survey_year", "unit_id"])
    up_e = _upsert(EMP_T, _EMP_COLS, ["survey_year", "unit_id", "item_code"])
    for year in a.years:
        units, emps = read_year(year)
        logger.info("{}: {:,} governments, {:,} government x function rows", year, len(units), len(emps))
        if engine is not None:
            with engine.begin() as cx:
                for i in range(0, len(units), a.batch):
                    cx.execute(up_u, units[i:i + a.batch])
                for i in range(0, len(emps), a.batch):
                    cx.execute(up_e, emps[i:i + a.batch])
            logger.success("Loaded ASPEP {} into bronze", year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

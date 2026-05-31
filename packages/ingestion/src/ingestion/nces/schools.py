#!/usr/bin/env python3
"""NCES CCD school-level (universe) loader -> bronze.bronze_schools_nces.

The district pipeline (school_districts.py) lands the LEA-level files; this loads
the SCHOOL-level CCD directory (file 029) that was downloaded but never landed:
data/cache/nces/ccd_sch_029_*/ccd_sch_029_*.csv  (~102k individual schools).

One snapshot table, replace-loaded (a directory, not incremental):
    bronze.bronze_schools_nces  PK(ncessch)
keyed by NCES school id, carrying the school's own location address and its LEAID
(link to the district). Feeds the MDM org pool via stg_schools__org.

Usage:
    python -m ingestion.nces.schools
Config: MDM_DATABASE_URL / DATABASE_URL (else local dbt warehouse).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

CACHE_GLOB = "data/cache/nces/ccd_sch_029_*/ccd_sch_029_*.csv"
TABLE = "bronze_schools_nces"

# CCD column -> bronze column (school directory, file 029). L* = physical location.
COLUMNS = {
    "NCESSCH": "ncessch",
    "ST_SCHID": "state_school_id",
    "SCH_NAME": "name",
    "LEAID": "leaid",
    "LEA_NAME": "lea_name",
    "ST": "state_code",
    "STATENAME": "state_name",
    "LSTREET1": "address",
    "LSTREET2": "address2",
    "LCITY": "city",
    "LSTATE": "location_state",
    "LZIP": "zip",
    "PHONE": "phone",
    "WEBSITE": "website",
    "SCH_TYPE_TEXT": "school_type",
    "SY_STATUS_TEXT": "status",
    "CHARTER_TEXT": "charter",
    "SCHOOL_YEAR": "school_year",
}


def _dsn() -> str:
    url = os.getenv("MDM_DATABASE_URL") or os.getenv("DATABASE_URL") \
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    return url.replace("postgres://", "postgresql://", 1) if url.startswith("postgres://") else url


def _find_csv() -> Path:
    matches = sorted(Path.cwd().glob(CACHE_GLOB))
    if not matches:
        raise FileNotFoundError(f"no CCD school directory CSV at {CACHE_GLOB}")
    return matches[-1]  # newest


def load() -> int:
    path = _find_csv()
    logger.info("Reading NCES school directory {}", path.name)
    # CCD files are latin-1; read as strings to preserve ids/zip leading zeros.
    df = pd.read_csv(path, dtype=str, encoding="latin-1", usecols=lambda c: c in COLUMNS)
    df = df.rename(columns=COLUMNS)
    for col in COLUMNS.values():
        if col not in df.columns:
            df[col] = None
    df = df[list(COLUMNS.values())]
    df["loaded_at"] = pd.Timestamp.utcnow()

    engine = create_engine(_dsn())
    with engine.begin() as conn:
        conn.execute(text("create schema if not exists bronze"))
    df.to_sql(TABLE, engine, schema="bronze", if_exists="replace", index=False, chunksize=10_000)
    with engine.begin() as conn:
        conn.execute(text(
            f'alter table bronze.{TABLE} add constraint {TABLE}_pkey primary key (ncessch)'
        ))
    logger.success("Loaded {:,} schools into bronze.{}", len(df), TABLE)
    return len(df)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    load()


if __name__ == "__main__":
    main()

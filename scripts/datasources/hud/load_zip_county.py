#!/usr/bin/env python3
"""
HUD ZIP-to-County Crosswalk → bronze.bronze_jurisdictions_zip_county

Reads the HUD USPS ZIP-County crosswalk Excel file from the local cache
and upserts records into the bronze_jurisdictions_zip_county PostgreSQL table.

Source: HUD USPS ZIP Code Crosswalk Files (quarterly)
File:   data/cache/hud/ZIP_COUNTY_<MMYYYY>.xlsx

Columns loaded:
  ZIP, COUNTY, USPS_ZIP_PREF_CITY, USPS_ZIP_PREF_STATE,
  RES_RATIO, BUS_RATIO, OTH_RATIO, TOT_RATIO

Usage:
    python scripts/datasources/hud/load_zip_county.py
    python scripts/datasources/hud/load_zip_county.py --truncate
    python scripts/datasources/hud/load_zip_county.py --file data/cache/hud/ZIP_COUNTY_122025.xlsx
    python scripts/datasources/hud/load_zip_county.py --limit 500 --dry-run
"""

import sys
import os
import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2.extras import execute_values
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

CACHE_DIR = Path("data/cache/hud")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"

EXPECTED_MIN = 40_000
EXPECTED_MAX = 70_000

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_zip_county (
        zip                  CHAR(5)        NOT NULL,
        county               CHAR(5)        NOT NULL,
        usps_zip_pref_city   VARCHAR(100),
        usps_zip_pref_state  CHAR(2),
        res_ratio            NUMERIC(20, 17),
        bus_ratio            NUMERIC(20, 17),
        oth_ratio            NUMERIC(20, 17),
        tot_ratio            NUMERIC(20, 17),
        ingestion_date       TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (zip, county)
    );
    CREATE INDEX IF NOT EXISTS idx_bzc_zip    ON bronze.bronze_jurisdictions_zip_county(zip);
    CREATE INDEX IF NOT EXISTS idx_bzc_county ON bronze.bronze_jurisdictions_zip_county(county);
    CREATE INDEX IF NOT EXISTS idx_bzc_state  ON bronze.bronze_jurisdictions_zip_county(usps_zip_pref_state);
"""

UPSERT_SQL = """
    INSERT INTO bronze.bronze_jurisdictions_zip_county
        (zip, county, usps_zip_pref_city, usps_zip_pref_state,
         res_ratio, bus_ratio, oth_ratio, tot_ratio)
    VALUES %s
    ON CONFLICT (zip, county) DO UPDATE SET
        usps_zip_pref_city  = EXCLUDED.usps_zip_pref_city,
        usps_zip_pref_state = EXCLUDED.usps_zip_pref_state,
        res_ratio           = EXCLUDED.res_ratio,
        bus_ratio           = EXCLUDED.bus_ratio,
        oth_ratio           = EXCLUDED.oth_ratio,
        tot_ratio           = EXCLUDED.tot_ratio,
        ingestion_date      = NOW()
"""


def find_latest_xlsx() -> Path:
    files = sorted(CACHE_DIR.glob("ZIP_COUNTY_*.xlsx"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No HUD ZIP_COUNTY xlsx found in {CACHE_DIR}. "
            "Download from https://www.huduser.gov/portal/datasets/usps_crosswalk.html"
        )
    return files[0]


def _safe_decimal(val: str | None) -> Decimal | None:
    if val is None or val.strip() == "":
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return None


def _safe_str(val: str | None, maxlen: int = None) -> str | None:
    if val is None:
        return None
    s = val.strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def parse_xlsx(path: Path, limit: int = None) -> list[tuple]:
    logger.info(f"Parsing {path} ...")

    with zipfile.ZipFile(path) as z:
        shared_strings = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = [
            si.find(".//s:t", NS).text
            for si in shared_strings.findall("s:si", NS)
        ]

        ws = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    rows = ws.findall(".//s:row", NS)
    logger.info(f"Rows in sheet (incl. header): {len(rows):,}")

    def cell_value(c):
        t = c.get("t")
        v = c.find("s:v", NS)
        if v is None:
            return None
        return strings[int(v.text)] if t == "s" else v.text

    # Skip header row
    data_rows = rows[1:]
    if limit:
        data_rows = data_rows[:limit]

    records = []
    for row in data_rows:
        cells = [cell_value(c) for c in row.findall("s:c", NS)]
        # Pad to 8 columns if any trailing cells are missing
        while len(cells) < 8:
            cells.append(None)

        zip_code = _safe_str(cells[0], 5)
        county   = _safe_str(cells[1], 5)

        if not zip_code or not county:
            continue

        records.append((
            zip_code,
            county,
            _safe_str(cells[2], 100),   # usps_zip_pref_city
            _safe_str(cells[3], 2),     # usps_zip_pref_state
            _safe_decimal(cells[4]),    # res_ratio
            _safe_decimal(cells[5]),    # bus_ratio
            _safe_decimal(cells[6]),    # oth_ratio
            _safe_decimal(cells[7]),    # tot_ratio
        ))

    logger.info(f"Prepared {len(records):,} records")
    return records


def load(records: list[tuple], truncate: bool, dry_run: bool) -> None:
    if dry_run:
        logger.info(f"[DRY RUN] Would upsert {len(records):,} records — skipping DB writes")
        if records:
            logger.info(f"  Sample: {records[0]}")
        return

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()
            logger.info("Table ensured.")

            if truncate:
                cur.execute("TRUNCATE TABLE bronze.bronze_jurisdictions_zip_county")
                conn.commit()
                logger.warning("Table truncated.")

            execute_values(cur, UPSERT_SQL, records, page_size=2_000)
            conn.commit()
            logger.success(f"Upserted {len(records):,} records into bronze.bronze_jurisdictions_zip_county")

            cur.execute("SELECT COUNT(*) FROM bronze.bronze_jurisdictions_zip_county")
            table_count = cur.fetchone()[0]
            logger.info(f"Table row count: {table_count:,}")

            if not truncate and not (EXPECTED_MIN <= table_count <= EXPECTED_MAX):
                logger.warning(
                    f"Row count {table_count:,} outside expected range "
                    f"[{EXPECTED_MIN:,}, {EXPECTED_MAX:,}]"
                )


def main():
    parser = argparse.ArgumentParser(description="Load HUD ZIP-to-County crosswalk into bronze")
    parser.add_argument("--file",     type=Path, help="Override xlsx path")
    parser.add_argument("--truncate", action="store_true", help="Truncate table before loading")
    parser.add_argument("--dry-run",  action="store_true", help="Parse only, no DB writes")
    parser.add_argument("--limit",    type=int,  help="Load only the first N data rows")
    args = parser.parse_args()

    xlsx_path = args.file or find_latest_xlsx()
    logger.info(f"Source file: {xlsx_path}")

    records = parse_xlsx(xlsx_path, limit=args.limit)
    load(records, truncate=args.truncate, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

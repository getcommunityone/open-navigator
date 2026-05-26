#!/usr/bin/env python3
"""
Load parcel attribute CSV (Esri harvest) into bronze.bronze_addresses.

Usage:
    .venv/bin/python scripts/datasources/parcels/load_parcel_addresses_to_bronze.py \\
        --csv data/cache/parcels/al/tuscaloosa_county_attrs.csv \\
        --state AL \\
        --county-fips 01125 \\
        --county-name Tuscaloosa \\
        --dataset al_tuscaloosa_county_parcels \\
        --esri-endpoint "https://services.arcgis.com/AWzSDaKZ41uuVges/ArcGIS/rest/services/Parcels/FeatureServer/0"

    .venv/bin/python scripts/datasources/parcels/load_parcel_addresses_to_bronze.py --truncate ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from loguru import logger
from psycopg2.extras import Json, execute_batch

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.database.target_database_url import resolve_target_database_url  # noqa: E402

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from field_mappings import normalize_column_names  # noqa: E402

BRONZE_TABLE = "bronze.bronze_addresses"
BATCH_SIZE = 5000

CREATE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_addresses (
        id                      BIGSERIAL PRIMARY KEY,
        source_dataset          TEXT          NOT NULL,
        source_record_id        TEXT          NOT NULL,
        state_code              CHAR(2)       NOT NULL,
        county_fips             VARCHAR(5),
        county_name             TEXT,
        jurisdiction_id         TEXT,
        owner_name              TEXT,
        situs_location          TEXT,
        street_number           TEXT,
        street_line1            TEXT,
        street_line2            TEXT,
        city                    TEXT,
        state_abbr              CHAR(2),
        postal_code             VARCHAR(10),
        situs_full              TEXT,
        parcel_number           TEXT,
        parcel_number_formatted TEXT,
        appraised_value         BIGINT,
        tax_class               TEXT,
        data_source             TEXT          NOT NULL DEFAULT 'esri_parcel',
        esri_endpoint           TEXT,
        raw_attributes          JSONB         NOT NULL DEFAULT '{}'::jsonb,
        loaded_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_bronze_addresses_source UNIQUE (source_dataset, source_record_id)
    );
    CREATE INDEX IF NOT EXISTS idx_bronze_addresses_state_county
        ON bronze.bronze_addresses (state_code, county_fips);
    CREATE INDEX IF NOT EXISTS idx_bronze_addresses_jurisdiction_id
        ON bronze.bronze_addresses (jurisdiction_id)
        WHERE jurisdiction_id IS NOT NULL;
"""

INSERT_SQL = f"""
    INSERT INTO {BRONZE_TABLE} (
        source_dataset, source_record_id, state_code, county_fips, county_name,
        jurisdiction_id, owner_name, situs_location, street_number, street_line1,
        street_line2, city, state_abbr, postal_code, situs_full, parcel_number,
        parcel_number_formatted, appraised_value, tax_class, data_source,
        esri_endpoint, raw_attributes
    ) VALUES (
        %(source_dataset)s, %(source_record_id)s, %(state_code)s, %(county_fips)s,
        %(county_name)s, %(jurisdiction_id)s, %(owner_name)s, %(situs_location)s,
        %(street_number)s, %(street_line1)s, %(street_line2)s, %(city)s,
        %(state_abbr)s, %(postal_code)s, %(situs_full)s, %(parcel_number)s,
        %(parcel_number_formatted)s, %(appraised_value)s, %(tax_class)s,
        %(data_source)s, %(esri_endpoint)s, %(raw_attributes)s
    )
    ON CONFLICT (source_dataset, source_record_id) DO UPDATE SET
        owner_name = EXCLUDED.owner_name,
        situs_location = EXCLUDED.situs_location,
        street_number = EXCLUDED.street_number,
        street_line1 = EXCLUDED.street_line1,
        street_line2 = EXCLUDED.street_line2,
        city = EXCLUDED.city,
        state_abbr = EXCLUDED.state_abbr,
        postal_code = EXCLUDED.postal_code,
        situs_full = EXCLUDED.situs_full,
        parcel_number = EXCLUDED.parcel_number,
        parcel_number_formatted = EXCLUDED.parcel_number_formatted,
        appraised_value = EXCLUDED.appraised_value,
        tax_class = EXCLUDED.tax_class,
        esri_endpoint = EXCLUDED.esri_endpoint,
        raw_attributes = EXCLUDED.raw_attributes,
        loaded_at = NOW()
"""


def _clean_str(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s else None


def _clean_int(val: Any) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _first_str(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = _clean_str(row.get(key))
        if val:
            return val
    return None


def _first_int(row: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        val = _clean_int(row.get(key))
        if val is not None:
            return val
    return None


def _build_situs_full(row: dict[str, Any]) -> str | None:
    situs = _first_str(row, "situs_address", "pcliLocati", "SITUS_ADDRESS", "ADDRESS", "SITEADDRESS")
    parts: list[str] = []
    if situs:
        parts.append(situs)
    num = _first_str(row, "addSTRTNUM", "STREETNUM", "HOUSE_NUM")
    s1 = _first_str(row, "addSTRT1", "STREETNAME", "STREET")
    s2 = _first_str(row, "addSTRT2")
    street_bits = [p for p in (num, s1, s2) if p]
    if street_bits and (not situs or " ".join(street_bits) not in situs):
        parts.append(" ".join(street_bits))
    city = _first_str(row, "addCITY", "CITY", "PROP_CITY")
    st = _first_str(row, "stABBR", "STATE", "STATECODE") or None
    z = _first_str(row, "addZIP", "ZIP", "ZIPCODE")
    if city:
        tail = " ".join(p for p in (st, z) if p)
        parts.append(f"{city}, {tail}" if tail else city)
    return ", ".join(parts) if parts else situs


def _source_record_id(row: dict[str, Any]) -> str:
    val = _first_str(
        row,
        "parcel_id",
        "PCNUM_FMT",
        "PARCEL_ID",
        "PARCELID",
        "PIN",
        "pclnum",
        "ppin",
        "PARCEL",
        "OBJECTID",
        "FID",
        "Name",
    )
    return val or "unknown"


def row_to_record(
    row: dict[str, Any],
    *,
    source_dataset: str,
    state_code: str,
    county_fips: str | None,
    county_name: str | None,
    jurisdiction_id: str | None,
    esri_endpoint: str | None,
) -> dict[str, Any]:
    return {
        "source_dataset": source_dataset,
        "source_record_id": _source_record_id(row),
        "state_code": state_code.upper()[:2],
        "county_fips": county_fips,
        "county_name": county_name,
        "jurisdiction_id": jurisdiction_id,
        "owner_name": _first_str(row, "owner_primary", "pcloNAME", "OWNER_NAME", "OWNER1", "OWNER"),
        "situs_location": _first_str(row, "situs_address", "pcliLocati", "SITUS_ADDRESS", "ADDRESS"),
        "street_number": _first_str(row, "addSTRTNUM", "STREETNUM"),
        "street_line1": _first_str(row, "addSTRT1", "STREETNAME", "STREET"),
        "street_line2": _first_str(row, "addSTRT2"),
        "city": _first_str(row, "addCITY", "CITY"),
        "state_abbr": (_first_str(row, "stABBR", "STATE") or state_code.upper())[:2] or None,
        "postal_code": _first_str(row, "addZIP", "ZIP", "ZIPCODE"),
        "situs_full": _build_situs_full(row),
        "parcel_number": _first_str(row, "parcel_id", "pclnum", "PIN", "PARCEL", "PARCELID"),
        "parcel_number_formatted": _first_str(row, "PCNUM_FMT", "parcel_id", "PARCEL_ID"),
        "appraised_value": _first_int(
            row, "appraised_total_value", "appraised", "TOTAL_VAL", "ASSESSED_VALUE", "APPRAISED_VALUE"
        ),
        "tax_class": _first_str(row, "tax_class", "TaxClass", "TAX_CLASS", "PROP_CLASS"),
        "data_source": "esri_parcel",
        "esri_endpoint": esri_endpoint,
        "raw_attributes": Json({k: (None if pd.isna(v) else v) for k, v in row.items()}),
    }


def load_csv_to_bronze(
    csv_path: Path,
    *,
    db_url: str,
    source_dataset: str,
    state_code: str,
    county_fips: str | None,
    county_name: str | None,
    jurisdiction_id: str | None,
    esri_endpoint: str | None,
    truncate: bool,
    dry_run: bool,
    limit: int | None,
) -> int:
    logger.info("Reading {}", csv_path)
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    df = normalize_column_names(df)
    if limit:
        df = df.head(limit)
    logger.info("Prepared {:,} rows for {}", len(df), BRONZE_TABLE)

    if dry_run:
        sample = row_to_record(
            df.iloc[0].to_dict(),
            source_dataset=source_dataset,
            state_code=state_code,
            county_fips=county_fips,
            county_name=county_name,
            jurisdiction_id=jurisdiction_id,
            esri_endpoint=esri_endpoint,
        )
        logger.info("Dry-run sample: {}", json.dumps({k: v for k, v in sample.items() if k != "raw_attributes"}, default=str))
        return len(df)

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
            if truncate:
                logger.warning("Truncating {} for dataset {}", BRONZE_TABLE, source_dataset)
                cur.execute(f"DELETE FROM {BRONZE_TABLE} WHERE source_dataset = %s", (source_dataset,))
            conn.commit()

        records = [
            row_to_record(
                row,
                source_dataset=source_dataset,
                state_code=state_code,
                county_fips=county_fips,
                county_name=county_name,
                jurisdiction_id=jurisdiction_id,
                esri_endpoint=esri_endpoint,
            )
            for row in df.to_dict(orient="records")
        ]

        with conn.cursor() as cur:
            for start in range(0, len(records), BATCH_SIZE):
                batch = records[start : start + BATCH_SIZE]
                execute_batch(cur, INSERT_SQL, batch, page_size=1000)
                logger.info("Inserted {:,} / {:,}", min(start + BATCH_SIZE, len(records)), len(records))
            conn.commit()
    finally:
        conn.close()

    logger.success("Loaded {:,} rows into {}", len(df), BRONZE_TABLE)
    return len(df)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load parcel CSV into bronze.bronze_addresses")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--state", required=True, help="2-letter state code (e.g. AL)")
    parser.add_argument("--county-fips", help="5-digit county FIPS (e.g. 01125)")
    parser.add_argument("--county-name", help="County name (e.g. Tuscaloosa)")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Unique source_dataset key (e.g. al_tuscaloosa_county_parcels)",
    )
    parser.add_argument("--jurisdiction-id", help="e.g. county_01125 (default: county_<fips>)")
    parser.add_argument("--esri-endpoint", help="Originating Esri layer URL")
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows for this dataset first")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        logger.error("CSV not found: {}", csv_path)
        return 1

    jurisdiction_id = args.jurisdiction_id
    if not jurisdiction_id and args.county_fips:
        jurisdiction_id = f"county_{args.county_fips}"

    load_csv_to_bronze(
        csv_path,
        db_url=resolve_target_database_url(),
        source_dataset=args.dataset,
        state_code=args.state.upper(),
        county_fips=args.county_fips,
        county_name=args.county_name,
        jurisdiction_id=jurisdiction_id,
        esri_endpoint=args.esri_endpoint,
        truncate=args.truncate,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Parcel addresses pipeline: load Esri parcel-attribute CSV into bronze.bronze_addresses.

Ported from load_parcel_addresses_to_bronze.py to the core_lib
DataSourcePipeline contract.

Data source: county Esri parcel feature services, harvested to CSV under
data/cache/parcels/<state>/<county>_attrs.csv. Localized Esri column names are
normalized to a small canonical vocabulary before bronze load.

Usage:
    python -m ingestion.arcgis.addresses \\
        --csv data/cache/parcels/al/tuscaloosa_county_attrs.csv \\
        --state AL \\
        --county-fips 01125 \\
        --county-name Tuscaloosa \\
        --dataset al_tuscaloosa_county_parcels \\
        --esri-endpoint "https://services.arcgis.com/.../FeatureServer/0"

    python -m ingestion.arcgis.addresses --truncate ...

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 connection to the local target database).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


BRONZE_TABLE = "bronze.bronze_addresses"


# ---------------------------------------------------------------------------
# Canonical parcel-attribute names and county-specific Esri field aliases.
#
# Vendored verbatim from scripts/datasources/parcels/field_mappings.py so the
# package is self-contained (no dependency on the scripts/ tree). Counties
# rarely share column names; map localized Esri fields to a small standard
# vocabulary before bronze load.
# ---------------------------------------------------------------------------

# canonical_name -> source aliases (first match wins, case-insensitive)
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "parcel_id": (
        "PARCEL_ID",
        "PARCELID",
        "PIN",
        "APN",
        "PROP_ID",
        "PROP_ID_NUM",
        "GEOPIN",
        "pclnum",
        "PCNUM_FMT",
        "PARCEL",
        "PARCEL_NUM",
        "ppin",
    ),
    "situs_address": (
        "SITUS_ADDRESS",
        "SITUS_ADDR",
        "PROP_ADR",
        "PROP_ADDR",
        "LOC_ADDR",
        "SITE_ADDR",
        "PHY_ADDR",
        "PROPERTY_ADDRESS",
        "pcliLocati",
        "ADDRESS",
        "SITEADDRESS",
    ),
    "owner_primary": (
        "OWNER_NAME",
        "OWNER1",
        "OWN_NAME",
        "PR_OWNER",
        "M_OWNER",
        "OWNER",
        "TAX_OWNER",
        "pcloNAME",
        "NAME1",
        "OWNERNAMES",
    ),
    "owner_secondary": (
        "OWNER2",
        "CO_OWNER",
        "SECONDARY_OWNER",
    ),
    "legal_description": (
        "LEGAL_DESC",
        "LEGAL_DESCRIPTION",
        "LEGAL",
        "LDESC",
    ),
    "appraised_improvement_value": (
        "IMPR_VAL",
        "IMP_VALUE",
        "BLDG_APPRAISAL",
        "IMPROVEMENT_VALUE",
        "BLDG_VAL",
    ),
    "appraised_land_value": (
        "LAND_VAL",
        "LAND_VALUE",
        "LAND_APPRAISAL",
    ),
    "appraised_total_value": (
        "TOTAL_VAL",
        "TOTAL_VALUE",
        "APPRAISED_VALUE",
        "APPR_VAL",
        "TOT_VAL",
        "ASSESSED_VALUE",
        "TOTAL_APPR",
        "appraised",
        "TOTALAPPR",
        "APPR_TOTAL",
    ),
    "tax_class": ("TaxClass", "TAX_CLASS", "CLASS", "PROP_CLASS"),
}


def build_rename_map(columns: Iterable[str]) -> dict[str, str]:
    """Map raw Esri column names to canonical names where an alias is recognized."""
    upper_to_orig = {str(c).upper(): str(c) for c in columns}
    renames: dict[str, str] = {}
    for canonical, aliases in CANONICAL_ALIASES.items():
        for alias in aliases:
            orig = upper_to_orig.get(alias.upper())
            if orig is not None and orig not in renames:
                renames[orig] = canonical
                break
    return renames


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with recognized parcel fields renamed to canonical names."""
    renames = build_rename_map(df.columns)
    if not renames:
        return df.copy()
    return df.rename(columns=renames)


# ---------------------------------------------------------------------------
# Pure helpers (preserved verbatim from the legacy loader).
# ---------------------------------------------------------------------------


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
        "raw_attributes": {k: (None if pd.isna(v) else v) for k, v in row.items()},
    }


# ---------------------------------------------------------------------------
# Row schema (nullability mirrors the bronze.bronze_addresses DDL).
# ---------------------------------------------------------------------------


class ParcelAddressRow(RawRow):
    """One parcel address row, validated before upsert."""

    source_dataset: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    state_code: str = Field(min_length=1, max_length=2)
    county_fips: str | None = Field(default=None, max_length=5)
    county_name: str | None = None
    jurisdiction_id: str | None = None
    owner_name: str | None = None
    situs_location: str | None = None
    street_number: str | None = None
    street_line1: str | None = None
    street_line2: str | None = None
    city: str | None = None
    state_abbr: str | None = Field(default=None, max_length=2)
    postal_code: str | None = Field(default=None, max_length=10)
    situs_full: str | None = None
    parcel_number: str | None = None
    parcel_number_formatted: str | None = None
    appraised_value: int | None = None
    tax_class: str | None = None
    data_source: str = Field(default="esri_parcel", min_length=1)
    esri_endpoint: str | None = None
    raw_attributes: dict[str, Any] = Field(default_factory=dict)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
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
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        """
        CREATE INDEX IF NOT EXISTS idx_bronze_addresses_state_county
            ON bronze.bronze_addresses (state_code, county_fips)
        """
    ),
    text(
        """
        CREATE INDEX IF NOT EXISTS idx_bronze_addresses_jurisdiction_id
            ON bronze.bronze_addresses (jurisdiction_id)
            WHERE jurisdiction_id IS NOT NULL
        """
    ),
)

# The legacy loader deletes only the rows for the dataset being (re)loaded,
# not the entire table; preserve that scoped behavior.
_DELETE_DATASET_SQL = text(
    f"DELETE FROM {BRONZE_TABLE} WHERE source_dataset = :source_dataset"
)

_UPSERT_SQL = text(
    f"""
    INSERT INTO {BRONZE_TABLE} (
        source_dataset, source_record_id, state_code, county_fips, county_name,
        jurisdiction_id, owner_name, situs_location, street_number, street_line1,
        street_line2, city, state_abbr, postal_code, situs_full, parcel_number,
        parcel_number_formatted, appraised_value, tax_class, data_source,
        esri_endpoint, raw_attributes
    ) VALUES (
        :source_dataset, :source_record_id, :state_code, :county_fips,
        :county_name, :jurisdiction_id, :owner_name, :situs_location,
        :street_number, :street_line1, :street_line2, :city,
        :state_abbr, :postal_code, :situs_full, :parcel_number,
        :parcel_number_formatted, :appraised_value, :tax_class,
        :data_source, :esri_endpoint, CAST(:raw_attributes AS jsonb)
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
)


class ArcgisAddressesPipeline(DataSourcePipeline[ParcelAddressRow]):
    source = "arcgis_addresses"
    batch_size = 5_000
    row_schema = ParcelAddressRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        limit: int | None = None,
        source_dataset: str | None = None,
        state_code: str | None = None,
        county_fips: str | None = None,
        county_name: str | None = None,
        jurisdiction_id: str | None = None,
        esri_endpoint: str | None = None,
    ):
        self._path = path
        self._limit = limit
        self._source_dataset = source_dataset
        self._state_code = state_code
        self._county_fips = county_fips
        self._county_name = county_name
        self._jurisdiction_id = jurisdiction_id
        self._esri_endpoint = esri_endpoint

    def _discover_path(self) -> Path:
        if self._path is None:
            raise FileNotFoundError("No parcel CSV path provided (--csv).")
        path = Path(self._path)
        if not path.is_file():
            raise FileNotFoundError(f"CSV not found: {path}")
        return path

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._discover_path()
        df = pd.read_csv(path, dtype=str, low_memory=False)
        df = normalize_column_names(df)
        if self._limit:
            df = df.head(self._limit)
        for row in df.to_dict(orient="records"):
            record = row_to_record(
                row,
                source_dataset=self._source_dataset or "",
                state_code=self._state_code or "",
                county_fips=self._county_fips,
                county_name=self._county_name,
                jurisdiction_id=self._jurisdiction_id,
                esri_endpoint=self._esri_endpoint,
            )
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": f"{record['source_dataset']}:{record['source_record_id']}",
                **record,
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[ParcelAddressRow],
        ctx: PipelineContext,
    ) -> None:
        params = []
        for r in rows:
            d = r.model_dump()
            d["raw_attributes"] = json.dumps(d.get("raw_attributes") or {}, default=str)
            # RawRow envelope fields are not part of the INSERT; drop them.
            for k in ("source", "source_version", "natural_key", "ingested_at"):
                d.pop(k, None)
            params.append(d)
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool, source_dataset: str | None = None) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate and source_dataset:
            await session.execute(_DELETE_DATASET_SQL, {"source_dataset": source_dataset})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load parcel CSV into bronze.bronze_addresses"
    )
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
    parser.add_argument(
        "--truncate", action="store_true",
        help="Delete existing rows for this dataset first",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser


async def _run(args: argparse.Namespace) -> None:
    jurisdiction_id = args.jurisdiction_id
    if not jurisdiction_id and args.county_fips:
        jurisdiction_id = f"county_{args.county_fips}"

    await _prepare_target(args.truncate, source_dataset=args.dataset)
    pipeline = ArcgisAddressesPipeline(
        path=args.csv,
        limit=args.limit,
        source_dataset=args.dataset,
        state_code=args.state.upper(),
        county_fips=args.county_fips,
        county_name=args.county_name,
        jurisdiction_id=jurisdiction_id,
        esri_endpoint=args.esri_endpoint,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

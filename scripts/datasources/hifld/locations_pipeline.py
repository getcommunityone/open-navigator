#!/usr/bin/env python3
"""HIFLD infrastructure locations pipeline: load cached parquet datasets into bronze.

Ported from load_hifld_to_postgres.py to the core_lib DataSourcePipeline
contract.

HIFLD datasets (places of worship, schools, hospitals, emergency services,
government buildings, etc.) are cached as parquet files under
data/cache/hifld/. Each row becomes one bronze.bronze_locations record;
fields not in the standard schema are preserved in `additional_info` JSONB.

Usage:
    python -m scripts.datasources.hifld.locations_pipeline
    python scripts/datasources/hifld/locations_pipeline.py \\
        --file data/cache/hifld/Hospitals.parquet --org-type hospital

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded localhost:5433/open_navigator).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/hifld")

STANDARD_FIELDS = {
    "name", "address", "city", "state", "zip", "county",
    "latitude", "longitude", "telephone", "website", "source_id",
}

# HIFLD datasets use wildly inconsistent column names; normalize them.
FIELD_MAP = {
    # Name
    "NAME": "name", "FACNAME": "name", "FACILITY_NAME": "name",
    "SCHOOL_NAME": "name", "HOSPITAL_NAME": "name",
    # Address
    "ADDRESS": "address", "STREET": "address", "ADDR": "address", "LOCATION": "address",
    # City
    "CITY": "city", "CITYNAME": "city",
    # State
    "STATE": "state", "ST": "state", "STATE_ABBR": "state",
    # Zip
    "ZIP": "zip", "ZIPCODE": "zip", "ZIP_CODE": "zip",
    # County
    "COUNTY": "county", "COUNTYNAME": "county",
    # Coords
    "LATITUDE": "latitude", "LAT": "latitude", "Y": "latitude",
    "LONGITUDE": "longitude", "LON": "longitude", "LONG": "longitude", "X": "longitude",
    # Contact
    "TELEPHONE": "telephone", "PHONE": "telephone", "TEL": "telephone",
    "WEBSITE": "website", "URL": "website", "WEB": "website",
    # IDs
    "FID": "source_id", "ID": "source_id", "OBJECTID": "source_id",
    "FACILITY_ID": "source_id",
}


def map_organization_type(dataset_name: str, row: dict) -> str:
    """Determine organization type from dataset name and row data."""
    name = dataset_name.lower()
    if "law_enforcement" in name or "police" in name:
        return str(row.get("TYPE", "law_enforcement")).lower().replace(" ", "_")
    if "worship" in name or "church" in name or "religious" in name:
        return "place_of_worship"
    if "school" in name or "education" in name:
        return "school"
    if "hospital" in name or "healthcare" in name or "medical" in name:
        return "hospital"
    if "fire" in name:
        return "fire_station"
    if "government" in name or "courthouse" in name or "city_hall" in name:
        return "government_building"
    return "other"


def normalize_field_names(df: pd.DataFrame) -> pd.DataFrame:
    rename_dict = {}
    for col in df.columns:
        if col.upper() in FIELD_MAP:
            rename_dict[col] = FIELD_MAP[col.upper()]
    if rename_dict:
        df = df.rename(columns=rename_dict)
    return df


def _read_parquet(path: Path) -> pd.DataFrame:
    """Read a HIFLD parquet, preferring geopandas if available + applicable."""
    try:
        import geopandas as gpd  # noqa: WPS433
        return gpd.read_parquet(path)
    except Exception:
        return pd.read_parquet(path)


def _truncate(val: Any, maxlen: int) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val)
    if not s or s.upper() == "NOT AVAILABLE":
        return None
    return s[:maxlen]


def _opt_float(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class LocationRow(RawRow):
    """One HIFLD infrastructure location, validated before insert."""

    source_id: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=500)
    organization_type: str = Field(min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=200)
    state: str | None = Field(default=None, max_length=2)
    zip_: str | None = Field(default=None, max_length=10, alias="zip")
    county: str | None = Field(default=None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    telephone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)
    source_dataset: str = Field(min_length=1, max_length=200)
    additional_info: dict[str, Any] | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")
_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_locations (
        id SERIAL PRIMARY KEY,
        source_id VARCHAR(100),
        name VARCHAR(500),
        organization_type VARCHAR(100),
        address VARCHAR(500),
        city VARCHAR(200),
        state VARCHAR(2),
        state_name VARCHAR(100),
        zip VARCHAR(10),
        county VARCHAR(200),
        latitude DECIMAL(10, 7),
        longitude DECIMAL(10, 7),
        telephone VARCHAR(50),
        website VARCHAR(500),
        data_source VARCHAR(100) DEFAULT 'HIFLD',
        source_dataset VARCHAR(200),
        additional_info JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        CONSTRAINT uq_bronze_locations_source UNIQUE (source_dataset, source_id)
    )
    """
)
_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bronzeloc_type ON bronze.bronze_locations(organization_type)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronzeloc_state ON bronze.bronze_locations(state)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronzeloc_city ON bronze.bronze_locations(city)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronzeloc_coords ON bronze.bronze_locations(latitude, longitude)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronzeloc_source ON bronze.bronze_locations(source_dataset)"),
)
_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_locations (
        source_id, name, organization_type, address, city, state, zip,
        county, latitude, longitude, telephone, website,
        source_dataset, additional_info
    )
    VALUES (
        :source_id, :name, :organization_type, :address, :city, :state, :zip,
        :county, :latitude, :longitude, :telephone, :website,
        :source_dataset, CAST(:additional_info AS jsonb)
    )
    ON CONFLICT ON CONSTRAINT uq_bronze_locations_source DO NOTHING
    """
)


class HifldLocationsPipeline(DataSourcePipeline[LocationRow]):
    source = "hifld"
    batch_size = 1_000
    row_schema = LocationRow

    def __init__(
        self,
        *,
        parquet_file: Path | None = None,
        org_type_override: str | None = None,
    ):
        self._parquet_file = parquet_file
        self._org_type_override = org_type_override

    def _discover_files(self) -> list[Path]:
        if self._parquet_file is not None:
            if not self._parquet_file.exists():
                raise FileNotFoundError(f"File not found: {self._parquet_file}")
            return [self._parquet_file]
        if not CACHE_DIR.exists():
            raise FileNotFoundError(f"HIFLD cache dir not found: {CACHE_DIR}")
        files = sorted(CACHE_DIR.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"No parquet files in {CACHE_DIR}")
        return files

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        for parquet_file in self._discover_files():
            df = _read_parquet(parquet_file)
            df = normalize_field_names(df)
            if "geometry" in df.columns:
                df = df.drop(columns=["geometry"])
            dataset_name = parquet_file.stem
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                org_type = self._org_type_override or map_organization_type(dataset_name, row_dict)
                additional_info: dict[str, Any] = {}
                for k, v in row_dict.items():
                    if k in STANDARD_FIELDS:
                        continue
                    if pd.notna(v):
                        if isinstance(v, pd.Timestamp):
                            additional_info[k] = str(v)
                        else:
                            additional_info[k] = v
                source_id = _truncate(row_dict.get("source_id"), 100) or ""
                yield {
                    "source": self.source,
                    "source_version": dataset_name,
                    "natural_key": f"{dataset_name}:{source_id}",
                    "source_id": source_id or None,
                    "name": _truncate(row_dict.get("name"), 500),
                    "organization_type": org_type,
                    "address": _truncate(row_dict.get("address"), 500),
                    "city": _truncate(row_dict.get("city"), 200),
                    "state": _truncate(row_dict.get("state"), 2),
                    "zip": _truncate(row_dict.get("zip"), 10),
                    "county": _truncate(row_dict.get("county"), 200),
                    "latitude": _opt_float(row_dict.get("latitude")),
                    "longitude": _opt_float(row_dict.get("longitude")),
                    "telephone": _truncate(row_dict.get("telephone"), 50),
                    "website": _truncate(row_dict.get("website"), 500),
                    "source_dataset": dataset_name,
                    "additional_info": additional_info or None,
                }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[LocationRow],
        ctx: PipelineContext,
    ) -> None:
        params = []
        for r in rows:
            d = r.model_dump(by_alias=True)
            d["additional_info"] = (
                json.dumps(d["additional_info"]) if d.get("additional_info") else None
            )
            # RawRow base fields are not part of the INSERT; drop them
            for k in ("source", "source_version", "natural_key", "ingested_at"):
                d.pop(k, None)
            params.append(d)
        await session.execute(_INSERT_SQL, params)


async def _prepare_target() -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load HIFLD infrastructure parquet datasets to bronze.bronze_locations"
    )
    parser.add_argument("--file", type=Path, help="Specific parquet file (default: all in cache)")
    parser.add_argument("--org-type", type=str, help="Override organization type for all rows")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target()
    pipeline = HifldLocationsPipeline(
        parquet_file=args.file, org_type_override=args.org_type
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""NCES CCD school-district pipeline: load cached CSVs into bronze tables.

Ported from load_nces_school_districts_to_bronze.py to the core_lib
DataSourcePipeline contract.

Data source: National Center for Education Statistics (NCES) Common Core of
Data (CCD), Local Education Agency (School District) Universe Survey,
https://nces.ed.gov/ccd/. Cached CSVs are produced by
scripts/datasources/nces/download_nces.py into data/cache/nces/:
    nces_directory.csv, nces_membership.csv, nces_staff.csv

Three bronze tables are populated from the single validated row stream
(routed per-record by the ``dataset`` discriminator), upserted/incremental
by their primary keys:
    bronze.bronze_jurisdictions_school_districts_nces_directory   PK(nces_id)
    bronze.bronze_jurisdictions_school_districts_nces_membership  PK(nces_id, school_year)
    bronze.bronze_jurisdictions_school_districts_nces_staff       PK(nces_id, school_year, staff_category)

Incremental modes:
    * Default loads all states present in the files (full upsert).
    * --states AL,TX limits upserts to those USPS codes (only touched rows change).

Usage:
    python -m scripts.datasources.nces.school_districts
    python scripts/datasources/nces/school_districts.py --states TX,CA
    python scripts/datasources/nces/school_districts.py --datasets directory

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 localhost:5433 / open_navigator credentials).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


CACHE_DIR = Path("data/cache/nces")

DATASETS = ("directory", "membership", "staff")

T_DIRECTORY = "bronze.bronze_jurisdictions_school_districts_nces_directory"
T_MEMBERSHIP = "bronze.bronze_jurisdictions_school_districts_nces_membership"
T_STAFF = "bronze.bronze_jurisdictions_school_districts_nces_staff"


# ---------------------------------------------------------------------------
# Pure helpers (preserved verbatim from the legacy loader).
# ---------------------------------------------------------------------------
def _scalar(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if hasattr(val, "item"):
        try:
            return val.item()
        except Exception:
            pass
    if pd.isna(val):
        return None
    return val


def _str_cell(val: Any, maxlen: int | None = None) -> str | None:
    v = _scalar(val)
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    return s[:maxlen] if maxlen else s


def _int_cell(val: Any) -> int | None:
    v = _scalar(val)
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


def _float_cell(val: Any) -> float | None:
    v = _scalar(val)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sanitize_for_jsonb(o: Any) -> Any:
    """Make values JSON/PostgreSQL-safe (no bare NaN tokens)."""
    if o is None:
        return None
    if isinstance(o, dict):
        return {str(k): _sanitize_for_jsonb(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize_for_jsonb(v) for v in o]
    if isinstance(o, (datetime, date)):
        try:
            return o.isoformat()
        except Exception:
            return str(o)
    try:
        import numpy as np

        if isinstance(o, np.generic):
            if isinstance(o, np.floating):
                x = float(o)
                if math.isnan(x) or math.isinf(x):
                    return None
                return x
            return _sanitize_for_jsonb(o.item())
    except ImportError:
        pass
    try:
        if pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if hasattr(o, "item"):
        try:
            inner = o.item()
            return _sanitize_for_jsonb(inner)
        except Exception:
            pass
    return o


def _record_to_jsonb(rec: dict[str, Any]) -> str:
    safe = _sanitize_for_jsonb(rec)

    def _json_default(obj: Any) -> Any:
        if hasattr(obj, "isoformat"):
            try:
                return obj.isoformat()
            except Exception:
                pass
        if hasattr(obj, "item"):
            try:
                return _sanitize_for_jsonb(obj.item())
            except Exception:
                pass
        return str(obj)

    return json.dumps(safe, ensure_ascii=False, allow_nan=False, default=_json_default)


def filter_by_states(df: pd.DataFrame, state_col: str, codes: list[str] | None) -> pd.DataFrame:
    if not codes:
        return df
    want = {c.strip().upper() for c in codes}
    if state_col not in df.columns:
        return df
    return df[df[state_col].astype(str).str.upper().isin(want)]


def directory_rows(df: pd.DataFrame, school_year: str) -> list[tuple]:
    rows: list[tuple] = []
    records = df.to_dict(orient="records")
    for rec in records:
        nid = _str_cell(rec.get("nces_id"), 20)
        if not nid:
            continue
        raw = _record_to_jsonb(rec)
        rows.append(
            (
                nid,
                _str_cell(rec.get("district_name"), 512),
                _str_cell(rec.get("state"), 2) or "",
                _str_cell(rec.get("state_fips"), 5),
                _str_cell(rec.get("street_address"), 512),
                _str_cell(rec.get("city"), 255),
                _str_cell(rec.get("zip"), 20),
                _str_cell(rec.get("phone"), 80),
                _str_cell(rec.get("website"), 2048),
                _str_cell(rec.get("district_type"), 255),
                _int_cell(rec.get("num_schools")),
                school_year,
                raw,
            )
        )
    return rows


def membership_rows(df: pd.DataFrame, school_year: str) -> list[tuple]:
    rows: list[tuple] = []
    for rec in df.to_dict(orient="records"):
        nid = _str_cell(rec.get("nces_id"), 20)
        if not nid:
            continue
        st = _str_cell(rec.get("state"), 2) or ""
        rows.append(
            (
                nid,
                st,
                _str_cell(rec.get("state_fips"), 5),
                _int_cell(rec.get("total_students")),
                school_year,
            )
        )
    return rows


def staff_rows(df: pd.DataFrame, school_year: str) -> list[tuple]:
    df = df.copy()
    df["staff_category"] = df["staff_category"].astype(str).str.strip()
    df = (
        df.groupby(["nces_id", "state", "state_fips", "staff_category"], as_index=False)["staff_count"]
        .sum()
    )
    rows: list[tuple] = []
    for rec in df.to_dict(orient="records"):
        nid = _str_cell(rec.get("nces_id"), 20)
        cat = _str_cell(rec.get("staff_category"), None)
        if not nid or not cat:
            continue
        rows.append(
            (
                nid,
                _str_cell(rec.get("state"), 2) or "",
                _str_cell(rec.get("state_fips"), 5),
                cat,
                _float_cell(rec.get("staff_count")),
                school_year,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Cache-file discovery.
# ---------------------------------------------------------------------------
def find_nces_files(cache_dir: Path, datasets: set[str]) -> dict[str, Path]:
    """Resolve the requested dataset CSV paths, raising if any are missing."""
    paths = {
        "directory": cache_dir / "nces_directory.csv",
        "membership": cache_dir / "nces_membership.csv",
        "staff": cache_dir / "nces_staff.csv",
    }
    wanted = {k: p for k, p in paths.items() if k in datasets}
    for key, p in wanted.items():
        if not p.is_file():
            raise FileNotFoundError(
                f"Missing cache file {p}. "
                "Run scripts/datasources/nces/download_nces.py first."
            )
    return wanted


# ---------------------------------------------------------------------------
# Row schema (union across the three datasets; routed by ``dataset``).
# ---------------------------------------------------------------------------
class NcesSchoolDistrictRow(RawRow):
    """One NCES CCD record (directory / membership / staff), validated before upsert."""

    dataset: str = Field(min_length=1, max_length=16)
    nces_id: str = Field(min_length=1, max_length=20)
    state_code: str = Field(max_length=2)
    state_fips: str | None = Field(default=None, max_length=5)
    school_year: str = Field(min_length=1, max_length=16)

    # directory-only columns
    district_name: str | None = Field(default=None, max_length=512)
    street_address: str | None = Field(default=None, max_length=512)
    city: str | None = Field(default=None, max_length=255)
    zip: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=2048)
    district_type: str | None = Field(default=None, max_length=255)
    num_schools: int | None = None
    raw_json: str | None = None

    # membership-only column
    total_students: int | None = None

    # staff-only columns
    staff_category: str | None = None
    staff_count: float | None = None


# ---------------------------------------------------------------------------
# DDL — separate statements (one execute each), preserved from the loader.
# ---------------------------------------------------------------------------
_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_DIRECTORY_TABLE_SQL = text(
    f"""
CREATE TABLE IF NOT EXISTS {T_DIRECTORY} (
    nces_id           VARCHAR(20) NOT NULL,
    district_name     VARCHAR(512),
    state_code        VARCHAR(2) NOT NULL,
    state_fips        VARCHAR(5),
    street_address    VARCHAR(512),
    city              VARCHAR(255),
    zip               VARCHAR(20),
    phone             VARCHAR(80),
    website           VARCHAR(2048),
    district_type     VARCHAR(255),
    num_schools       INTEGER,
    school_year       VARCHAR(16) NOT NULL,
    raw_json          JSONB,
    ingestion_date    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (nces_id)
)
"""
)

_CREATE_MEMBERSHIP_TABLE_SQL = text(
    f"""
CREATE TABLE IF NOT EXISTS {T_MEMBERSHIP} (
    nces_id           VARCHAR(20) NOT NULL,
    state_code        VARCHAR(2) NOT NULL,
    state_fips        VARCHAR(5),
    total_students    BIGINT,
    school_year       VARCHAR(16) NOT NULL,
    ingestion_date    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (nces_id, school_year)
)
"""
)

_CREATE_STAFF_TABLE_SQL = text(
    f"""
CREATE TABLE IF NOT EXISTS {T_STAFF} (
    nces_id           VARCHAR(20) NOT NULL,
    state_code        VARCHAR(2) NOT NULL,
    state_fips        VARCHAR(5),
    staff_category    TEXT NOT NULL,
    staff_count       DOUBLE PRECISION,
    school_year       VARCHAR(16) NOT NULL,
    ingestion_date    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (nces_id, school_year, staff_category)
)
"""
)

_CREATE_INDEXES_SQL = (
    text(f"CREATE INDEX IF NOT EXISTS idx_bjsdn_dir_state ON {T_DIRECTORY}(state_code)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_bjsdn_dir_year ON {T_DIRECTORY}(school_year)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_bjsdn_mem_state ON {T_MEMBERSHIP}(state_code)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_bjsdn_stf_state ON {T_STAFF}(state_code)"),
)

_TRUNCATE_DIRECTORY_SQL = text(f"TRUNCATE TABLE {T_DIRECTORY}")
_TRUNCATE_MEMBERSHIP_SQL = text(f"TRUNCATE TABLE {T_MEMBERSHIP}")
_TRUNCATE_STAFF_SQL = text(f"TRUNCATE TABLE {T_STAFF}")

_UPSERT_DIRECTORY_SQL = text(
    f"""
INSERT INTO {T_DIRECTORY}
    (nces_id, district_name, state_code, state_fips, street_address, city, zip,
     phone, website, district_type, num_schools, school_year, raw_json)
VALUES (:nces_id, :district_name, :state_code, :state_fips, :street_address, :city, :zip,
        :phone, :website, :district_type, :num_schools, :school_year, CAST(:raw_json AS jsonb))
ON CONFLICT (nces_id) DO UPDATE SET
    district_name     = EXCLUDED.district_name,
    state_code        = EXCLUDED.state_code,
    state_fips        = EXCLUDED.state_fips,
    street_address    = EXCLUDED.street_address,
    city              = EXCLUDED.city,
    zip               = EXCLUDED.zip,
    phone             = EXCLUDED.phone,
    website           = EXCLUDED.website,
    district_type     = EXCLUDED.district_type,
    num_schools       = EXCLUDED.num_schools,
    school_year       = EXCLUDED.school_year,
    raw_json          = EXCLUDED.raw_json,
    ingestion_date    = NOW()
"""
)

_UPSERT_MEMBERSHIP_SQL = text(
    f"""
INSERT INTO {T_MEMBERSHIP}
    (nces_id, state_code, state_fips, total_students, school_year)
VALUES (:nces_id, :state_code, :state_fips, :total_students, :school_year)
ON CONFLICT (nces_id, school_year) DO UPDATE SET
    state_code        = EXCLUDED.state_code,
    state_fips        = EXCLUDED.state_fips,
    total_students    = EXCLUDED.total_students,
    ingestion_date    = NOW()
"""
)

_UPSERT_STAFF_SQL = text(
    f"""
INSERT INTO {T_STAFF}
    (nces_id, state_code, state_fips, staff_category, staff_count, school_year)
VALUES (:nces_id, :state_code, :state_fips, :staff_category, :staff_count, :school_year)
ON CONFLICT (nces_id, school_year, staff_category) DO UPDATE SET
    state_code        = EXCLUDED.state_code,
    state_fips        = EXCLUDED.state_fips,
    staff_count       = EXCLUDED.staff_count,
    ingestion_date    = NOW()
"""
)


class NcesSchoolDistrictsPipeline(DataSourcePipeline[NcesSchoolDistrictRow]):
    source = "nces_school_districts"
    batch_size = 2_000
    row_schema = NcesSchoolDistrictRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        states: list[str] | None = None,
        datasets: set[str] | None = None,
        school_year: str | None = None,
        limit: int | None = None,
    ):
        self._cache_dir = path or CACHE_DIR
        self._states = states
        self._datasets = datasets or set(DATASETS)
        self._school_year = school_year
        self._limit = limit

    def _resolve_school_year(self) -> str:
        if self._school_year:
            return self._school_year
        from scripts.datasources.nces.download_nces import NCESSchoolDistrictIngestion

        meta = NCESSchoolDistrictIngestion().get_nces_files()
        return meta.get("school_year") or "2024-25"

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        from scripts.datasources.nces.download_nces import NCESSchoolDistrictIngestion

        ingestion = NCESSchoolDistrictIngestion()
        paths = find_nces_files(self._cache_dir, self._datasets)
        school_year = self._resolve_school_year()
        emitted = 0

        if "directory" in self._datasets:
            ddir = ingestion.parse_csv_to_dataframe(paths["directory"])
            ddir = filter_by_states(ddir, "state", self._states)
            for (
                nces_id, district_name, state_code, state_fips, street_address, city, zip_code,
                phone, website, district_type, num_schools, sy, raw_json,
            ) in directory_rows(ddir, school_year):
                if self._limit is not None and emitted >= self._limit:
                    return
                yield {
                    "source": self.source,
                    "source_version": school_year,
                    "natural_key": f"directory:{nces_id}",
                    "dataset": "directory",
                    "nces_id": nces_id,
                    "state_code": state_code,
                    "state_fips": state_fips,
                    "school_year": sy,
                    "district_name": district_name,
                    "street_address": street_address,
                    "city": city,
                    "zip": zip_code,
                    "phone": phone,
                    "website": website,
                    "district_type": district_type,
                    "num_schools": num_schools,
                    "raw_json": raw_json,
                }
                emitted += 1

        if "membership" in self._datasets:
            mdf = ingestion.parse_membership_csv(paths["membership"])
            mdf = filter_by_states(mdf, "state", self._states)
            for nces_id, state_code, state_fips, total_students, sy in membership_rows(
                mdf, school_year
            ):
                if self._limit is not None and emitted >= self._limit:
                    return
                yield {
                    "source": self.source,
                    "source_version": school_year,
                    "natural_key": f"membership:{nces_id}:{sy}",
                    "dataset": "membership",
                    "nces_id": nces_id,
                    "state_code": state_code,
                    "state_fips": state_fips,
                    "school_year": sy,
                    "total_students": total_students,
                }
                emitted += 1

        if "staff" in self._datasets:
            sdf = ingestion.parse_staff_csv(paths["staff"])
            sdf = filter_by_states(sdf, "state", self._states)
            for nces_id, state_code, state_fips, staff_category, staff_count, sy in staff_rows(
                sdf, school_year
            ):
                if self._limit is not None and emitted >= self._limit:
                    return
                yield {
                    "source": self.source,
                    "source_version": school_year,
                    "natural_key": f"staff:{nces_id}:{sy}:{staff_category}",
                    "dataset": "staff",
                    "nces_id": nces_id,
                    "state_code": state_code,
                    "state_fips": state_fips,
                    "school_year": sy,
                    "staff_category": staff_category,
                    "staff_count": staff_count,
                }
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[NcesSchoolDistrictRow],
        ctx: PipelineContext,
    ) -> None:
        directory_params: list[dict] = []
        membership_params: list[dict] = []
        staff_params: list[dict] = []
        for r in rows:
            if r.dataset == "directory":
                directory_params.append(
                    {
                        "nces_id": r.nces_id,
                        "district_name": r.district_name,
                        "state_code": r.state_code,
                        "state_fips": r.state_fips,
                        "street_address": r.street_address,
                        "city": r.city,
                        "zip": r.zip,
                        "phone": r.phone,
                        "website": r.website,
                        "district_type": r.district_type,
                        "num_schools": r.num_schools,
                        "school_year": r.school_year,
                        "raw_json": r.raw_json,
                    }
                )
            elif r.dataset == "membership":
                membership_params.append(
                    {
                        "nces_id": r.nces_id,
                        "state_code": r.state_code,
                        "state_fips": r.state_fips,
                        "total_students": r.total_students,
                        "school_year": r.school_year,
                    }
                )
            elif r.dataset == "staff":
                staff_params.append(
                    {
                        "nces_id": r.nces_id,
                        "state_code": r.state_code,
                        "state_fips": r.state_fips,
                        "staff_category": r.staff_category,
                        "staff_count": r.staff_count,
                        "school_year": r.school_year,
                    }
                )

        if directory_params:
            await session.execute(_UPSERT_DIRECTORY_SQL, directory_params)
        if membership_params:
            await session.execute(_UPSERT_MEMBERSHIP_SQL, membership_params)
        if staff_params:
            await session.execute(_UPSERT_STAFF_SQL, staff_params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_DIRECTORY_TABLE_SQL)
        await session.execute(_CREATE_MEMBERSHIP_TABLE_SQL)
        await session.execute(_CREATE_STAFF_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_DIRECTORY_SQL)
            await session.execute(_TRUNCATE_MEMBERSHIP_SQL)
            await session.execute(_TRUNCATE_STAFF_SQL)


def _parse_datasets(raw: str) -> set[str]:
    ds_raw = {s.strip().lower() for s in raw.split(",")}
    if "all" in ds_raw:
        return set(DATASETS)
    datasets = ds_raw & set(DATASETS)
    if not datasets:
        logger.error("No valid datasets in --datasets")
        sys.exit(1)
    return datasets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load NCES school district CSV cache into "
        "bronze_jurisdictions_school_districts_nces_* tables"
    )
    parser.add_argument(
        "--states",
        type=str,
        help="Comma-separated USPS codes (only those rows are upserted). Omit for all states.",
    )
    parser.add_argument(
        "--school-year",
        type=str,
        default=None,
        help="CCD school year label for PK scope (default: from download_nces manifest, e.g. 2024-25).",
    )
    parser.add_argument(
        "--datasets",
        type=str,
        default="all",
        help="Comma-separated: directory, membership, staff, or all (default all).",
    )
    parser.add_argument("--limit", type=int, help="Load only the first N data rows")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE tables before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    states = (
        [s.strip().upper() for s in args.states.split(",")] if args.states else None
    )
    datasets = _parse_datasets(args.datasets)
    pipeline = NcesSchoolDistrictsPipeline(
        states=states,
        datasets=datasets,
        school_year=args.school_year,
        limit=args.limit,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Load NCES CCD school-district CSVs from ``data/cache/nces/`` into bronze tables.

Expects cache files produced by ``download_nces.py``:
    ``nces_directory.csv``, ``nces_membership.csv``, ``nces_staff.csv``

Tables (bronze schema, upsert / incremental by primary keys):

    bronze.bronze_jurisdictions_school_districts_nces_directory
    bronze.bronze_jurisdictions_school_districts_nces_membership
    bronze.bronze_jurisdictions_school_districts_nces_staff

Incremental modes:

    * Default loads **all** states present in the files (full upsert).
    * ``--states AL,TX`` limits upserts to those USPS codes (only touched rows change).

Database URL: ``OPEN_NAVIGATOR_DATABASE_URL`` / ``NEON_DATABASE_URL_DEV`` /
``NEON_DATABASE_URL`` — see ``scripts/database/target_database_url.py``.

Usage:
    ./.venv/bin/python scripts/datasources/nces/load_nces_school_districts_to_bronze.py
    ./.venv/bin/python scripts/datasources/nces/load_nces_school_districts_to_bronze.py --states TX,CA
    ./.venv/bin/python scripts/datasources/nces/load_nces_school_districts_to_bronze.py --datasets directory
    ./.venv/bin/python scripts/datasources/nces/load_nces_school_districts_to_bronze.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VENV_REEXEC = "_OPEN_NAVIGATOR_NCES_BRONZE_VENV_REEXEC"


def _in_project_venv() -> bool:
    px = Path(sys.prefix).resolve()
    return px in {(_ROOT / ".venv").resolve(), (_ROOT / ".venv-dbt").resolve()}


def _maybe_reexec_with_project_venv() -> None:
    if os.environ.get(_VENV_REEXEC) == "1":
        return
    if _in_project_venv():
        return
    for name in (".venv", ".venv-dbt"):
        vpy = _ROOT / name / "bin" / "python"
        if vpy.is_file():
            os.environ[_VENV_REEXEC] = "1"
            os.execv(str(vpy), [str(vpy)] + sys.argv)


try:
    import pandas as pd
    import psycopg2
    from psycopg2.extras import execute_batch
    from dotenv import load_dotenv
    from loguru import logger
except ImportError:
    _maybe_reexec_with_project_venv()
    print(
        "Need pandas, psycopg2-binary, python-dotenv, loguru. "
        "cd repo root && ./.venv/bin/pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")
load_dotenv()

from scripts.database.target_database_url import resolve_target_database_url
from scripts.datasources.nces.download_nces import NCESSchoolDistrictIngestion

DATABASE_URL = resolve_target_database_url()

CACHE_DIR = Path("data/cache/nces")

T_DIRECTORY = "bronze.bronze_jurisdictions_school_districts_nces_directory"
T_MEMBERSHIP = "bronze.bronze_jurisdictions_school_districts_nces_membership"
T_STAFF = "bronze.bronze_jurisdictions_school_districts_nces_staff"

def ddl_statements() -> list[str]:
    """Separate DDL statements for psycopg2 (one execute each)."""
    return [
        "CREATE SCHEMA IF NOT EXISTS bronze",
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
""",
        f"CREATE INDEX IF NOT EXISTS idx_bjsdn_dir_state ON {T_DIRECTORY}(state_code)",
        f"CREATE INDEX IF NOT EXISTS idx_bjsdn_dir_year ON {T_DIRECTORY}(school_year)",
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
""",
        f"CREATE INDEX IF NOT EXISTS idx_bjsdn_mem_state ON {T_MEMBERSHIP}(state_code)",
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
""",
        f"CREATE INDEX IF NOT EXISTS idx_bjsdn_stf_state ON {T_STAFF}(state_code)",
    ]

UPSERT_DIRECTORY = f"""
INSERT INTO {T_DIRECTORY}
    (nces_id, district_name, state_code, state_fips, street_address, city, zip,
     phone, website, district_type, num_schools, school_year, raw_json)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
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

UPSERT_MEMBERSHIP = f"""
INSERT INTO {T_MEMBERSHIP}
    (nces_id, state_code, state_fips, total_students, school_year)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (nces_id, school_year) DO UPDATE SET
    state_code        = EXCLUDED.state_code,
    state_fips        = EXCLUDED.state_fips,
    total_students    = EXCLUDED.total_students,
    ingestion_date    = NOW()
"""

UPSERT_STAFF = f"""
INSERT INTO {T_STAFF}
    (nces_id, state_code, state_fips, staff_category, staff_count, school_year)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (nces_id, school_year, staff_category) DO UPDATE SET
    state_code        = EXCLUDED.state_code,
    state_fips        = EXCLUDED.state_fips,
    staff_count       = EXCLUDED.staff_count,
    ingestion_date    = NOW()
"""


def _database_url_source_label() -> str:
    if (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip():
        return "OPEN_NAVIGATOR_DATABASE_URL"
    if (os.getenv("NEON_DATABASE_URL_DEV") or "").strip():
        return "NEON_DATABASE_URL_DEV"
    if (os.getenv("NEON_DATABASE_URL") or "").strip():
        return "NEON_DATABASE_URL"
    return "default local (localhost:5433/open_navigator)"


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


def load_to_postgres(
    *,
    states: list[str] | None,
    datasets: set[str],
    school_year: str,
    dry_run: bool,
) -> dict[str, int]:
    ingestion = NCESSchoolDistrictIngestion()
    paths = {
        "directory": CACHE_DIR / "nces_directory.csv",
        "membership": CACHE_DIR / "nces_membership.csv",
        "staff": CACHE_DIR / "nces_staff.csv",
    }
    for key, p in paths.items():
        if key in datasets and not p.is_file():
            logger.error(f"Missing cache file {p}. Run scripts/datasources/nces/download_nces.py first.")
            sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()
    for stmt in ddl_statements():
        cur.execute(stmt.strip())
    conn.commit()

    stats: dict[str, int] = {}

    if "directory" in datasets:
        ddir = ingestion.parse_csv_to_dataframe(paths["directory"])
        ddir = filter_by_states(ddir, "state", states)
        batch = directory_rows(ddir, school_year)
        stats["directory_rows"] = len(batch)
        if dry_run:
            logger.info(f"DRY RUN — would upsert {len(batch):,} directory rows")
        else:
            execute_batch(cur, UPSERT_DIRECTORY, batch, page_size=2000)
            conn.commit()
            logger.success(f"Upserted {len(batch):,} rows → {T_DIRECTORY}")

    if "membership" in datasets:
        mdf = ingestion.parse_membership_csv(paths["membership"])
        mdf = filter_by_states(mdf, "state", states)
        batch = membership_rows(mdf, school_year)
        stats["membership_rows"] = len(batch)
        if dry_run:
            logger.info(f"DRY RUN — would upsert {len(batch):,} membership rows")
        else:
            execute_batch(cur, UPSERT_MEMBERSHIP, batch, page_size=2000)
            conn.commit()
            logger.success(f"Upserted {len(batch):,} rows → {T_MEMBERSHIP}")

    if "staff" in datasets:
        sdf = ingestion.parse_staff_csv(paths["staff"])
        sdf = filter_by_states(sdf, "state", states)
        batch = staff_rows(sdf, school_year)
        stats["staff_rows"] = len(batch)
        if dry_run:
            logger.info(f"DRY RUN — would upsert {len(batch):,} staff rows")
        else:
            execute_batch(cur, UPSERT_STAFF, batch, page_size=2000)
            conn.commit()
            logger.success(f"Upserted {len(batch):,} rows → {T_STAFF}")

    cur.close()
    conn.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load NCES school district CSV cache into bronze_jurisdictions_school_districts_nces_* tables"
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state_filter = [s.strip().upper() for s in args.states.split(",")] if args.states else None

    ds_raw = {s.strip().lower() for s in args.datasets.split(",")}
    if "all" in ds_raw:
        datasets = {"directory", "membership", "staff"}
    else:
        allowed = {"directory", "membership", "staff"}
        datasets = ds_raw & allowed
        if not datasets:
            logger.error("No valid datasets in --datasets")
            sys.exit(1)

    ingestion_meta = NCESSchoolDistrictIngestion().get_nces_files()
    school_year = args.school_year or ingestion_meta.get("school_year") or "2024-25"

    logger.info("=" * 70)
    logger.info("NCES cache → bronze_jurisdictions_school_districts_nces_*")
    logger.info("=" * 70)
    logger.info(f"Database: {_database_url_source_label()} → {DATABASE_URL.split('@')[-1]}")
    logger.info(f"School year key: {school_year}")
    logger.info(f"Datasets: {', '.join(sorted(datasets))}")
    logger.info(f"State filter: {state_filter or 'ALL'}")

    stats = load_to_postgres(
        states=state_filter,
        datasets=datasets,
        school_year=school_year,
        dry_run=args.dry_run,
    )
    logger.info("Summary:")
    for k, v in stats.items():
        logger.info(f"  {k}: {v:,}")
    logger.success("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Load OSF replication `.rds` into schema `bronze` with table names `bronze_osf_<stem>` (one table per file).
Load `.csv` only when no same-basename `.rds` exists (matches load_osf_rds_to_bronze.R).

Does not require R — uses `pyreadr` to read RDS files.

Env (same as other bronze loaders):
  POSTGRES_PASSWORD (default: password)
  PGHOST, PGPORT, PGDATABASE, PGUSER

Usage:
  python3 scripts/datasources/osf/load_osf_rds_to_bronze.py
  python3 scripts/datasources/osf/load_osf_rds_to_bronze.py --data-dir data/cache/osf/osf/Replication
  python3 scripts/datasources/osf/load_osf_rds_to_bronze.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger

try:
    import pandas as pd
    import pyreadr
    from sqlalchemy import create_engine, text
except ImportError as e:
    print(
        "Missing dependency. Install with:\n"
        "  pip install pandas pyreadr sqlalchemy psycopg2-binary\n"
        f"Original error: {e}",
        file=sys.stderr,
    )
    sys.exit(1)

DEFAULT_DATA_DIR = Path("data/cache/osf/osf/Replication")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = os.getenv("PGPORT", "5433")
PGDATABASE = os.getenv("PGDATABASE", "open_navigator")
PGUSER = os.getenv("PGUSER", "postgres")


# postgres max identifier 63; prefix "bronze_osf_" is 11 chars → suffix max 52
_BRONZE_OSF_PREFIX = "bronze_osf_"
_SUFFIX_MAX = 63 - len(_BRONZE_OSF_PREFIX)


def bronze_osf_table_name(stem: str) -> str:
    """Table name in schema `bronze`, e.g. bronze_osf_ledb_candidatelevel."""
    suf = stem.lower()
    suf = re.sub(r"[^a-z0-9_]+", "_", suf)
    suf = re.sub(r"_+", "_", suf).strip("_")
    if not suf:
        suf = "unnamed_table"
    suf = suf[:_SUFFIX_MAX]
    return f"{_BRONZE_OSF_PREFIX}{suf}"


def list_rds(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() == ".rds"
    )


def list_csv(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.csv") if p.is_file())


def basename_stem(path: Path) -> str:
    return path.stem


def read_csv_flexible(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return pd.read_csv(path, dtype=object, low_memory=False, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=object, low_memory=False, encoding_errors="replace")


def read_rds_via_rscript(path: Path) -> pd.DataFrame:
    """Fallback when pyreadr fails on non-UTF8 R strings (requires `Rscript` on PATH)."""
    rscript = shutil.which("Rscript")
    if not rscript:
        raise RuntimeError("Rscript not found; cannot decode this RDS without R.") from None

    fd, tmp_csv = tempfile.mkstemp(suffix=".csv", text=False)
    os.close(fd)
    try:
        ps = path.resolve().as_posix().replace("'", "\\'")
        ts = tmp_csv.replace("'", "\\'")
        code = (
            f'd <- readRDS("{ps}"); '
            f'write.csv(d, file="{ts}", row.names=FALSE, fileEncoding="UTF-8")'
        )
        subprocess.run([rscript, "-e", code], check=True, capture_output=True, text=True)
        return read_csv_flexible(Path(tmp_csv))
    finally:
        try:
            os.unlink(tmp_csv)
        except OSError:
            pass


def read_rds(path: Path) -> pd.DataFrame:
    try:
        result = pyreadr.read_r(str(path))
    except UnicodeDecodeError:
        logger.warning(f"pyreadr UTF-8 issue, trying Rscript fallback: {path.name}")
        return read_rds_via_rscript(path)
    except Exception as e:
        err = str(e).lower()
        if shutil.which("Rscript") and ("decode" in err or "codec" in err):
            logger.warning(f"pyreadr decode issue, trying Rscript fallback: {path.name}")
            return read_rds_via_rscript(path)
        raise

    if not result:
        raise ValueError(f"No objects in RDS: {path}")
    if len(result) > 1:
        logger.warning(f"RDS has {len(result)} objects; using first only: {path}")
    df = next(iter(result.values()))
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"RDS object is not a data frame: {path}")
    return df


def build_engine():
    # SQLAlchemy URL for psycopg2
    url = (
        f"postgresql+psycopg2://{PGUSER}:{POSTGRES_PASSWORD}"
        f"@{PGHOST}:{PGPORT}/{PGDATABASE}"
    )
    return create_engine(url)


def write_table(engine, table: str, df: pd.DataFrame, label: str, dry_run: bool) -> None:
    if dry_run:
        logger.info(f"[dry-run] would write {len(df)} rows -> bronze.{table} ({label})")
        return
    df.to_sql(table, engine, schema="bronze", if_exists="replace", index=False)
    logger.success(f"OK bronze.{table} ({len(df):,} rows) {label}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load OSF RDS/CSV into bronze.bronze_osf_* tables (no R required)"
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Replication folder")
    parser.add_argument("--dry-run", action="store_true", help="Do not connect or write")
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    if not data_dir.is_dir():
        logger.error(f"Data directory not found: {data_dir}")
        return 1

    rds_paths = list_rds(data_dir)
    if not rds_paths:
        logger.error(f"No .rds files under {data_dir}")
        return 1

    stems_rds = {basename_stem(p) for p in rds_paths}
    logger.info(f"Data dir: {data_dir}")

    engine = None if args.dry_run else build_engine()
    if engine is not None:
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze"))
            conn.commit()

    for p in rds_paths:
        stem = basename_stem(p)
        tbl = bronze_osf_table_name(stem)
        logger.info(f"RDS {p.name} -> {tbl}")
        try:
            df = read_rds(p)
        except (ValueError, TypeError, RuntimeError, subprocess.CalledProcessError) as e:
            logger.warning(f"Skip {p}: {e}")
            continue
        write_table(engine, tbl, df, p.name, args.dry_run)

    for p in list_csv(data_dir):
        stem = basename_stem(p)
        if stem in stems_rds:
            logger.info(f"CSV skip (RDS exists): {p.name}")
            continue
        tbl = bronze_osf_table_name(stem)
        logger.info(f"CSV {p.name} -> {tbl}")
        df = read_csv_flexible(p)
        write_table(engine, tbl, df, p.name, args.dry_run)

    logger.success("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

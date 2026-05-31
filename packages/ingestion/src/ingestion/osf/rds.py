#!/usr/bin/env python3
"""OSF replication RDS/CSV registry pipeline: load discovered OSF replication
files into bronze.bronze_osf_rds.

Ported from load_osf_rds_to_bronze.py to the core_lib DataSourcePipeline
contract.

The legacy loader read each OSF replication `.rds` (and `.csv` only when no
same-basename `.rds` exists, matching load_osf_rds_to_bronze.R) and wrote one
dynamically-shaped `bronze.bronze_osf_<stem>` table per file via pandas
`to_sql`. That per-file dynamic schema cannot be expressed as a single fixed
RawRow, so this pipeline preserves the discovery + table-naming + RDS reading
behavior and records a stable bronze *registry* of every replication file:
  - source file path (relative + absolute)
  - format (rds / csv)
  - target bronze table name (bronze_osf_<stem>)
  - row count (read via pyreadr / Rscript fallback / flexible CSV)

Downstream jobs use that registry to locate raw OSF replication artifacts and
their intended bronze table names.

Expected cache layout (created by download_osf_zip.py):
  data/cache/osf/osf/Replication

Usage:
    python -m ingestion.osf.rds
    python -m ingestion.osf.rds --data-dir data/cache/osf/osf/Replication
    python -m ingestion.osf.rds --truncate --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql+psycopg2://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd


def _import_pandas():
    """Import pandas lazily (needed to read CSV / shape RDS frames).

    Kept lazy so the pipeline/schema stay importable without the file-reading
    deps; the legacy loader exited at import time, here we defer the same hard
    failure to the moment a file is actually read.
    """
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover - dependency guard
        print(
            "Missing dependency. Install with:\n"
            "  pip install pandas pyreadr\n"
            f"Original error: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    return pd


def _import_pyreadr():
    """Import pyreadr lazily (needed only to decode RDS files)."""
    try:
        import pyreadr
    except ImportError as e:  # pragma: no cover - dependency guard
        print(
            "Missing dependency. Install with:\n"
            "  pip install pandas pyreadr\n"
            f"Original error: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    return pyreadr


# Default location of the extracted OSF replication cache.
CACHE_DIR = Path("data/cache/osf/osf/Replication")


# postgres max identifier 63; prefix "bronze_osf_" is 11 chars → suffix max 52
_BRONZE_OSF_PREFIX = "bronze_osf_"
_SUFFIX_MAX = 63 - len(_BRONZE_OSF_PREFIX)


# Explicit renames for specific OSF tables whose mechanical bronze_osf_<stem>
# name we override (e.g. to group person-level tables under bronze_persons_*).
# Keyed by the default generated name.
_TABLE_NAME_OVERRIDES = {
    "bronze_osf_ledb_candidatelevel": "bronze_persons_osf_ledb",
}


def bronze_osf_table_name(stem: str) -> str:
    """Table name in schema `bronze`, e.g. bronze_osf_ledb_candidatelevel.

    A few tables are renamed via ``_TABLE_NAME_OVERRIDES`` (e.g.
    ``bronze_osf_ledb_candidatelevel`` → ``bronze_persons_osf_ledb``).
    """
    suf = stem.lower()
    suf = re.sub(r"[^a-z0-9_]+", "_", suf)
    suf = re.sub(r"_+", "_", suf).strip("_")
    if not suf:
        suf = "unnamed_table"
    suf = suf[:_SUFFIX_MAX]
    default = f"{_BRONZE_OSF_PREFIX}{suf}"
    return _TABLE_NAME_OVERRIDES.get(default, default)


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
    pd = _import_pandas()
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
    pd = _import_pandas()
    pyreadr = _import_pyreadr()
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


def find_data_dir() -> Path:
    """Return the default OSF replication cache dir, raising if it is missing."""
    if not CACHE_DIR.is_dir():
        raise FileNotFoundError(
            f"Data directory not found: {CACHE_DIR}. "
            "Run scripts/datasources/osf/download_osf_zip.py first."
        )
    return CACHE_DIR


class OsfRdsRow(RawRow):
    """One discovered OSF replication file, validated before upsert."""

    rel_path: str = Field(min_length=1)
    abs_path: str = Field(min_length=1)
    file_format: str = Field(min_length=1, max_length=8)
    table_name: str = Field(min_length=1, max_length=63)
    row_count: int | None = Field(default=None, ge=0)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_osf_rds (
        rel_path            TEXT            PRIMARY KEY,
        abs_path            TEXT            NOT NULL,
        file_format         VARCHAR(8)      NOT NULL,
        table_name          VARCHAR(63)     NOT NULL,
        row_count           BIGINT,
        ingestion_date      TIMESTAMP       DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_osf_rds_table  ON bronze.bronze_osf_rds(table_name)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_osf_rds_format ON bronze.bronze_osf_rds(file_format)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_osf_rds")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_osf_rds
        (rel_path, abs_path, file_format, table_name, row_count)
    VALUES
        (:rel_path, :abs_path, :file_format, :table_name, :row_count)
    ON CONFLICT (rel_path) DO UPDATE SET
        abs_path       = EXCLUDED.abs_path,
        file_format    = EXCLUDED.file_format,
        table_name     = EXCLUDED.table_name,
        row_count      = EXCLUDED.row_count,
        ingestion_date = NOW()
    """
)


class OsfRdsPipeline(DataSourcePipeline[OsfRdsRow]):
    source = "osf_rds"
    batch_size = 1_000
    row_schema = OsfRdsRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        data_dir = (self._path or find_data_dir()).resolve()
        if not data_dir.is_dir():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

        rds_paths = list_rds(data_dir)
        if not rds_paths:
            raise FileNotFoundError(f"No .rds files under {data_dir}")

        stems_rds = {basename_stem(p) for p in rds_paths}
        emitted = 0

        for p in rds_paths:
            if self._limit is not None and emitted >= self._limit:
                return
            stem = basename_stem(p)
            tbl = bronze_osf_table_name(stem)
            try:
                df = read_rds(p)
            except (ValueError, TypeError, RuntimeError, subprocess.CalledProcessError) as e:
                logger.warning(f"Skip {p}: {e}")
                continue
            rel = str(p.relative_to(data_dir))
            yield {
                "source": self.source,
                "source_version": data_dir.name,
                "natural_key": rel,
                "rel_path": rel,
                "abs_path": str(p.resolve()),
                "file_format": "rds",
                "table_name": tbl,
                "row_count": int(len(df)),
            }
            emitted += 1

        # CSV only when no same-basename RDS exists (matches load_osf_rds_to_bronze.R).
        for p in list_csv(data_dir):
            if self._limit is not None and emitted >= self._limit:
                return
            stem = basename_stem(p)
            if stem in stems_rds:
                logger.info(f"CSV skip (RDS exists): {p.name}")
                continue
            tbl = bronze_osf_table_name(stem)
            df = read_csv_flexible(p)
            rel = str(p.relative_to(data_dir))
            yield {
                "source": self.source,
                "source_version": data_dir.name,
                "natural_key": rel,
                "rel_path": rel,
                "abs_path": str(p.resolve()),
                "file_format": "csv",
                "table_name": tbl,
                "row_count": int(len(df)),
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[OsfRdsRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "rel_path": r.rel_path,
                "abs_path": r.abs_path,
                "file_format": r.file_format,
                "table_name": r.table_name,
                "row_count": r.row_count,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load OSF RDS/CSV replication file registry into bronze.bronze_osf_rds (no R required)"
    )
    parser.add_argument(
        "--data-dir", type=Path,
        help=f"Replication folder (default: {CACHE_DIR})",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = OsfRdsPipeline(path=args.data_dir, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

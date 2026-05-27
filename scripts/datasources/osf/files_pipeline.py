#!/usr/bin/env python3
"""OSF cache file-registry pipeline: load extracted file metadata into
bronze.bronze_osf_files.

Ported from load_osf_to_bronze.py to the core_lib DataSourcePipeline contract.

This pipeline ingests *metadata* about the extracted OSF cache into Postgres.
It does NOT interpret the dataset schema (CSV/JSON/etc); it creates a stable
bronze registry of every file extracted from the ZIP:
  - relative path
  - absolute path
  - extension
  - size, modified time
  - sha256

That gives downstream jobs a consistent way to find the raw source artifacts.

Expected cache layout (created by download_osf_zip.py):
  data/cache/osf/osf/...

Usage:
    python -m scripts.datasources.osf.files_pipeline
    python scripts/datasources/osf/files_pipeline.py --extract-dir data/cache/osf/osf
    python scripts/datasources/osf/files_pipeline.py --truncate --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# Default location of the extracted OSF cache (created by download_osf_zip.py).
CACHE_DIR = Path("data/cache/osf/osf")


def find_extract_dir() -> Path:
    """Return the default extracted OSF cache dir, raising if it is missing."""
    if not CACHE_DIR.exists():
        raise FileNotFoundError(
            f"Extract dir not found: {CACHE_DIR}. "
            "Run scripts/datasources/osf/download_osf_zip.py first."
        )
    return CACHE_DIR


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_ext(p: Path) -> str | None:
    s = p.suffix.lower().lstrip(".")
    return s or None


class FileRow(RawRow):
    """One extracted OSF file's metadata, validated before upsert."""

    rel_path: str = Field(min_length=1)
    abs_path: str = Field(min_length=1)
    file_ext: str | None = None
    size_bytes: int = Field(ge=0)
    mtime_utc: datetime | None = None
    sha256: str = Field(min_length=64, max_length=64)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_osf_files (
        rel_path            TEXT            PRIMARY KEY,
        abs_path            TEXT            NOT NULL,
        file_ext            TEXT,
        size_bytes          BIGINT          NOT NULL,
        mtime_utc           TIMESTAMP,
        sha256              CHAR(64)        NOT NULL,
        ingestion_date      TIMESTAMP       DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_osf_files_sha256 ON bronze.bronze_osf_files(sha256)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_osf_files_ext    ON bronze.bronze_osf_files(file_ext)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_osf_files")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_osf_files
        (rel_path, abs_path, file_ext, size_bytes, mtime_utc, sha256)
    VALUES
        (:rel_path, :abs_path, :file_ext, :size_bytes, :mtime_utc, :sha256)
    ON CONFLICT (rel_path) DO UPDATE SET
        abs_path       = EXCLUDED.abs_path,
        file_ext       = EXCLUDED.file_ext,
        size_bytes     = EXCLUDED.size_bytes,
        mtime_utc      = EXCLUDED.mtime_utc,
        sha256         = EXCLUDED.sha256,
        ingestion_date = NOW()
    """
)


class OsfFilesPipeline(DataSourcePipeline[FileRow]):
    source = "osf_files"
    batch_size = 1_000
    row_schema = FileRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        extract_dir = self._path or find_extract_dir()
        if not extract_dir.exists():
            raise FileNotFoundError(
                f"Extract dir not found: {extract_dir}. "
                "Run scripts/datasources/osf/download_osf_zip.py first."
            )

        files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
        if not files:
            raise FileNotFoundError(f"No files found under {extract_dir}")

        emitted = 0
        for p in files:
            if self._limit is not None and emitted >= self._limit:
                return
            st = p.stat()
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(tzinfo=None)
            rel = str(p.relative_to(extract_dir))
            yield {
                "source": self.source,
                "source_version": extract_dir.name,
                "natural_key": rel,
                "rel_path": rel,
                "abs_path": str(p.resolve()),
                "file_ext": _file_ext(p),
                "size_bytes": int(st.st_size),
                "mtime_utc": mtime,
                "sha256": _sha256_file(p),
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[FileRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "rel_path": r.rel_path,
                "abs_path": r.abs_path,
                "file_ext": r.file_ext,
                "size_bytes": r.size_bytes,
                "mtime_utc": r.mtime_utc,
                "sha256": r.sha256,
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
        description="Load OSF extracted file metadata into bronze.bronze_osf_files"
    )
    parser.add_argument(
        "--extract-dir", type=Path,
        help=f"Extracted OSF directory (default: {CACHE_DIR})",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = OsfFilesPipeline(path=args.extract_dir, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

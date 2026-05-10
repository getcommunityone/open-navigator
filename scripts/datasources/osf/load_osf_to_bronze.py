#!/usr/bin/env python3
"""
OSF Cache → Bronze Loader (file registry)

This loader ingests *metadata* about the extracted OSF cache into Postgres:
  bronze.bronze_osf_files

It does NOT attempt to interpret the dataset schema (CSV/JSON/etc). Instead it
creates a stable bronze registry of all files extracted from the ZIP:
  - relative path
  - size, modified time
  - sha256

That gives downstream jobs a consistent way to find the raw source artifacts.

Expected cache layout (created by download_osf_zip.py):
  data/cache/osf/osf/...

Usage:
  python scripts/datasources/osf/load_osf_to_bronze.py
  python scripts/datasources/osf/load_osf_to_bronze.py --extract-dir data/cache/osf/osf
  python scripts/datasources/osf/load_osf_to_bronze.py --truncate
  python scripts/datasources/osf/load_osf_to_bronze.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from loguru import logger  # type: ignore
except Exception:  # pragma: no cover
    class _FallbackLogger:
        def info(self, msg: str) -> None:
            print(msg)

        def success(self, msg: str) -> None:
            print(msg)

        def warning(self, msg: str) -> None:
            print(msg)

        def error(self, msg: str) -> None:
            print(msg, file=sys.stderr)

    logger = _FallbackLogger()


def _get_psycopg2():
    """Import psycopg2 only when loading to Postgres (avoids import noise for dry-run)."""
    try:
        import psycopg2  # type: ignore
        from psycopg2.extras import execute_values  # type: ignore

        return psycopg2, execute_values
    except ModuleNotFoundError:
        return None, None


DEFAULT_EXTRACT_DIR = Path("data/cache/osf/osf")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"


CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_osf_files (
        rel_path            TEXT            PRIMARY KEY,
        abs_path            TEXT            NOT NULL,
        file_ext            TEXT,
        size_bytes          BIGINT          NOT NULL,
        mtime_utc           TIMESTAMP,
        sha256              CHAR(64)        NOT NULL,
        ingestion_date      TIMESTAMP       DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_bronze_osf_files_sha256 ON bronze.bronze_osf_files(sha256);
    CREATE INDEX IF NOT EXISTS idx_bronze_osf_files_ext    ON bronze.bronze_osf_files(file_ext);
"""


UPSERT_SQL = """
    INSERT INTO bronze.bronze_osf_files
        (rel_path, abs_path, file_ext, size_bytes, mtime_utc, sha256)
    VALUES %s
    ON CONFLICT (rel_path) DO UPDATE SET
        abs_path       = EXCLUDED.abs_path,
        file_ext       = EXCLUDED.file_ext,
        size_bytes     = EXCLUDED.size_bytes,
        mtime_utc      = EXCLUDED.mtime_utc,
        sha256         = EXCLUDED.sha256,
        ingestion_date = NOW()
"""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_ext(p: Path) -> str | None:
    s = p.suffix.lower().lstrip(".")
    return s or None


def index_files(extract_dir: Path) -> list[tuple]:
    if not extract_dir.exists():
        raise FileNotFoundError(
            f"Extract dir not found: {extract_dir}. "
            "Run scripts/datasources/osf/download_osf_zip.py first."
        )

    files = [p for p in extract_dir.rglob("*") if p.is_file()]
    if not files:
        raise FileNotFoundError(f"No files found under {extract_dir}")

    records: list[tuple] = []
    for p in sorted(files):
        rel = str(p.relative_to(extract_dir))
        st = p.stat()
        mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(tzinfo=None)
        records.append(
            (
                rel,
                str(p.resolve()),
                _file_ext(p),
                int(st.st_size),
                mtime,
                _sha256_file(p),
            )
        )
    return records


def load(records: list[tuple], truncate: bool, dry_run: bool) -> None:
    logger.info(f"Prepared {len(records):,} files for bronze registry")
    if dry_run:
        logger.info("[DRY RUN] Skipping DB writes")
        if records:
            logger.info(f"  Sample: {records[0]}")
        return

    psycopg2, execute_values = _get_psycopg2()
    if psycopg2 is None or execute_values is None:
        logger.error("psycopg2 is required to load into Postgres.")
        logger.error("Install it in the same environment you use for bronze loaders, e.g.:")
        logger.error("  ./.venv/bin/python -m pip install psycopg2-binary")
        logger.error("  ./.venv-dbt/bin/python -m pip install psycopg2-binary")
        logger.error("  python3 -m pip install --user psycopg2-binary")
        logger.error("Or: pip install -r requirements.txt (includes psycopg2-binary).")
        sys.exit(1)

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()

            if truncate:
                cur.execute("TRUNCATE TABLE bronze.bronze_osf_files")
                conn.commit()
                logger.warning("Truncated bronze.bronze_osf_files")

            execute_values(cur, UPSERT_SQL, records, page_size=1_000)
            conn.commit()
            logger.success(f"Upserted {len(records):,} rows into bronze.bronze_osf_files")

            cur.execute("SELECT COUNT(*) FROM bronze.bronze_osf_files")
            total = cur.fetchone()[0]
            logger.info(f"Table row count: {total:,}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Load OSF extracted file metadata into bronze")
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_DIR, help="Extracted OSF directory")
    parser.add_argument("--truncate", action="store_true", help="Truncate table before loading")
    parser.add_argument("--dry-run", action="store_true", help="Index only; no DB writes")
    args = parser.parse_args()

    extract_dir = args.extract_dir
    logger.info(f"Indexing extracted files under: {extract_dir}")
    records = index_files(extract_dir)
    load(records, truncate=args.truncate, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())


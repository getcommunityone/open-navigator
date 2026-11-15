"""Land Epoch AI's data center files in bronze (DC-4.1, #249).

    python -m ingestion.data_centers.epoch_sites                 # download + load
    python -m ingestion.data_centers.epoch_sites --no-download   # load what's cached
    python -m ingestion.data_centers.epoch_sites --file-dir DIR  # load files you saved

Source: Epoch AI, "AI data centers" (https://epoch.ai/data/data-centers), licensed
CC BY 4.0: free to use and republish with credit to Epoch AI. Every row keeps its
source URL so the mart and the page can credit it.

Each CSV row lands as raw JSONB with the file's SHA-256 and the download date, so
a re-run of the same file adds nothing and a newer file adds a new snapshot. dbt
does all the typing and shaping (``stg_epoch_data_center*``, ``data_center_site``);
keeping old snapshots is what lets a site that drops out of Epoch's list stay
visible as "no longer listed" instead of vanishing.

The loader checks the headers it relies on (``Name``; ``Data center`` and
``Date``) and stops with the headers it actually found if Epoch renames them,
rather than loading rows that would turn into nulls downstream.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from loguru import logger

CACHE_DIR = Path("data/cache/epoch")
BASE_URL = "https://epoch.ai/data/data_centers"


@dataclass(frozen=True)
class EpochFile:
    filename: str
    table: str
    key_header: str
    required: tuple[str, ...]

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.filename}"


DATA_CENTERS = EpochFile("data_centers.csv", "bronze_epoch_data_centers", "Name", ("Name",))
TIMELINES = EpochFile(
    "data_center_timelines.csv",
    "bronze_epoch_data_center_timelines",
    "Data center",
    ("Data center", "Date"),
)
FILES = (DATA_CENTERS, TIMELINES)


class HeaderMismatch(ValueError):
    """Epoch's file no longer has a header this loader relies on."""


def parse_csv(text: str, spec: EpochFile) -> list[dict[str, str]]:
    """Rows of one Epoch CSV as dicts; raises HeaderMismatch on a missing header."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [h for h in spec.required if h not in headers]
    if missing:
        raise HeaderMismatch(
            f"{spec.filename}: missing {missing}; found {headers}. "
            "Update ingestion.data_centers.epoch_sites and the staging models."
        )
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {(k or "").strip(): (v if v is not None else "") for k, v in raw.items()}
        if not (row.get(spec.key_header) or "").strip():
            continue  # blank trailing lines
        rows.append(row)
    return rows


def bronze_rows(
    rows: list[dict[str, str]], spec: EpochFile, *, file_sha256: str, snapshot_on: date
) -> list[tuple]:
    """Tuples for the bronze insert: (sha, row_number, snapshot_on, url, key, record_json)."""
    return [
        (
            file_sha256,
            i,
            snapshot_on,
            spec.url,
            row[spec.key_header].strip(),
            json.dumps(row, ensure_ascii=False),
        )
        for i, row in enumerate(rows, start=1)
    ]


def create_sql(spec: EpochFile) -> str:
    key_col = "name" if spec is DATA_CENTERS else "data_center"
    return f"""
        CREATE SCHEMA IF NOT EXISTS bronze;
        CREATE TABLE IF NOT EXISTS bronze.{spec.table} (
            file_sha256  text        NOT NULL,
            row_number   integer     NOT NULL,
            snapshot_on  date        NOT NULL,
            source_url   text        NOT NULL,
            {key_col}    text        NOT NULL,
            record       jsonb       NOT NULL,
            loaded_at    timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (file_sha256, row_number)
        );
        CREATE INDEX IF NOT EXISTS ix_{spec.table}_snapshot ON bronze.{spec.table} (snapshot_on);
    """


def insert_sql(spec: EpochFile) -> str:
    key_col = "name" if spec is DATA_CENTERS else "data_center"
    return (
        f"INSERT INTO bronze.{spec.table} "
        f"(file_sha256, row_number, snapshot_on, source_url, {key_col}, record) VALUES %s "
        "ON CONFLICT (file_sha256, row_number) DO NOTHING"
    )


def download(spec: EpochFile, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / spec.filename
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(spec.url)
        resp.raise_for_status()
    target.write_bytes(resp.content)
    logger.info("Downloaded {} ({:,} bytes)", spec.url, len(resp.content))
    return target


def _dsn() -> str | None:
    return next(
        (os.environ[k] for k in ("NEON_DATABASE_URL_DEV", "NEON_DATABASE_URL", "DATABASE_URL") if os.environ.get(k)),
        None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file-dir", type=Path, help="Load CSVs from here instead of downloading.")
    parser.add_argument("--no-download", action="store_true", help=f"Use the files in {CACHE_DIR}.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and check, but don't write.")
    args = parser.parse_args(argv)

    source_dir = args.file_dir or CACHE_DIR
    parsed: list[tuple[EpochFile, list[tuple]]] = []
    for spec in FILES:
        path = source_dir / spec.filename
        if args.file_dir is None and not args.no_download:
            path = download(spec, CACHE_DIR)
        if not path.exists():
            logger.error("{} not found (download it or pass --file-dir)", path)
            return 2
        data = path.read_bytes()
        try:
            rows = parse_csv(data.decode("utf-8"), spec)
        except HeaderMismatch as e:
            logger.error(str(e))
            return 3
        sha = hashlib.sha256(data).hexdigest()
        parsed.append((spec, bronze_rows(rows, spec, file_sha256=sha, snapshot_on=date.today())))
        logger.info("{}: {:,} rows (sha256 {})", spec.filename, len(rows), sha[:12])

    if args.dry_run:
        logger.success("Dry run: both files parsed; nothing written")
        return 0

    dsn = _dsn()
    if not dsn:
        logger.error("Set NEON_DATABASE_URL_DEV, NEON_DATABASE_URL or DATABASE_URL")
        return 2

    import psycopg2
    from psycopg2.extras import execute_values

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        for spec, rows in parsed:
            cur.execute(create_sql(spec))
            execute_values(cur, insert_sql(spec), rows, page_size=500)
            logger.info("bronze.{}: {:,} rows sent (already-loaded rows are skipped)", spec.table, len(rows))
        conn.commit()
    logger.success("Loaded Epoch AI data center files (CC BY 4.0, credit Epoch AI)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

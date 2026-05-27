#!/usr/bin/env python3
"""Load FEC individual contribution by-date shards into bronze.

This loader targets the cached bulk-download layout under:

    data/cache/fec_data/bulk-downloads/contributions-by-individuals/<cycle>/by_date/

Each ``itcont_*.txt`` shard is pipe-delimited and contains the raw individual
contribution records published by the FEC. The script streams the files into
``bronze.bronze_campaigns_contributions`` in the local ``open_navigator``
database.

Usage:
    python scripts/datasources/fec/load_fec_individual_contributions_by_date_to_bronze.py
    python scripts/datasources/fec/load_fec_individual_contributions_by_date_to_bronze.py \
        --input-dir data/cache/fec_data/bulk-downloads/contributions-by-individuals/2026/by_date
    python scripts/datasources/fec/load_fec_individual_contributions_by_date_to_bronze.py \
        --truncate
    python scripts/datasources/fec/load_fec_individual_contributions_by_date_to_bronze.py \
        --limit-files 2 --limit-rows 1000
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

import psycopg2
from psycopg2.extras import execute_values
from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "fec_data"
    / "bulk-downloads"
    / "contributions-by-individuals"
    / "2026"
    / "by_date"
)
DATABASE_URL = "postgresql://postgres:password@localhost:5433/open_navigator"
TARGET_TABLE = "bronze.bronze_campaigns_contributions"
SOURCE_COLUMNS = [
    "committee_id",
    "amended_indicator",
    "report_type",
    "transaction_pgi",
    "image_num",
    "transaction_type",
    "entity_type",
    "contributor_name",
    "contributor_city",
    "contributor_state",
    "contributor_zip",
    "contributor_employer",
    "contributor_occupation",
    "transaction_date_raw",
    "contribution_amount_raw",
    "other_id",
    "transaction_id",
    "file_num",
    "memo_code",
    "memo_text",
    "contribution_id",
]
INSERT_COLUMNS = [
    "contribution_id",
    "committee_id",
    "amended_indicator",
    "report_type",
    "transaction_pgi",
    "image_num",
    "transaction_type",
    "entity_type",
    "contributor_name",
    "contributor_city",
    "contributor_state",
    "contributor_zip",
    "contributor_employer",
    "contributor_occupation",
    "transaction_date_raw",
    "transaction_date",
    "contribution_amount_raw",
    "contribution_amount",
    "other_id",
    "transaction_id",
    "file_num",
    "memo_code",
    "memo_text",
    "source_file",
    "source_cycle",
    "loaded_at",
]
RAW_COLUMN_COUNT = len(SOURCE_COLUMNS)
DATE_RE = re.compile(r"^\d{8}$")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def detect_source_cycle(path: Path) -> int | None:
    """Return the first 4-digit year-like path component, if present."""
    for part in reversed(path.resolve().parts):
        if re.fullmatch(r"\d{4}", part):
            return int(part)
    return None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def parse_transaction_date(value: str | None) -> date | None:
    cleaned = normalize_text(value)
    if not cleaned or not DATE_RE.match(cleaned):
        return None
    try:
        return datetime.strptime(cleaned, "%m%d%Y").date()
    except ValueError:
        return None


def parse_amount(value: str | None) -> Decimal | None:
    cleaned = normalize_text(value)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def discover_input_files(input_path: Path) -> list[Path]:
    """Discover by-date shard files in a directory or normalize a single file."""
    if input_path.is_file():
        return [input_path]

    if input_path.name != "by_date" and (input_path / "by_date").is_dir():
        input_path = input_path / "by_date"

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    files = sorted(p for p in input_path.glob("*.txt") if p.is_file())
    if not files:
        raise FileNotFoundError(f"No .txt shard files found in {input_path}")
    return files


def ensure_target_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
                contribution_id text PRIMARY KEY,
                committee_id text,
                amended_indicator text,
                report_type text,
                transaction_pgi text,
                image_num text,
                transaction_type text,
                entity_type text,
                contributor_name text,
                contributor_city text,
                contributor_state text,
                contributor_zip text,
                contributor_employer text,
                contributor_occupation text,
                transaction_date_raw text,
                transaction_date date,
                contribution_amount_raw text,
                contribution_amount numeric(18, 2),
                other_id text,
                transaction_id text,
                file_num text,
                memo_code text,
                memo_text text,
                source_file text NOT NULL,
                source_cycle integer,
                loaded_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def row_is_header(row: Sequence[str]) -> bool:
    if len(row) != RAW_COLUMN_COUNT:
        return False
    first = (row[0] or "").strip().lower()
    return first in {"cmte_id", "committee_id"}


def normalize_record(
    row: Sequence[str],
    *,
    source_file: Path,
    source_cycle: int | None,
    loaded_at: datetime,
) -> tuple:
    values = list(row[:RAW_COLUMN_COUNT])
    if len(values) != RAW_COLUMN_COUNT:
        raise ValueError(f"Expected {RAW_COLUMN_COUNT} columns, got {len(values)}")

    record = dict(zip(SOURCE_COLUMNS, values, strict=True))

    contribution_id = normalize_text(record["contribution_id"])
    if not contribution_id:
        raise ValueError("Missing contribution_id/sub_id")

    transaction_date_raw = normalize_text(record["transaction_date_raw"])
    contribution_amount_raw = normalize_text(record["contribution_amount_raw"])

    return (
        contribution_id,
        normalize_text(record["committee_id"]),
        normalize_text(record["amended_indicator"]),
        normalize_text(record["report_type"]),
        normalize_text(record["transaction_pgi"]),
        normalize_text(record["image_num"]),
        normalize_text(record["transaction_type"]),
        normalize_text(record["entity_type"]),
        normalize_text(record["contributor_name"]),
        normalize_text(record["contributor_city"]),
        normalize_text(record["contributor_state"]),
        normalize_text(record["contributor_zip"]),
        normalize_text(record["contributor_employer"]),
        normalize_text(record["contributor_occupation"]),
        transaction_date_raw,
        parse_transaction_date(transaction_date_raw),
        contribution_amount_raw,
        parse_amount(contribution_amount_raw),
        normalize_text(record["other_id"]),
        normalize_text(record["transaction_id"]),
        normalize_text(record["file_num"]),
        normalize_text(record["memo_code"]),
        normalize_text(record["memo_text"]),
        str(source_file),
        source_cycle,
        loaded_at,
    )


def insert_batch(conn, rows: list[tuple]) -> int:
    if not rows:
        return 0

    insert_sql = f"""
        INSERT INTO {TARGET_TABLE} ({", ".join(INSERT_COLUMNS)})
        VALUES %s
        ON CONFLICT (contribution_id) DO UPDATE SET
            committee_id = EXCLUDED.committee_id,
            amended_indicator = EXCLUDED.amended_indicator,
            report_type = EXCLUDED.report_type,
            transaction_pgi = EXCLUDED.transaction_pgi,
            image_num = EXCLUDED.image_num,
            transaction_type = EXCLUDED.transaction_type,
            entity_type = EXCLUDED.entity_type,
            contributor_name = EXCLUDED.contributor_name,
            contributor_city = EXCLUDED.contributor_city,
            contributor_state = EXCLUDED.contributor_state,
            contributor_zip = EXCLUDED.contributor_zip,
            contributor_employer = EXCLUDED.contributor_employer,
            contributor_occupation = EXCLUDED.contributor_occupation,
            transaction_date_raw = EXCLUDED.transaction_date_raw,
            transaction_date = EXCLUDED.transaction_date,
            contribution_amount_raw = EXCLUDED.contribution_amount_raw,
            contribution_amount = EXCLUDED.contribution_amount,
            other_id = EXCLUDED.other_id,
            transaction_id = EXCLUDED.transaction_id,
            file_num = EXCLUDED.file_num,
            memo_code = EXCLUDED.memo_code,
            memo_text = EXCLUDED.memo_text,
            source_file = EXCLUDED.source_file,
            source_cycle = EXCLUDED.source_cycle,
            loaded_at = EXCLUDED.loaded_at
    """
    with conn.cursor() as cur:
        execute_values(cur, insert_sql, rows, page_size=len(rows))
    return len(rows)


def load_file(
    conn,
    file_path: Path,
    *,
    source_cycle: int | None,
    batch_size: int,
    limit_rows: int | None,
    dry_run: bool,
) -> int:
    loaded_at = datetime.now(UTC)
    rows: list[tuple] = []
    inserted = 0
    skipped = 0

    logger.info("Loading {}", file_path.name)

    with file_path.open("r", encoding="latin-1", newline="") as handle:
        reader = csv.reader(handle, delimiter="|")
        for raw_index, raw_row in enumerate(reader, start=1):
            if limit_rows is not None and inserted + len(rows) >= limit_rows:
                break

            if not raw_row:
                skipped += 1
                continue

            if row_is_header(raw_row):
                skipped += 1
                continue

            if len(raw_row) != RAW_COLUMN_COUNT:
                logger.warning(
                    "Skipping malformed row {} in {} (expected {} columns, got {})",
                    raw_index,
                    file_path.name,
                    RAW_COLUMN_COUNT,
                    len(raw_row),
                )
                skipped += 1
                continue

            try:
                rows.append(
                    normalize_record(
                        raw_row,
                        source_file=file_path,
                        source_cycle=source_cycle,
                        loaded_at=loaded_at,
                    )
                )
            except ValueError as exc:
                logger.warning(
                    "Skipping row {} in {}: {}",
                    raw_index,
                    file_path.name,
                    exc,
                )
                skipped += 1
                continue

            if len(rows) >= batch_size:
                if dry_run:
                    inserted += len(rows)
                else:
                    inserted += insert_batch(conn, rows)
                rows.clear()

        if rows:
            if dry_run:
                inserted += len(rows)
            else:
                inserted += insert_batch(conn, rows)

    if not dry_run:
        conn.commit()

    logger.info(
        "Finished {}: loaded {:,} rows, skipped {:,}",
        file_path.name,
        inserted,
        skipped,
    )
    return inserted


def load_directory(
    input_path: Path,
    *,
    truncate: bool,
    dry_run: bool,
    batch_size: int,
    limit_files: int | None,
    limit_rows: int | None,
) -> int:
    files = discover_input_files(input_path)
    if limit_files is not None:
        files = files[:limit_files]

    source_cycle = detect_source_cycle(input_path)
    logger.info("Source cycle: {}", source_cycle if source_cycle is not None else "unknown")

    if dry_run:
        logger.info("Dry run enabled: no rows will be written to the database")

    conn = None if dry_run else get_connection()
    try:
        if conn is not None:
            ensure_target_table(conn)
            with conn.cursor() as cur:
                if truncate:
                    logger.info("Truncating {}", TARGET_TABLE)
                    cur.execute(f"TRUNCATE TABLE {TARGET_TABLE}")
                    conn.commit()

        total_loaded = 0
        rows_remaining = limit_rows

        for file_path in files:
            file_limit = rows_remaining
            loaded = load_file(
                conn,
                file_path,
                source_cycle=source_cycle,
                batch_size=batch_size,
                limit_rows=file_limit,
                dry_run=dry_run,
            )
            total_loaded += loaded
            if rows_remaining is not None:
                rows_remaining = max(rows_remaining - loaded, 0)
                if rows_remaining == 0:
                    break

        return total_loaded
    finally:
        if conn is not None:
            conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load FEC individual contribution by-date shards into bronze"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Input directory or file (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help=f"Truncate {TARGET_TABLE} before loading",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and count rows without writing to the database",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Rows per insert batch (default: 5000)",
    )
    parser.add_argument(
        "--limit-files",
        type=int,
        help="Only process the first N shard files",
    )
    parser.add_argument(
        "--limit-rows",
        type=int,
        help="Only process the first N rows across all files",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logger.info("=" * 72)
    logger.info("FEC Individual Contributions by-date → bronze")
    logger.info("=" * 72)
    logger.info("Input: {}", args.input_dir)
    logger.info("Target: {}", TARGET_TABLE)

    loaded = load_directory(
        args.input_dir,
        truncate=args.truncate,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        limit_files=args.limit_files,
        limit_rows=args.limit_rows,
    )

    logger.success("Loaded {:,} contribution rows into {}", loaded, TARGET_TABLE)


if __name__ == "__main__":
    main()
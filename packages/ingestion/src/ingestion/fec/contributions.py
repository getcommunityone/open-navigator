#!/usr/bin/env python3
"""FEC individual contributions pipeline: load by-date shards into bronze.

Ported from load_fec_individual_contributions_by_date_to_bronze.py to the
core_lib DataSourcePipeline contract.

Targets cached bulk-download layout:
    data/cache/fec_data/bulk-downloads/contributions-by-individuals/<cycle>/by_date/

Each itcont_*.txt shard is pipe-delimited FEC individual contribution data.
Loads into bronze.bronze_campaigns_contributions via the framework-managed
async session.

Usage:
    python -m ingestion.fec.contributions
    python -m ingestion.fec.contributions
    python -m ingestion.fec.contributions --truncate
    python -m ingestion.fec.contributions \\
        --input-dir data/cache/fec_data/bulk-downloads/contributions-by-individuals/2026/by_date \\
        --limit-files 2 --limit-rows 1000

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL (resolved by
    core_lib.db.engine). Hardcoded postgres://localhost:5433 credentials
    from the legacy script are removed.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import AsyncIterator, Sequence

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


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
RAW_COLUMN_COUNT = len(SOURCE_COLUMNS)
DATE_RE = re.compile(r"^\d{8}$")


# ---------------------------------------------------------------------------
# Row helpers (unchanged behavior from legacy loader)
# ---------------------------------------------------------------------------


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


def row_is_header(row: Sequence[str]) -> bool:
    if len(row) != RAW_COLUMN_COUNT:
        return False
    first = (row[0] or "").strip().lower()
    return first in {"cmte_id", "committee_id"}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class ContributionRow(RawRow):
    """One FEC individual contribution row, validated before upsert."""

    contribution_id: str = Field(min_length=1)
    committee_id: str | None = None
    amended_indicator: str | None = None
    report_type: str | None = None
    transaction_pgi: str | None = None
    image_num: str | None = None
    transaction_type: str | None = None
    entity_type: str | None = None
    contributor_name: str | None = None
    contributor_city: str | None = None
    contributor_state: str | None = None
    contributor_zip: str | None = None
    contributor_employer: str | None = None
    contributor_occupation: str | None = None
    transaction_date_raw: str | None = None
    transaction_date: date | None = None
    contribution_amount_raw: str | None = None
    contribution_amount: Decimal | None = None
    other_id: str | None = None
    transaction_id: str | None = None
    file_num: str | None = None
    memo_code: str | None = None
    memo_text: str | None = None
    source_file: str
    source_cycle: int | None = None


_ENSURE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_ENSURE_TABLE_SQL = text(
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

_TRUNCATE_SQL = text(f"TRUNCATE TABLE {TARGET_TABLE}")

_UPSERT_SQL = text(
    f"""
    INSERT INTO {TARGET_TABLE} (
        contribution_id, committee_id, amended_indicator, report_type,
        transaction_pgi, image_num, transaction_type, entity_type,
        contributor_name, contributor_city, contributor_state, contributor_zip,
        contributor_employer, contributor_occupation, transaction_date_raw,
        transaction_date, contribution_amount_raw, contribution_amount,
        other_id, transaction_id, file_num, memo_code, memo_text,
        source_file, source_cycle, loaded_at
    )
    VALUES (
        :contribution_id, :committee_id, :amended_indicator, :report_type,
        :transaction_pgi, :image_num, :transaction_type, :entity_type,
        :contributor_name, :contributor_city, :contributor_state, :contributor_zip,
        :contributor_employer, :contributor_occupation, :transaction_date_raw,
        :transaction_date, :contribution_amount_raw, :contribution_amount,
        :other_id, :transaction_id, :file_num, :memo_code, :memo_text,
        :source_file, :source_cycle, :loaded_at
    )
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
)


class FecContributionsPipeline(DataSourcePipeline[ContributionRow]):
    source = "fec_contributions"
    batch_size = 5_000
    row_schema = ContributionRow

    def __init__(
        self,
        *,
        input_dir: Path = DEFAULT_INPUT_DIR,
        limit_files: int | None = None,
        limit_rows: int | None = None,
    ):
        self._input_dir = input_dir
        self._limit_files = limit_files
        self._limit_rows = limit_rows

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        files = discover_input_files(self._input_dir)
        if self._limit_files is not None:
            files = files[: self._limit_files]
        source_cycle = detect_source_cycle(self._input_dir)
        emitted = 0
        for file_path in files:
            with file_path.open("r", encoding="latin-1", newline="") as handle:
                reader = csv.reader(handle, delimiter="|")
                for raw_index, raw_row in enumerate(reader, start=1):
                    if self._limit_rows is not None and emitted >= self._limit_rows:
                        return
                    if not raw_row or row_is_header(raw_row):
                        continue
                    if len(raw_row) != RAW_COLUMN_COUNT:
                        continue  # malformed; framework will count via rejected if validated, here we drop silently like legacy
                    record = dict(zip(SOURCE_COLUMNS, raw_row, strict=True))
                    contribution_id = normalize_text(record["contribution_id"])
                    if not contribution_id:
                        continue
                    transaction_date_raw = normalize_text(record["transaction_date_raw"])
                    contribution_amount_raw = normalize_text(record["contribution_amount_raw"])
                    yield {
                        "source": self.source,
                        "source_version": str(source_cycle) if source_cycle else "unknown",
                        "natural_key": contribution_id,
                        "contribution_id": contribution_id,
                        "committee_id": normalize_text(record["committee_id"]),
                        "amended_indicator": normalize_text(record["amended_indicator"]),
                        "report_type": normalize_text(record["report_type"]),
                        "transaction_pgi": normalize_text(record["transaction_pgi"]),
                        "image_num": normalize_text(record["image_num"]),
                        "transaction_type": normalize_text(record["transaction_type"]),
                        "entity_type": normalize_text(record["entity_type"]),
                        "contributor_name": normalize_text(record["contributor_name"]),
                        "contributor_city": normalize_text(record["contributor_city"]),
                        "contributor_state": normalize_text(record["contributor_state"]),
                        "contributor_zip": normalize_text(record["contributor_zip"]),
                        "contributor_employer": normalize_text(record["contributor_employer"]),
                        "contributor_occupation": normalize_text(record["contributor_occupation"]),
                        "transaction_date_raw": transaction_date_raw,
                        "transaction_date": parse_transaction_date(transaction_date_raw),
                        "contribution_amount_raw": contribution_amount_raw,
                        "contribution_amount": parse_amount(contribution_amount_raw),
                        "other_id": normalize_text(record["other_id"]),
                        "transaction_id": normalize_text(record["transaction_id"]),
                        "file_num": normalize_text(record["file_num"]),
                        "memo_code": normalize_text(record["memo_code"]),
                        "memo_text": normalize_text(record["memo_text"]),
                        "source_file": str(file_path),
                        "source_cycle": source_cycle,
                    }
                    emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[ContributionRow],
        ctx: PipelineContext,
    ) -> None:
        loaded_at = datetime.now(timezone.utc)
        params = []
        for r in rows:
            d = r.model_dump()
            d["loaded_at"] = loaded_at
            # pydantic frozen + Decimal/Date already serialized natively for SQLAlchemy
            params.append(d)
        await session.execute(_UPSERT_SQL, params)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_ENSURE_SCHEMA_SQL)
        await session.execute(_ENSURE_TABLE_SQL)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


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


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = FecContributionsPipeline(
        input_dir=args.input_dir,
        limit_files=args.limit_files,
        limit_rows=args.limit_rows,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

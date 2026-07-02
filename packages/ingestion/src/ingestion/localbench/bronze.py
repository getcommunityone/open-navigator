"""Load the three LocalBench QA files into bronze (raw fidelity).

Reads the cached LocalBench files (downloading them first if missing via
``ingestion.localbench.download``) and lands each one verbatim into its own
bronze table:

    census_QA.csv      → bronze.bronze_localbench_census_qa   (6,120)
    reddit_QA.parquet  → bronze.bronze_localbench_reddit_qa   (4,000)
    news_QA.parquet    → bronze.bronze_localbench_news_qa     (4,662)

Each table keeps the source columns (lower-cased) plus a synthetic ``qa_id``
PRIMARY KEY (``<dataset>_<rownum>``, matching LocalBench's own id style),
a ``dataset`` tag, ``source_file``, and ``ingestion_date``. FIPS is normalised
to a 5-digit string at the ingestion boundary (the source stores it as a float
with a trailing ``.0``); everything else is landed source-native. Unification to
LocalBench's shared logical schema is left to dbt staging — no SQL/transform
logic here beyond raw typing.

These files are static benchmark releases, so the loader does a full reload
(TRUNCATE + INSERT) rather than an incremental upsert.

Usage:
    export DATABASE_URL=postgresql://postgres:password@localhost:5433/open_navigator
    python -m ingestion.localbench.bronze                 # download (if needed) + load all
    python -m ingestion.localbench.bronze --datasets census
    python -m ingestion.localbench.bronze --dry-run
    python -m ingestion.localbench.bronze --bootstrap     # create empty tables only

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (DEV target only). LOCALBENCH_CACHE_DIR overrides the cache location.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging

from .download import default_cache_dir, download_all

DATA_SOURCE = "localbench"


@dataclass(frozen=True)
class Dataset:
    """One LocalBench file → one bronze table."""

    key: str  # "census" | "reddit" | "news"
    filename: str
    table: str
    create_sql: str
    insert_sql: str
    # source column -> bronze column (after lower-casing source headers)
    columns: dict[str, str]
    text_cols: tuple[str, ...] = field(default_factory=tuple)


CENSUS = Dataset(
    key="census",
    filename="census_QA.csv",
    table="bronze.bronze_localbench_census_qa",
    create_sql="""
        CREATE TABLE IF NOT EXISTS bronze.bronze_localbench_census_qa (
            qa_id            TEXT PRIMARY KEY,
            dataset          TEXT NOT NULL,
            state_name       TEXT,
            county_name      TEXT,
            fips             TEXT,
            pop_cou          BIGINT,
            rucc             SMALLINT,
            rucc_group       TEXT,
            metric           TEXT,
            question_type    TEXT,
            question         TEXT,
            answer           TEXT,
            selected_variant TEXT,
            dimension        TEXT,
            question_tokens  INTEGER,
            answer_tokens    INTEGER,
            source_file      TEXT,
            ingestion_date   TIMESTAMP DEFAULT NOW()
        )
    """,
    insert_sql="""
        INSERT INTO bronze.bronze_localbench_census_qa (
            qa_id, dataset, state_name, county_name, fips, pop_cou, rucc,
            rucc_group, metric, question_type, question, answer,
            selected_variant, dimension, question_tokens, answer_tokens,
            source_file
        ) VALUES (
            :qa_id, :dataset, :state_name, :county_name, :fips, :pop_cou, :rucc,
            :rucc_group, :metric, :question_type, :question, :answer,
            :selected_variant, :dimension, :question_tokens, :answer_tokens,
            :source_file
        )
    """,
    columns={
        "state_name": "state_name",
        "county_name": "county_name",
        "fips": "fips",
        "pop_cou": "pop_cou",
        "rucc": "rucc",
        "rucc_group": "rucc_group",
        "metric": "metric",
        "question_type": "question_type",
        "question": "question",
        "answer": "answer",
        "selected_variant": "selected_variant",
        "dimension": "dimension",
        "question_tokens": "question_tokens",
        "answer_tokens": "answer_tokens",
    },
)

REDDIT = Dataset(
    key="reddit",
    filename="reddit_QA.parquet",
    table="bronze.bronze_localbench_reddit_qa",
    create_sql="""
        CREATE TABLE IF NOT EXISTS bronze.bronze_localbench_reddit_qa (
            qa_id            TEXT PRIMARY KEY,
            dataset          TEXT NOT NULL,
            state            TEXT,
            county           TEXT,
            created_time     TEXT,
            rucc             SMALLINT,
            rucc_group       TEXT,
            fips             TEXT,
            question         TEXT,
            context          TEXT,
            answer           TEXT,
            chosen_dimension TEXT,
            source_file      TEXT,
            ingestion_date   TIMESTAMP DEFAULT NOW()
        )
    """,
    insert_sql="""
        INSERT INTO bronze.bronze_localbench_reddit_qa (
            qa_id, dataset, state, county, created_time, rucc, rucc_group, fips,
            question, context, answer, chosen_dimension, source_file
        ) VALUES (
            :qa_id, :dataset, :state, :county, :created_time, :rucc, :rucc_group,
            :fips, :question, :context, :answer, :chosen_dimension, :source_file
        )
    """,
    columns={
        "state": "state",
        "county": "county",
        "created_time": "created_time",
        "rucc": "rucc",
        "rucc_group": "rucc_group",
        "fips": "fips",
        "question": "question",
        "context": "context",
        "answer": "answer",
        "chosen_dimension": "chosen_dimension",
    },
    text_cols=("created_time",),
)

NEWS = Dataset(
    key="news",
    filename="news_QA.parquet",
    table="bronze.bronze_localbench_news_qa",
    create_sql="""
        CREATE TABLE IF NOT EXISTS bronze.bronze_localbench_news_qa (
            qa_id            TEXT PRIMARY KEY,
            dataset          TEXT NOT NULL,
            state            TEXT,
            county           TEXT,
            article_date     TEXT,
            rucc             TEXT,
            rucc_group       TEXT,
            fips             TEXT,
            question         TEXT,
            context          TEXT,
            answer           TEXT,
            chosen_dimension TEXT,
            source_file      TEXT,
            ingestion_date   TIMESTAMP DEFAULT NOW()
        )
    """,
    insert_sql="""
        INSERT INTO bronze.bronze_localbench_news_qa (
            qa_id, dataset, state, county, article_date, rucc, rucc_group, fips,
            question, context, answer, chosen_dimension, source_file
        ) VALUES (
            :qa_id, :dataset, :state, :county, :article_date, :rucc, :rucc_group,
            :fips, :question, :context, :answer, :chosen_dimension, :source_file
        )
    """,
    columns={
        "state": "state",
        "county": "county",
        "date": "article_date",
        "rucc": "rucc",
        "rucc_group": "rucc_group",
        "fips": "fips",
        "question": "question",
        "context": "context",
        "answer": "answer",
        "chosen_dimension": "chosen_dimension",
    },
    text_cols=("rucc", "article_date"),
)

DATASETS: dict[str, Dataset] = {ds.key: ds for ds in (CENSUS, REDDIT, NEWS)}


# --- value coercion ----------------------------------------------------------


def _clean_scalar(val: Any) -> Any:
    """Convert pandas NaN/NaT to None; pass everything else through."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def _format_fips(val: Any) -> str | None:
    """Normalise a source FIPS (float ``48341.0`` / int / str) to a 5-digit string."""
    val = _clean_scalar(val)
    if val is None:
        return None
    if isinstance(val, float):
        val = int(val)
    if isinstance(val, int):
        return f"{val:05d}"
    s = str(val).strip()
    if not s:
        return None
    # strip a trailing ".0" that survives as text, then zero-pad numeric codes.
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(5) if s.isdigit() else s


def _to_record(
    row: pd.Series, ds: Dataset, lower_map: dict[str, str], index: int
) -> dict[str, Any]:
    """Build one bronze row dict from a source row."""
    rec: dict[str, Any] = {
        "qa_id": f"{ds.key}_{index}",
        "dataset": ds.key,
        "source_file": ds.filename,
    }
    for src_col, bronze_col in ds.columns.items():
        actual = lower_map.get(src_col.lower())
        raw = row[actual] if actual is not None else None
        if bronze_col == "fips":
            rec[bronze_col] = _format_fips(raw)
        elif bronze_col in ds.text_cols:
            cleaned = _clean_scalar(raw)
            rec[bronze_col] = None if cleaned is None else str(cleaned)
        else:
            rec[bronze_col] = _clean_scalar(raw)
    return rec


def read_records(ds: Dataset, cache_dir: Path) -> list[dict[str, Any]]:
    """Read a LocalBench file into a list of bronze row dicts."""
    path = cache_dir / ds.filename
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — run `python -m ingestion.localbench.download` first"
        )
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    lower_map = {c.lower(): c for c in df.columns}
    records = [
        _to_record(row, ds, lower_map, i) for i, (_, row) in enumerate(df.iterrows())
    ]
    logger.info("Read {:,} rows from {}", len(records), ds.filename)
    return records


# --- DB ----------------------------------------------------------------------

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")


async def _prepare_target(session: AsyncSession, ds: Dataset, truncate: bool) -> None:
    await session.execute(_CREATE_SCHEMA_SQL)
    await session.execute(text(ds.create_sql))
    if truncate:
        before = (
            await session.execute(text(f"SELECT COUNT(*) FROM {ds.table}"))
        ).scalar_one()
        await session.execute(text(f"TRUNCATE TABLE {ds.table}"))
        logger.info("Truncated {} ({:,} rows removed)", ds.table, before)


async def load_dataset(
    ds: Dataset, records: list[dict[str, Any]], *, truncate: bool = True
) -> int:
    async with async_session() as session:
        await _prepare_target(session, ds, truncate)
        if records:
            await session.execute(text(ds.insert_sql), records)
        total = (
            await session.execute(text(f"SELECT COUNT(*) FROM {ds.table}"))
        ).scalar_one()
    logger.success("Loaded {:,} rows → {} (table total: {:,})", len(records), ds.table, total)
    return len(records)


async def bootstrap(keys: list[str], *, truncate: bool = False) -> None:
    async with async_session() as session:
        for key in keys:
            await _prepare_target(session, DATASETS[key], truncate)
    logger.success("Bootstrapped LocalBench bronze tables (schema only): {}", ", ".join(keys))


# --- CLI ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load the three LocalBench QA files into bronze.bronze_localbench_*"
    )
    parser.add_argument(
        "--datasets",
        default="census,reddit,news",
        help="Comma-separated subset of {census,reddit,news} (default: all)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="LocalBench cache dir (default: $LOCALBENCH_CACHE_DIR or data/cache/localbench)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Do not fetch missing files; read only what's already cached",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Append instead of full reload (default reloads via TRUNCATE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read + parse, show first records, no DB writes",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the empty bronze tables (schema only) and exit",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    keys = [k.strip() for k in args.datasets.split(",") if k.strip()]
    unknown = [k for k in keys if k not in DATASETS]
    if unknown:
        logger.error("Unknown dataset(s): {} (valid: census, reddit, news)", unknown)
        return 2

    logger.info("=" * 70)
    logger.info("LocalBench → bronze ({})", ", ".join(keys))
    logger.info("=" * 70)

    if args.bootstrap:
        await bootstrap(keys, truncate=not args.no_truncate)
        return 0

    cache_dir = args.cache_dir or default_cache_dir()
    if not args.no_download:
        download_all(cache_dir)

    total = 0
    for key in keys:
        ds = DATASETS[key]
        records = read_records(ds, cache_dir)
        if args.dry_run:
            logger.warning("DRY RUN [{}] — first 2 of {:,} records:", key, len(records))
            for r in records[:2]:
                logger.info("  {}", r)
            continue
        total += await load_dataset(ds, records, truncate=not args.no_truncate)

    if not args.dry_run:
        logger.success("=" * 70)
        logger.success("Done. Loaded {:,} LocalBench rows into bronze.", total)
        logger.success("=" * 70)
    return 0


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

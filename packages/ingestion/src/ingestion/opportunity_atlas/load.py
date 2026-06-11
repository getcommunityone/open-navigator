"""Load Opportunity Atlas commuting-zone mobility data into bronze (long/tidy).

Streams the Opportunity Insights CZ outcomes CSV (~58 MB, 741 CZ rows,
~10,825 columns) with the stdlib ``csv`` module, selecting ONLY the columns we
serve by header index (never a wide pandas load), reshapes LONG, and UPSERTs into
``bronze.bronze_opportunity_atlas_cz``:

    cz integer, czname text, race text, gender text, parent_income_level text,
    child_income_rank numeric, n numeric, loaded_at timestamptz

One bronze row is emitted for EVERY (cz, race, gender, parent_income_level) combo
whose value column is present in the source header (63 per CZ). ``child_income_rank``
is NULL when the source cell is blank (honest "missing", never a stand-in number);
``n`` is taken from the per-(race,gender) ``kfr_<race>_<gender>_n`` sample-count
column so downstream empty-states are honest.

Measure (``kfr_<race>_<gender>_p<plevel>``): the child's mean adult
household-income RANK (a decimal 0..1) given parents at the ``p<plevel>`` national
income percentile. parent_income_level maps p25 -> 'low', p50 -> 'middle',
p75 -> 'high'.

Source:
    Opportunity Insights — "Opportunity Atlas" / Chetty, Hendren, Jones & Porter
    (2018), "Race and Economic Opportunity in the United States."

Usage:
    python -m ingestion.opportunity_atlas.load              # download (cached) + load
    python -m ingestion.opportunity_atlas.load --truncate   # truncate then reload
    python -m ingestion.opportunity_atlas.load --dry-run    # parse, no DB writes
    python -m ingestion.opportunity_atlas.load --bootstrap  # create empty table only
    python -m ingestion.opportunity_atlas.load --csv /path/to/cz_outcomes.csv

Configuration:
    NEON_DATABASE_URL_DEV / OPEN_NAVIGATOR_DATABASE_URL / NEON_DATABASE_URL /
    local default (localhost:5433 open_navigator) via core_lib.db.
    DEV target only — never prod.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path
from typing import Any, Iterator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging

from .download import DEFAULT_CACHE_FILE, download_cz_outcomes

TABLE = "bronze.bronze_opportunity_atlas_cz"

# The race / gender / parent-income dimensions we serve.
RACES = ["pooled", "white", "black", "hisp", "asian", "natam", "other"]
GENDERS = ["pooled", "male", "female"]
# Source percentile -> our parent_income_level label.
PLEVEL_TO_LEVEL = {"25": "low", "50": "middle", "75": "high"}

# The stdlib csv reader can choke on the very long header line's field-size limit.
csv.field_size_limit(10 * 1024 * 1024)


# --- DDL (each statement a SEPARATE text(); never multiple per text()) --------

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_opportunity_atlas_cz (
        cz                    INTEGER     NOT NULL,
        czname                TEXT,
        race                  TEXT        NOT NULL,
        gender                TEXT        NOT NULL,
        parent_income_level   TEXT        NOT NULL,
        child_income_rank     NUMERIC,
        n                     NUMERIC,
        loaded_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (cz, race, gender, parent_income_level)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_boac_czname "
        "ON bronze.bronze_opportunity_atlas_cz(czname)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_boac_dims "
        "ON bronze.bronze_opportunity_atlas_cz(race, gender, parent_income_level)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_opportunity_atlas_cz")

_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_opportunity_atlas_cz (
        cz, czname, race, gender, parent_income_level,
        child_income_rank, n, loaded_at
    ) VALUES (
        :cz, :czname, :race, :gender, :parent_income_level,
        :child_income_rank, :n, NOW()
    )
    ON CONFLICT (cz, race, gender, parent_income_level) DO UPDATE SET
        czname            = EXCLUDED.czname,
        child_income_rank = EXCLUDED.child_income_rank,
        n                 = EXCLUDED.n,
        loaded_at         = NOW()
    """
)


# --- parsing helpers ---------------------------------------------------------


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _to_num(val: Any) -> float | None:
    """Parse a numeric cell; blank/non-numeric -> None (honest missing, never 0)."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() in ("NA", "N/A", "."):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def build_column_plan(header: list[str]) -> dict[str, Any]:
    """Resolve the header indices for every column we need.

    Returns a dict with:
        cz_idx, czname_idx: int | None
        combos: list of (race, gender, plevel, level, value_idx, n_idx) for every
                kfr_<race>_<gender>_p<plevel> value column PRESENT in the header.
    Missing optional columns are skipped (logged), not fabricated.
    """
    pos = {name: i for i, name in enumerate(header)}

    cz_idx = pos.get("cz")
    if cz_idx is None:
        raise ValueError("Source header is missing required column 'cz'.")
    czname_idx = pos.get("czname")
    if czname_idx is None:
        logger.warning("Source header missing 'czname'; czname will be NULL.")

    combos: list[tuple[str, str, str, str, int, int | None]] = []
    missing_val: list[str] = []
    for race in RACES:
        for gender in GENDERS:
            n_col = f"kfr_{race}_{gender}_n"
            n_idx = pos.get(n_col)
            for plevel, level in PLEVEL_TO_LEVEL.items():
                val_col = f"kfr_{race}_{gender}_p{plevel}"
                val_idx = pos.get(val_col)
                if val_idx is None:
                    missing_val.append(val_col)
                    continue
                combos.append((race, gender, plevel, level, val_idx, n_idx))

    if missing_val:
        logger.warning(
            "{} expected value columns absent from source header (skipped): {}",
            len(missing_val),
            ", ".join(missing_val[:10]) + ("..." if len(missing_val) > 10 else ""),
        )
    logger.info(
        "Column plan: {} value-column combos present (of {} expected).",
        len(combos),
        len(RACES) * len(GENDERS) * len(PLEVEL_TO_LEVEL),
    )
    return {"cz_idx": cz_idx, "czname_idx": czname_idx, "combos": combos}


def iter_long_records(csv_path: Path) -> Iterator[dict[str, Any]]:
    """Stream the CSV and yield one long bronze record per (cz,race,gender,plevel).

    Reads by column index only — the full ~10,825-column row is read by csv but
    we touch just the indices in the column plan, so no wide frame is built.
    """
    with csv_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        plan = build_column_plan(header)
        cz_idx = plan["cz_idx"]
        czname_idx = plan["czname_idx"]
        combos = plan["combos"]
        row_count = 0
        for row in reader:
            if not row:
                continue
            cz = _to_int(row[cz_idx]) if cz_idx < len(row) else None
            if cz is None:
                continue
            row_count += 1
            czname = (
                (row[czname_idx].strip() or None)
                if czname_idx is not None and czname_idx < len(row)
                else None
            )
            for race, gender, _plevel, level, val_idx, n_idx in combos:
                rank = _to_num(row[val_idx]) if val_idx < len(row) else None
                n = (
                    _to_num(row[n_idx])
                    if (n_idx is not None and n_idx < len(row))
                    else None
                )
                yield {
                    "cz": cz,
                    "czname": czname,
                    "race": race,
                    "gender": gender,
                    "parent_income_level": level,
                    "child_income_rank": rank,
                    "n": n,
                }
        logger.info("Parsed {:,} CZ data rows from {}", row_count, csv_path.name)


# --- DB ----------------------------------------------------------------------


async def _prepare_target(session: AsyncSession, truncate: bool) -> None:
    await session.execute(_CREATE_SCHEMA_SQL)
    await session.execute(_CREATE_TABLE_SQL)
    for idx in _CREATE_INDEXES_SQL:
        await session.execute(idx)
    if truncate:
        before = (
            await session.execute(text(f"SELECT COUNT(*) FROM {TABLE}"))
        ).scalar_one()
        await session.execute(_TRUNCATE_SQL)
        logger.info("Truncated {} ({:,} rows removed)", TABLE, before)


async def _log_summary(session: AsyncSession) -> None:
    total = (await session.execute(text(f"SELECT COUNT(*) FROM {TABLE}"))).scalar_one()
    distinct_cz = (
        await session.execute(text(f"SELECT COUNT(DISTINCT cz) FROM {TABLE}"))
    ).scalar_one()
    with_rank = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE child_income_rank IS NOT NULL")
        )
    ).scalar_one()
    logger.success(
        "Loaded {:,} long rows ({:,} distinct CZs; {:,} with a non-NULL rank) -> {}",
        total,
        distinct_cz,
        with_rank,
        TABLE,
    )
    # Verify-after-load anchors (pooled/pooled/low).
    anchors = await session.execute(
        text(
            f"""
            SELECT czname, cz, child_income_rank
            FROM {TABLE}
            WHERE cz IN (10801, 20500)
              AND race = 'pooled' AND gender = 'pooled'
              AND parent_income_level = 'low'
            ORDER BY cz
            """
        )
    )
    for czname, cz, rank in anchors.all():
        logger.info("  anchor cz={} ({}) pooled/pooled/low rank={}", cz, czname, rank)


async def bootstrap(truncate: bool = False) -> None:
    async with async_session() as session:
        await _prepare_target(session, truncate)
    logger.success("Bootstrapped {} (schema only).", TABLE)


async def load_records(records: list[dict[str, Any]], truncate: bool) -> int:
    if not records:
        logger.warning("No records to load.")
        return 0
    async with async_session() as session:
        await _prepare_target(session, truncate)
        # executemany via a single execute with a list of param dicts.
        CHUNK = 5000
        for i in range(0, len(records), CHUNK):
            await session.execute(_INSERT_SQL, records[i : i + CHUNK])
        await _log_summary(session)
    return len(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Load Opportunity Atlas commuting-zone mobility (long) into "
            "bronze.bronze_opportunity_atlas_cz"
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=f"Path to a local cz_outcomes.csv (default: download+cache to {DEFAULT_CACHE_FILE})",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the source CSV even if a complete cache exists.",
    )
    parser.add_argument(
        "--truncate", action="store_true", help="TRUNCATE table before loading."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + reshape, show first records and counts, no DB writes.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the empty bronze table (schema only) and exit.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    logger.info("=" * 70)
    logger.info("Opportunity Atlas CZ mobility -> {}", TABLE)
    logger.info("=" * 70)

    if args.bootstrap:
        await bootstrap(truncate=args.truncate)
        return 0

    csv_path = args.csv or download_cz_outcomes(force=args.force_download)
    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.error("CSV not found: {}", csv_path)
        return 1

    records = list(iter_long_records(csv_path))
    logger.info("Reshaped {:,} long records.", len(records))

    if args.dry_run:
        logger.warning("DRY RUN — first 5 records, no DB writes:")
        for r in records[:5]:
            logger.info("  {}", r)
        # Surface the anchors from the parsed data so a dry-run still verifies.
        for r in records:
            if (
                r["cz"] in (10801, 20500)
                and r["race"] == "pooled"
                and r["gender"] == "pooled"
                and r["parent_income_level"] == "low"
            ):
                logger.info(
                    "  ANCHOR cz={} ({}) pooled/pooled/low rank={}",
                    r["cz"],
                    r["czname"],
                    r["child_income_rank"],
                )
        return 0

    await load_records(records, truncate=args.truncate)
    logger.success("=" * 70)
    logger.success("Done.")
    logger.success("=" * 70)
    return 0


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""NTEE codes pipeline: load cached parquet into cause_ntee.

Ported from load_to_postgres.py to the core_lib DataSourcePipeline contract.

The National Taxonomy of Exempt Entities (NTEE) codes classify tax-exempt
nonprofit organizations by their mission and activities.

Data source: IRS Publication 557 + NCCS (National Center for Charitable
Statistics), materialized to data/gold/causes_ntee_codes.parquet (196 codes).

Usage:
    python -m scripts.datasources.ntee.codes_pipeline
    python scripts/datasources/ntee/codes_pipeline.py --truncate
    python scripts/datasources/ntee/codes_pipeline.py \\
        --file data/gold/causes_ntee_codes.parquet --limit 50

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433 and the
    legacy --neon / --db-url flags).
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


GOLD_DIR = Path("data/gold")


def find_latest_parquet() -> Path:
    files = sorted(GOLD_DIR.glob("causes_ntee_codes*.parquet"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No NTEE codes parquet found in {GOLD_DIR}. "
            "Run scripts/datasources/ntee/generate_ntee_codes.py first."
        )
    return files[0]


def _is_missing(val: Any) -> bool:
    """True for None / NaN / empty-string values (pandas-friendly)."""
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    return str(val).strip() == ""


def _safe_str(val: Any, maxlen: int | None = None) -> str | None:
    if _is_missing(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def build_breadcrumb(
    code: str,
    parent_code: Any,
    code_lookup: dict[str, str],
    parent_lookup: dict[str, Any],
) -> str:
    """Build hierarchical breadcrumb path by walking up the parent chain.

    Preserved from the original loader; the dataframe lookups are replaced by
    plain dicts so the helper is pure and unit-testable.
    """
    if _is_missing(parent_code):
        # Top level - just the name
        return code_lookup.get(code, code)

    # Build path: traverse up the parent chain
    path: list[str] = []
    current = parent_code

    # Traverse up to 5 levels to avoid infinite loops
    for _ in range(5):
        if _is_missing(current):
            break
        if current in code_lookup:
            path.insert(0, code_lookup[current])
        # Find parent of current
        nxt = parent_lookup.get(current)
        if not _is_missing(nxt):
            current = nxt
        else:
            break

    # Add current code's name
    path.append(code_lookup.get(code, code))

    return " > ".join(path)


class NteeCodesRow(RawRow):
    """One NTEE classification code, validated before upsert."""

    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    description: str | None = None
    cause_type: str = Field(min_length=1, max_length=20)
    parent_code: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    cause_breadcrumb: str | None = None
    code_source: str = Field(min_length=1, max_length=50)


_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS cause_ntee (
        code VARCHAR(100) PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        cause_type VARCHAR(20) NOT NULL,
        parent_code VARCHAR(100),
        category VARCHAR(100),
        subcategory VARCHAR(100),
        cause_breadcrumb TEXT,
        source VARCHAR(50) NOT NULL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_cause_ntee_type ON cause_ntee(cause_type)"),
    text(
        "CREATE INDEX IF NOT EXISTS idx_cause_ntee_name_search "
        "ON cause_ntee USING gin(to_tsvector('english', name))"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_cause_ntee_description_search "
        "ON cause_ntee USING gin(to_tsvector('english', description))"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE cause_ntee")

_UPSERT_SQL = text(
    """
    INSERT INTO cause_ntee
        (code, name, description, cause_type, parent_code,
         category, subcategory, cause_breadcrumb, source, last_updated)
    VALUES
        (:code, :name, :description, :cause_type, :parent_code,
         :category, :subcategory, :cause_breadcrumb, :code_source, CURRENT_TIMESTAMP)
    ON CONFLICT (code) DO UPDATE SET
        name             = EXCLUDED.name,
        description      = EXCLUDED.description,
        cause_breadcrumb = EXCLUDED.cause_breadcrumb,
        last_updated     = CURRENT_TIMESTAMP
    """
)


class NteeCodesPipeline(DataSourcePipeline[NteeCodesRow]):
    source = "ntee_codes"
    batch_size = 1_000
    row_schema = NteeCodesRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or find_latest_parquet()
        df = pd.read_parquet(path)

        # Lookups used to build hierarchical breadcrumbs (preserved behavior).
        code_lookup = {
            row["ntee_code"]: row.get("description", "")
            for _, row in df.iterrows()
        }
        parent_lookup = {
            row["ntee_code"]: row.get("parent_code")
            for _, row in df.iterrows()
        }

        emitted = 0
        for _, row in df.iterrows():
            if self._limit is not None and emitted >= self._limit:
                return
            code = _safe_str(row.get("ntee_code"), 100)
            if not code:
                continue
            description = _safe_str(row.get("description"))
            parent_code = _safe_str(row.get("parent_code"), 100)
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": code,
                "code": code,
                "name": description or code,
                "description": description,
                "cause_type": "ntee",
                "parent_code": parent_code,
                "category": _safe_str(row.get("ntee_type"), 100),
                "subcategory": None,
                "cause_breadcrumb": build_breadcrumb(
                    code, row.get("parent_code"), code_lookup, parent_lookup
                ),
                "code_source": "irs",
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[NteeCodesRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "code": r.code,
                "name": r.name,
                "description": r.description,
                "cause_type": r.cause_type,
                "parent_code": r.parent_code,
                "category": r.category,
                "subcategory": r.subcategory,
                "cause_breadcrumb": r.cause_breadcrumb,
                "code_source": r.code_source,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load NTEE codes parquet into cause_ntee"
    )
    parser.add_argument(
        "--file", type=Path, help="Path to parquet (default: latest in data/gold/)"
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = NteeCodesPipeline(path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

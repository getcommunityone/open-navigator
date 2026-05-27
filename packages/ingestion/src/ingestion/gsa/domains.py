#!/usr/bin/env python3
"""GSA .gov domains pipeline: load cached CSV into bronze.bronze_gov_domains.

Ported from load_gsa_domains_to_postgres.py to the core_lib
DataSourcePipeline contract.

Data source: cisagov/dotgov-data (https://github.com/cisagov/dotgov-data),
downloaded by scripts/datasources/gsa/download_gsa_domains.py into
data/cache/gsa/dotgov_domains_*.csv.

Usage:
    python -m scripts.datasources.gsa.domains_pipeline
    python scripts/datasources/gsa/domains_pipeline.py --truncate
    python scripts/datasources/gsa/domains_pipeline.py \\
        --file data/cache/gsa/dotgov_domains_20260507.csv --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/gsa")

# Known approximate bounds for .gov domain counts (cisagov/dotgov-data)
EXPECTED_MIN = 5_000
EXPECTED_MAX = 15_000


def find_latest_csv() -> Path:
    csvs = sorted(CACHE_DIR.glob("dotgov_domains_*.csv"), reverse=True)
    if not csvs:
        raise FileNotFoundError(
            f"No cached GSA CSV found in {CACHE_DIR}. "
            "Run download_gsa_domains.py first."
        )
    return csvs[0]


def _safe_str(val: str | None, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


class DomainRow(RawRow):
    """One .gov domain row, validated before upsert."""

    domain_name: str = Field(min_length=1, max_length=255)
    domain_type: str | None = Field(default=None, max_length=50)
    agency: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=2)
    security_contact: str | None = Field(default=None, max_length=255)


# Pre-migration: the legacy table used to live at public.bronze_bronze_gov_domains.
# Move it under bronze schema and rename if present.
_MIGRATE_SQL = text(
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'bronze_bronze_gov_domains'
        ) THEN
            CREATE SCHEMA IF NOT EXISTS bronze;
            ALTER TABLE public.bronze_bronze_gov_domains SET SCHEMA bronze;
            ALTER TABLE bronze.bronze_bronze_gov_domains RENAME TO bronze_gov_domains;
        END IF;
    END
    $$;
    """
)

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_gov_domains (
        domain_name         VARCHAR(255) PRIMARY KEY,
        domain_type         VARCHAR(50),
        agency              VARCHAR(255),
        organization        VARCHAR(255),
        city                VARCHAR(100),
        state               VARCHAR(2),
        security_contact    VARCHAR(255),
        ingestion_date      TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bgd_domain_type ON bronze.bronze_gov_domains(domain_type)"),
    text("CREATE INDEX IF NOT EXISTS idx_bgd_state       ON bronze.bronze_gov_domains(state)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_gov_domains")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_gov_domains
        (domain_name, domain_type, agency, organization, city, state, security_contact)
    VALUES
        (:domain_name, :domain_type, :agency, :organization, :city, :state, :security_contact)
    ON CONFLICT (domain_name) DO UPDATE SET
        domain_type      = EXCLUDED.domain_type,
        agency           = EXCLUDED.agency,
        organization     = EXCLUDED.organization,
        city             = EXCLUDED.city,
        state            = EXCLUDED.state,
        security_contact = EXCLUDED.security_contact,
        ingestion_date   = NOW()
    """
)


class GsaDomainsPipeline(DataSourcePipeline[DomainRow]):
    source = "gsa_domains"
    batch_size = 5_000
    row_schema = DomainRow

    def __init__(self, *, csv_path: Path | None = None, limit: int | None = None):
        self._csv_path = csv_path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._csv_path or find_latest_csv()
        emitted = 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            # Normalize headers to snake_case lower
            reader.fieldnames = [
                (h or "").strip().lower().replace(" ", "_") for h in (reader.fieldnames or [])
            ]
            for row in reader:
                if self._limit is not None and emitted >= self._limit:
                    return
                domain_name = _safe_str(row.get("domain_name"), 255)
                if not domain_name:
                    continue
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": domain_name.lower(),
                    "domain_name": domain_name,
                    "domain_type": _safe_str(row.get("domain_type"), 50),
                    "agency": _safe_str(row.get("organization_name"), 255),
                    "organization": _safe_str(row.get("suborganization_name"), 255),
                    "city": _safe_str(row.get("city"), 100),
                    "state": _safe_str(row.get("state"), 2),
                    "security_contact": _safe_str(row.get("security_contact_email"), 255),
                }
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[DomainRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "domain_name": r.domain_name,
                "domain_type": r.domain_type,
                "agency": r.agency,
                "organization": r.organization,
                "city": r.city,
                "state": r.state,
                "security_contact": r.security_contact,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_MIGRATE_SQL)
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached GSA .gov domain CSV into bronze.bronze_gov_domains"
    )
    parser.add_argument("--file", type=Path, help="Path to CSV (default: latest in data/cache/gsa/)")
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = GsaDomainsPipeline(csv_path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

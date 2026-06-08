"""Load jurisdiction-grain civic documents into bronze.

Upserts the curated ``registry.REGISTRY`` (comprehensive plans / frameworks,
zoning ordinances, ordinance codes, zoning maps) into
``bronze.bronze_jurisdiction_document``. Each document's full registry entry is
kept verbatim in a ``raw`` JSONB column; the frequently-queried fields are also
flattened into typed columns so downstream dbt staging has a stable surface.

Follows the bronze-loader pattern of ``ingestion.grants_gov.bronze`` (typed
bronze table + raw JSONB, typed-column UPSERT, ``--dry-run`` / ``--truncate`` /
``--bootstrap`` flags, DSN via ``core_lib.db`` — DEV target only).

A document is keyed by (jurisdiction_id, url_sha256): the same plan can be
re-registered idempotently, and one jurisdiction can own many documents.

Usage:
    export DATABASE_URL=postgresql://postgres:password@localhost:5433/open_navigator
    python -m ingestion.jurisdiction_documents.bronze            # upsert the registry
    python -m ingestion.jurisdiction_documents.bronze --dry-run  # show rows, no writes
    python -m ingestion.jurisdiction_documents.bronze --truncate # replace the table
    python -m ingestion.jurisdiction_documents.bronze --bootstrap# create empty table only

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import asdict
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging

from .registry import DOCUMENT_TYPES, REGISTRY, JurisdictionDocument

TABLE = "bronze.bronze_jurisdiction_document"


# --- DDL (each statement as a SEPARATE text(); never multiple per text()) ----

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_document (
        jurisdiction_id  TEXT NOT NULL,
        url_sha256       VARCHAR(64) NOT NULL,
        document_url     TEXT NOT NULL,
        document_type    VARCHAR(64),
        title            TEXT,
        adopted_date     DATE,
        source           VARCHAR(128),
        raw              JSONB,
        ingestion_date   TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (jurisdiction_id, url_sha256)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bjd_jurisdiction "
        "ON bronze.bronze_jurisdiction_document(jurisdiction_id)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bjd_document_type "
        "ON bronze.bronze_jurisdiction_document(document_type)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_jurisdiction_document")

_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_jurisdiction_document (
        jurisdiction_id, url_sha256, document_url, document_type,
        title, adopted_date, source, raw
    ) VALUES (
        :jurisdiction_id, :url_sha256, :document_url, :document_type,
        :title, :adopted_date, :source, CAST(:raw AS JSONB)
    )
    ON CONFLICT (jurisdiction_id, url_sha256) DO UPDATE SET
        document_url   = EXCLUDED.document_url,
        document_type  = EXCLUDED.document_type,
        title          = EXCLUDED.title,
        adopted_date   = EXCLUDED.adopted_date,
        source         = EXCLUDED.source,
        raw            = EXCLUDED.raw,
        ingestion_date = NOW()
    """
)


# --- shaping -----------------------------------------------------------------


def url_sha256(url: str) -> str:
    """Stable 64-char hex digest of the document URL (the per-doc key part)."""
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def to_record(doc: JurisdictionDocument) -> dict[str, Any]:
    """Turn one registry entry into a bronze row dict."""
    if doc.document_type not in DOCUMENT_TYPES:
        raise ValueError(
            f"Unknown document_type {doc.document_type!r} for "
            f"{doc.jurisdiction_id} — add it to registry.DOCUMENT_TYPES "
            "(and the dbt accepted-values test) first."
        )
    raw = asdict(doc)
    raw["adopted_date"] = doc.adopted_date.isoformat() if doc.adopted_date else None
    return {
        "jurisdiction_id": doc.jurisdiction_id,
        "url_sha256": url_sha256(doc.document_url),
        "document_url": doc.document_url.strip(),
        "document_type": doc.document_type,
        "title": doc.title.strip() or None,
        "adopted_date": doc.adopted_date,
        "source": doc.source,
        "raw": json.dumps(raw),
    }


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


async def _log_summary(session: AsyncSession, loaded: int) -> None:
    total = (await session.execute(text(f"SELECT COUNT(*) FROM {TABLE}"))).scalar_one()
    logger.success(
        "Upserted {:,} document(s) → {} (table total: {:,})", loaded, TABLE, total
    )
    breakdown = await session.execute(
        text(
            f"""
            SELECT COALESCE(document_type, '(unknown)') AS t, COUNT(*) AS cnt
            FROM {TABLE}
            GROUP BY t
            ORDER BY cnt DESC
            """
        )
    )
    logger.info("Breakdown by document_type:")
    for doc_type, cnt in breakdown.all():
        logger.info("  {}: {:,}", doc_type, cnt)


async def bootstrap(truncate: bool = False) -> None:
    """Create the empty bronze table (and indexes) without loading data."""
    async with async_session() as session:
        await _prepare_target(session, truncate)
    logger.success("Bootstrapped {} (schema only).", TABLE)


async def load_to_postgres(
    records: list[dict[str, Any]],
    truncate: bool = False,
) -> int:
    if not records:
        logger.warning("No records to load.")
        return 0
    async with async_session() as session:
        await _prepare_target(session, truncate)
        await session.execute(_INSERT_SQL, records)
        await _log_summary(session, len(records))
    return len(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Load curated jurisdiction-grain civic documents into "
            "bronze.bronze_jurisdiction_document"
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the prepared rows, no DB writes",
    )
    parser.add_argument(
        "--truncate", action="store_true", help="TRUNCATE table before loading"
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the empty bronze table (schema only) and exit",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    logger.info("=" * 70)
    logger.info("Jurisdiction documents → {}", TABLE)
    logger.info("=" * 70)

    if args.bootstrap:
        await bootstrap(truncate=args.truncate)
        return 0

    records = [to_record(doc) for doc in REGISTRY]
    logger.info("Prepared {:,} registry record(s)", len(records))

    if args.dry_run:
        logger.warning("DRY RUN — showing rows, not writing to database:")
        for r in records:
            logger.info(
                "  {} | {} | {!r} | {}",
                r["jurisdiction_id"],
                r["document_type"],
                r["title"],
                r["document_url"],
            )
        return 0

    await load_to_postgres(records, truncate=args.truncate)

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

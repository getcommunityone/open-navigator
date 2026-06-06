"""Load Grants.gov federal opportunities into bronze.

Searches the Grants.gov Search2 API for grant *opportunities* (open / forecasted
federal funding) and upserts them into ``bronze.bronze_grants_gov_opportunity``
(PK = ``opportunity_id``). Each opportunity's full Search2 record is kept verbatim
in a ``raw`` JSONB column for fidelity; a handful of frequently-queried fields are
also flattened into typed columns so downstream dbt staging has a stable surface.

This is the bronze-loader companion to ``ingestion.grants_gov.client``, following
the same pattern as ``ingestion.data_gov.organizations`` and
``ingestion.google_data_commons.bronze`` (typed bronze table + raw JSONB,
typed-column UPSERT, ``--dry-run`` / ``--truncate`` / ``--limit`` / ``--bootstrap``
flags, DSN via ``core_lib.db`` — DEV target only).

NOTE: these are PROSPECTIVE opportunities, a distinct entity from the historical
IRS 990 Schedule I grants in ``public.grant``. Keep them separate downstream.

No API key is required.

Usage:
    export DATABASE_URL=postgresql://postgres:password@localhost:5433/open_navigator
    python -m ingestion.grants_gov.bronze                       # all open opportunities
    python -m ingestion.grants_gov.bronze --keyword "oral health"
    python -m ingestion.grants_gov.bronze --statuses "forecasted|posted|closed"
    python -m ingestion.grants_gov.bronze --limit 200
    python -m ingestion.grants_gov.bronze --truncate
    python -m ingestion.grants_gov.bronze --dry-run
    python -m ingestion.grants_gov.bronze --bootstrap           # create empty table only

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging

from .client import DATA_SOURCE, DEFAULT_STATUSES, GrantsGovClient

TABLE = "bronze.bronze_grants_gov_opportunity"


# --- DDL (each statement as a SEPARATE text(); never multiple per text()) ----

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_grants_gov_opportunity (
        opportunity_id      VARCHAR(32) PRIMARY KEY,
        opportunity_number  VARCHAR(255),
        title               TEXT,
        agency_code         VARCHAR(64),
        agency_name         TEXT,
        open_date           DATE,
        close_date          DATE,
        opp_status          VARCHAR(32),
        doc_type            VARCHAR(64),
        aln                 VARCHAR(32),
        data_source         VARCHAR(64),
        raw                 JSONB,
        ingestion_date      TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bggo_status "
        "ON bronze.bronze_grants_gov_opportunity(opp_status)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bggo_close_date "
        "ON bronze.bronze_grants_gov_opportunity(close_date)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bggo_agency "
        "ON bronze.bronze_grants_gov_opportunity(agency_code)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_grants_gov_opportunity")

_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_grants_gov_opportunity (
        opportunity_id, opportunity_number, title,
        agency_code, agency_name, open_date, close_date,
        opp_status, doc_type, aln, data_source, raw
    ) VALUES (
        :opportunity_id, :opportunity_number, :title,
        :agency_code, :agency_name, :open_date, :close_date,
        :opp_status, :doc_type, :aln, :data_source, CAST(:raw AS JSONB)
    )
    ON CONFLICT (opportunity_id) DO UPDATE SET
        opportunity_number = EXCLUDED.opportunity_number,
        title              = EXCLUDED.title,
        agency_code        = EXCLUDED.agency_code,
        agency_name        = EXCLUDED.agency_name,
        open_date          = EXCLUDED.open_date,
        close_date         = EXCLUDED.close_date,
        opp_status         = EXCLUDED.opp_status,
        doc_type           = EXCLUDED.doc_type,
        aln                = EXCLUDED.aln,
        data_source        = EXCLUDED.data_source,
        raw                = EXCLUDED.raw,
        ingestion_date     = NOW()
    """
)


# --- parsing helpers ---------------------------------------------------------


def _safe_str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def parse_grants_date(val: Any) -> date | None:
    """Parse a Grants.gov date (``MM/DD/YYYY``, sometimes ISO) into a date."""
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # ISO timestamp fallback (e.g. "2024-10-15T00:00:00Z").
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        logger.debug("Unparseable Grants.gov date: {!r}", val)
        return None


def _first_aln(hit: dict[str, Any]) -> str | None:
    """Pull the first Assistance Listing Number from a hit.

    ``cfdaList`` is normally a list of strings ("93.110") but older/demo payloads
    used a list of ``{"cfdaNumber": ...}`` dicts — handle both.
    """
    cfda = hit.get("cfdaList") or hit.get("alnist") or []
    if not isinstance(cfda, list) or not cfda:
        return None
    first = cfda[0]
    if isinstance(first, dict):
        return _safe_str(first.get("cfdaNumber") or first.get("aln"), 32)
    return _safe_str(first, 32)


def to_record(hit: dict[str, Any]) -> dict[str, Any]:
    """Turn one Search2 ``oppHits`` record into a bronze row dict.

    Field names follow the current Search2 contract (``number``, ``title``,
    ``agency``/``agencyCode``, ``openDate``, ``closeDate``, ``oppStatus``,
    ``docType``) with fallbacks to the legacy demo names so a stale payload still
    lands. The full record is preserved in ``raw`` regardless.
    """
    return {
        "opportunity_id": _safe_str(hit.get("id"), 32),
        "opportunity_number": _safe_str(
            hit.get("number") or hit.get("opportunityNumber"), 255
        ),
        "title": _safe_str(hit.get("title") or hit.get("opportunityTitle")),
        "agency_code": _safe_str(hit.get("agencyCode"), 64),
        "agency_name": _safe_str(hit.get("agency") or hit.get("agencyName")),
        "open_date": parse_grants_date(hit.get("openDate")),
        "close_date": parse_grants_date(hit.get("closeDate")),
        "opp_status": _safe_str(
            hit.get("oppStatus") or hit.get("opportunityStatus"), 32
        ),
        "doc_type": _safe_str(hit.get("docType"), 64),
        "aln": _first_aln(hit),
        "data_source": DATA_SOURCE,
        "raw": json.dumps(hit),
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
        "Upserted {:,} opportunities → {} (table total: {:,})", loaded, TABLE, total
    )
    breakdown = await session.execute(
        text(
            f"""
            SELECT COALESCE(opp_status, '(unknown)') AS s, COUNT(*) AS cnt
            FROM {TABLE}
            GROUP BY s
            ORDER BY cnt DESC
            """
        )
    )
    logger.info("Breakdown by opp_status:")
    for status, cnt in breakdown.all():
        logger.info("  {}: {:,}", status, cnt)
    open_now = (
        await session.execute(
            text(
                f"SELECT COUNT(*) FROM {TABLE} "
                "WHERE close_date IS NOT NULL AND close_date >= CURRENT_DATE"
            )
        )
    ).scalar_one()
    logger.info("Opportunities still open (close_date >= today): {:,}", open_now)


async def bootstrap(truncate: bool = False) -> None:
    """Create the empty bronze table (and indexes) without fetching data."""
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
            "Load Grants.gov federal opportunities into "
            "bronze.bronze_grants_gov_opportunity"
        )
    )
    parser.add_argument(
        "--keyword", help="Free-text search keyword (default: all open opportunities)"
    )
    parser.add_argument(
        "--funding-category",
        help="Pipe-separated funding category codes (e.g. 'HL' for Health)",
    )
    parser.add_argument(
        "--agency", help="Pipe-separated agency codes (e.g. 'HHS|HHS-NIH')"
    )
    parser.add_argument(
        "--statuses",
        default=DEFAULT_STATUSES,
        help=f"Pipe-separated opp statuses (default: '{DEFAULT_STATUSES}')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max opportunities to fetch (default: all matching)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + parse, show first records, no DB writes",
    )
    parser.add_argument(
        "--truncate", action="store_true", help="TRUNCATE table before loading"
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the empty bronze table (schema only) and exit",
    )
    parser.add_argument(
        "--staging", action="store_true", help="Use the Grants.gov staging API"
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    logger.info("=" * 70)
    logger.info("Grants.gov opportunities → {}", TABLE)
    logger.info("=" * 70)

    if args.bootstrap:
        await bootstrap(truncate=args.truncate)
        return 0

    client = GrantsGovClient(use_staging=args.staging)
    hits = list(
        client.iter_opportunities(
            keyword=args.keyword,
            funding_categories=args.funding_category,
            agencies=args.agency,
            opp_statuses=args.statuses,
            max_results=args.limit,
        )
    )
    logger.info("Fetched {:,} opportunity hits", len(hits))

    # De-dupe by opportunity id (a keyword sweep can surface the same id twice).
    records: dict[str, dict[str, Any]] = {}
    for hit in hits:
        rec = to_record(hit)
        if rec["opportunity_id"]:
            records[rec["opportunity_id"]] = rec
    record_list = list(records.values())
    logger.info("Prepared {:,} unique bronze records", len(record_list))

    if args.dry_run:
        logger.warning("DRY RUN — showing first 3 records, not writing to database:")
        for r in record_list[:3]:
            logger.info(
                "  id={} number={} status={} close={} title={!r}",
                r["opportunity_id"],
                r["opportunity_number"],
                r["opp_status"],
                r["close_date"],
                r["title"],
            )
        return 0

    await load_to_postgres(record_list, truncate=args.truncate)

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

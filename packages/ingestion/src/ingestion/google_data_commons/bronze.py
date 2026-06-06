"""Load Google Data Commons jurisdiction enrichment into bronze.

Reads jurisdiction FIPS codes from ``intermediate.int_jurisdictions`` (counties
by default), fetches demographic / economic / education / health / housing
statistics from the Google Data Commons v2 API, and upserts them into
``bronze.bronze_jurisdiction_datacommons`` (PK = ``fips_code``). The full set of
statistical variables is also stored verbatim in a ``stats`` JSONB column for
raw fidelity.

This is the bronze-loader companion to ``ingestion.google_data_commons.client``,
following the same pattern as ``ingestion.data_gov.organizations`` (typed bronze
table, typed-column UPSERT, ``--dry-run`` / ``--truncate`` / ``--limit`` flags,
DSN via ``core_lib.db`` — DEV target only).

Requires a free Data Commons API key (https://apikeys.datacommons.org/) passed
via the ``DATA_COMMONS_API_KEY`` env var or ``--api-key``.

Usage:
    export DATA_COMMONS_API_KEY=your_key_here
    export DATABASE_URL=postgresql://postgres:password@localhost:5433/open_navigator
    python -m ingestion.google_data_commons.bronze
    python -m ingestion.google_data_commons.bronze --limit 50
    python -m ingestion.google_data_commons.bronze --fips 01073,01089,01097
    python -m ingestion.google_data_commons.bronze --truncate
    python -m ingestion.google_data_commons.bronze --dry-run
    python -m ingestion.google_data_commons.bronze --bootstrap   # create empty table only

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging

from .client import DataCommonsClient

TABLE = "bronze.bronze_jurisdiction_datacommons"

# How many places to request per v2 observation call.
DEFAULT_CHUNK_SIZE = 200

# Map the Data Commons statistical variables onto friendly typed columns. The
# full {statvar: value} map is also persisted to the `stats` JSONB column.
VAR_COLUMNS: dict[str, str] = {
    "Count_Person": "population",
    "Count_Person_Male": "population_male",
    "Count_Person_Female": "population_female",
    "Median_Age_Person": "median_age",
    "Count_Person_WhiteAlone": "population_white",
    "Count_Person_BlackOrAfricanAmericanAlone": "population_black",
    "Count_Person_HispanicOrLatino": "population_hispanic",
    "Count_Person_AsianAlone": "population_asian",
    "Median_Income_Household": "median_household_income",
    "UnemploymentRate_Person": "unemployment_rate",
    "Count_Person_BelowPovertyLevelInThePast12Months": "poverty_count",
    "Median_Earnings_Person": "median_earnings",
    "Count_Person_EducationalAttainmentBachelorsDegreeOrHigher": "bachelors_or_higher",
    "Count_Person_EducationalAttainmentHighSchoolGraduateOrHigher": "hs_grad_or_higher",
    "Count_Person_WithHealthInsurance": "insured_count",
    "Count_Person_NoHealthInsurance": "uninsured_count",
    "Median_Price_SoldHome": "median_home_price",
    "Count_HousingUnit": "housing_units",
    "Count_Household": "households",
}

# Ordered list of friendly column names (for DDL + UPSERT generation).
_TYPED_COLS = list(VAR_COLUMNS.values())


# --- DDL (each statement as a SEPARATE text(); never multiple per text()) ----

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_datacommons (
        fips_code               VARCHAR(7) PRIMARY KEY,
        dcid                    VARCHAR(32),
        population              DOUBLE PRECISION,
        population_male         DOUBLE PRECISION,
        population_female       DOUBLE PRECISION,
        median_age              DOUBLE PRECISION,
        population_white        DOUBLE PRECISION,
        population_black        DOUBLE PRECISION,
        population_hispanic     DOUBLE PRECISION,
        population_asian        DOUBLE PRECISION,
        median_household_income DOUBLE PRECISION,
        unemployment_rate       DOUBLE PRECISION,
        poverty_count           DOUBLE PRECISION,
        median_earnings         DOUBLE PRECISION,
        bachelors_or_higher     DOUBLE PRECISION,
        hs_grad_or_higher       DOUBLE PRECISION,
        insured_count           DOUBLE PRECISION,
        uninsured_count         DOUBLE PRECISION,
        median_home_price       DOUBLE PRECISION,
        housing_units           DOUBLE PRECISION,
        households              DOUBLE PRECISION,
        data_source             VARCHAR(64),
        stats                   JSONB,
        retrieval_date          TIMESTAMP,
        ingestion_date          TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bjdc_population "
        "ON bronze.bronze_jurisdiction_datacommons(population)"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bjdc_median_income "
        "ON bronze.bronze_jurisdiction_datacommons(median_household_income)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_jurisdiction_datacommons")


def _build_insert_sql() -> Any:
    cols = ["fips_code", "dcid", *_TYPED_COLS, "data_source", "stats", "retrieval_date"]
    placeholders = []
    for c in cols:
        if c == "stats":
            placeholders.append("CAST(:stats AS JSONB)")
        else:
            placeholders.append(f":{c}")
    updates = ",\n        ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != "fips_code"
    )
    return text(
        f"""
        INSERT INTO {TABLE} ({", ".join(cols)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT (fips_code) DO UPDATE SET
        {updates},
        ingestion_date = NOW()
        """
    )


_INSERT_SQL = _build_insert_sql()


def to_record(enriched: dict[str, Any]) -> dict[str, Any]:
    """Turn one enrich_jurisdiction(_bulk) dict into a bronze row dict."""
    stats = {
        statvar: enriched.get(statvar)
        for statvar in VAR_COLUMNS
        if enriched.get(statvar) is not None
    }
    record: dict[str, Any] = {
        "fips_code": enriched["fips_code"],
        "dcid": enriched.get("dcid"),
        "data_source": enriched.get("data_source"),
        "stats": json.dumps(stats),
        "retrieval_date": enriched.get("retrieval_date"),
    }
    for statvar, col in VAR_COLUMNS.items():
        record[col] = enriched.get(statvar)
    return record


async def _fetch_fips_from_db(
    jurisdiction_type: str, limit: int | None
) -> list[str]:
    """Read distinct FIPS codes from intermediate.int_jurisdictions."""
    # Counties use 5-digit FIPS; place/city use 7-digit. Filter to the matching
    # width so we don't issue malformed DCIDs.
    width = 7 if jurisdiction_type in ("place", "city", "municipality") else 5
    sql = text(
        """
        SELECT DISTINCT fips_code
        FROM intermediate.int_jurisdictions
        WHERE jurisdiction_type = :jtype
          AND fips_code IS NOT NULL
          AND length(fips_code) = :width
        ORDER BY fips_code
        """
    )
    async with async_session() as session:
        rows = (
            await session.execute(sql, {"jtype": jurisdiction_type, "width": width})
        ).scalars().all()
    fips = [str(r) for r in rows]
    if limit:
        fips = fips[:limit]
    logger.info(
        "Resolved {:,} '{}' FIPS codes from intermediate.int_jurisdictions",
        len(fips),
        jurisdiction_type,
    )
    return fips


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
        "Upserted {:,} jurisdictions → {} (table total: {:,})", loaded, TABLE, total
    )
    with_pop = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE population IS NOT NULL")
        )
    ).scalar_one()
    logger.info("Jurisdictions with a population value: {:,} / {:,}", with_pop, total)


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
            "Load Google Data Commons jurisdiction enrichment into "
            "bronze.bronze_jurisdiction_datacommons"
        )
    )
    parser.add_argument(
        "--api-key", help="Data Commons API key (overrides DATA_COMMONS_API_KEY)"
    )
    parser.add_argument(
        "--fips",
        help="Comma-separated FIPS codes to enrich (overrides DB lookup)",
    )
    parser.add_argument(
        "--jurisdiction-type",
        default="county",
        help="int_jurisdictions.jurisdiction_type to enrich (default: county)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of jurisdictions")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Places per API call (default: {DEFAULT_CHUNK_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve FIPS + target schema, no network fetch, no DB writes",
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
    logger.info("Google Data Commons → {}", TABLE)
    logger.info("=" * 70)

    if args.bootstrap:
        await bootstrap(truncate=args.truncate)
        return 0

    # Resolve the FIPS list (explicit override or DB lookup).
    if args.fips:
        fips_codes = [f.strip() for f in args.fips.split(",") if f.strip()]
        if args.limit:
            fips_codes = fips_codes[: args.limit]
        logger.info("Using {:,} FIPS codes from --fips", len(fips_codes))
    else:
        fips_codes = await _fetch_fips_from_db(args.jurisdiction_type, args.limit)

    if not fips_codes:
        logger.error("No FIPS codes resolved — nothing to do.")
        return 1

    if args.dry_run:
        logger.warning("DRY RUN — no network fetch, no DB writes.")
        logger.info("Would enrich {:,} jurisdictions, e.g. {}", len(fips_codes), fips_codes[:5])
        logger.info(
            "Would fetch {} statistical variables → {} typed columns + stats JSONB",
            len(VAR_COLUMNS),
            len(_TYPED_COLS),
        )
        logger.info("Target table: {}", TABLE)
        return 0

    api_key = args.api_key or os.getenv("DATA_COMMONS_API_KEY")
    if not api_key:
        logger.error(
            "Missing API key. Set DATA_COMMONS_API_KEY or pass --api-key. "
            "Get a free key at https://apikeys.datacommons.org/ "
            "(use --bootstrap to create the empty table without a key)."
        )
        return 2

    client = DataCommonsClient(api_key=api_key)

    all_records: list[dict[str, Any]] = []
    chunk = max(1, args.chunk_size)
    for i in range(0, len(fips_codes), chunk):
        batch = fips_codes[i : i + chunk]
        logger.info(
            "Fetching observations for {:,}–{:,} of {:,}",
            i + 1,
            i + len(batch),
            len(fips_codes),
        )
        enriched_rows = client.enrich_jurisdictions_bulk(batch)
        all_records.extend(
            to_record(r) for r in enriched_rows if not r.get("error")
        )

    logger.info("Prepared {:,} bronze records", len(all_records))
    await load_to_postgres(all_records, truncate=args.truncate)

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

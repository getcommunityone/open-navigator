"""
Regenerate rpt_bill_map_aggregate from OpenStates PostgreSQL database.

This populates the rpt_bill_map_aggregate table with data for ALL 50 states
from the local OpenStates PostgreSQL database.
"""
import asyncio
import asyncpg
from loguru import logger
import os
from datetime import datetime

def _normalize_pg_url(url: str) -> str:
    """Normalize legacy ``postgres://`` schemes to ``postgresql://`` for asyncpg."""
    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        return "postgresql://" + cleaned[len("postgres://") :]
    return cleaned


def _resolve_openstates_db_url() -> str:
    url = os.getenv("OPENSTATES_DATABASE_URL", "").strip()
    if url:
        return _normalize_pg_url(url)
    return "postgresql://postgres:password@localhost:5433/openstates"


def _resolve_open_navigator_db_url() -> str:
    for var in (
        "OPEN_NAVIGATOR_DATABASE_URL",
        "NEON_DATABASE_URL_DEV",
        "NEON_DATABASE_URL",
        "DATABASE_URL",
    ):
        val = os.getenv(var, "").strip()
        if val:
            return _normalize_pg_url(val)
    return "postgresql://postgres:password@localhost:5433/open_navigator"


# Database connections (kept at module level for compatibility; resolved dynamically at runtime)
OPENSTATES_DB = _resolve_openstates_db_url()
OPEN_NAVIGATOR_DB = _resolve_open_navigator_db_url()


_AGGREGATE_QUERY = """
    SELECT
        SUBSTRING(s.jurisdiction_id FROM 'ocd-jurisdiction/country:us/state:([a-z]{2})') as state,
        COUNT(*) as total_bills,
        (ARRAY_AGG(
            jsonb_build_object(
                'title', b.title,
                'bill_number', b.identifier,
                'latest_action_date', b.latest_action_date
            )
            ORDER BY b.latest_action_date DESC NULLS LAST
        ))[1:3] as sample_bills
    FROM opencivicdata_bill b
    JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
    WHERE s.jurisdiction_id LIKE 'ocd-jurisdiction/country:us/state:%'
    GROUP BY state
    ORDER BY state
"""


async def regenerate_map_aggregates(
    openstates_db_url: str | None = None,
    navigator_db_url: str | None = None,
):
    """Generate bills map aggregates for all 50 states from PostgreSQL."""

    logger.info("Regenerating rpt_bill_map_aggregate from OpenStates PostgreSQL...")

    openstates_dsn = _normalize_pg_url(openstates_db_url) if openstates_db_url else _resolve_openstates_db_url()
    navigator_dsn = _normalize_pg_url(navigator_db_url) if navigator_db_url else _resolve_open_navigator_db_url()

    openstates_conn = None
    navigator_conn = None

    try:
        openstates_conn = await asyncpg.connect(openstates_dsn)
        navigator_conn = await asyncpg.connect(navigator_dsn)

        # Get all states with bill counts
        logger.info("Querying OpenStates database for all states...")
        states_data = await openstates_conn.fetch(_AGGREGATE_QUERY)
        logger.info(f"✅ Found {len(states_data)} states")
        
        # Clear existing aggregates
        await navigator_conn.execute("TRUNCATE TABLE rpt_bill_map_aggregate")
        logger.info("🗑️  Cleared existing aggregates")
        
        # Insert new aggregates
        insert_query = """
            INSERT INTO rpt_bill_map_aggregate (
                state_code, topic, total_bills,
                type_bill, type_resolution, type_concurrent_resolution,
                type_joint_resolution, type_constitutional_amendment,
                status_enacted, status_failed, status_pending,
                primary_type, primary_status, map_category,
                sample_bills, last_updated
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        """
        
        for row in states_data:
            state = row['state'].upper()
            total = row['total_bills']
            samples = row['sample_bills']
            
            # Categorize by bill count
            if total > 50000:
                category = 'very_high'
            elif total > 20000:
                category = 'high'
            elif total > 10000:
                category = 'medium'
            else:
                category = 'low'
            
            await navigator_conn.execute(
                insert_query,
                state, 'all', total,
                0, 0, 0, 0, 0,  # type counts (would need more queries)
                0, 0, total,     # status: all pending for now
                'bill', 'pending', category,
                samples, datetime.now()
            )
            
            logger.info(f"  ✅ {state}: {total:,} bills ({category})")
        
        logger.info(f"\n✅ Successfully populated rpt_bill_map_aggregate with {len(states_data)} states!")
        
    finally:
        if navigator_conn is not None:
            try:
                await navigator_conn.close()
            finally:
                if openstates_conn is not None:
                    await openstates_conn.close()
        elif openstates_conn is not None:
            await openstates_conn.close()


if __name__ == "__main__":
    asyncio.run(regenerate_map_aggregates())

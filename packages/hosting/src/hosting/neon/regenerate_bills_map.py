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

# Database connections
OPENSTATES_DB = os.getenv("OPENSTATES_DATABASE_URL", "postgresql://postgres:password@localhost:5433/openstates")
OPEN_NAVIGATOR_DB = os.getenv("NEON_DATABASE_URL_DEV", "postgresql://postgres:password@localhost:5433/open_navigator")


async def regenerate_map_aggregates():
    """Generate bills map aggregates for all 50 states from PostgreSQL."""
    
    logger.info("🔄 Regenerating rpt_bill_map_aggregate from OpenStates PostgreSQL...")
    
    # Connect to both databases
    openstates_conn = await asyncpg.connect(OPENSTATES_DB)
    navigator_conn = await asyncpg.connect(OPEN_NAVIGATOR_DB)
    
    try:
        # Get all states with bill counts
        logger.info("📊 Querying OpenStates database for all states...")
        query = """
            SELECT 
                SUBSTRING(s.jurisdiction_id FROM 'ocd-jurisdiction/country:us/state:([a-z]{2})') as state,
                COUNT(*) as total_bills,
                ARRAY_AGG(
                    jsonb_build_object(
                        'title', b.title,
                        'bill_number', b.identifier,
                        'latest_action_date', b.latest_action_date
                    ) 
                    ORDER BY b.latest_action_date DESC
                    LIMIT 3
                ) as sample_bills
            FROM opencivicdata_bill b
            JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
            WHERE s.jurisdiction_id LIKE 'ocd-jurisdiction/country:us/state:%'
            GROUP BY state
            ORDER BY state
        """
        
        states_data = await openstates_conn.fetch(query)
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
        await openstates_conn.close()
        await navigator_conn.close()


if __name__ == "__main__":
    asyncio.run(regenerate_map_aggregates())

"""
Update statistics aggregates from actual database counts
Run this after loading data to refresh stats
"""
import os
import asyncio
from datetime import datetime
from loguru import logger
import asyncpg
from dotenv import load_dotenv

load_dotenv()

# Database configuration
NEON_DATABASE_URL_DEV = os.getenv('NEON_DATABASE_URL_DEV')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL')
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

if not DATABASE_URL:
    raise ValueError("Neither NEON_DATABASE_URL_DEV nor NEON_DATABASE_URL set in environment")

logger.info(f"Using: {'DEV' if NEON_DATABASE_URL_DEV else 'PROD'} database")


async def update_national_stats():
    """Calculate and update national statistics from database"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        logger.info("📊 Calculating national statistics from database...")
        
        # Count jurisdictions by type
        jurisdictions_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_jurisdiction WHERE classification IN ('city', 'county', 'town', 'village')"
        )
        
        school_districts_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_jurisdiction WHERE classification = 'school_district'"
        )
        
        # Count nonprofits
        nonprofits_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_organization"
        )
        
        # Sum financials (handle NULL values)
        financial_stats = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(revenue), 0) as total_revenue,
                COALESCE(SUM(assets), 0) as total_assets
            FROM civic_organization
            WHERE revenue IS NOT NULL OR assets IS NOT NULL
        """)
        
        # Count events
        events_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_event"
        )
        
        # Count contacts
        contacts_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_person"
        )
        
        logger.info(f"  Jurisdictions: {jurisdictions_count:,}")
        logger.info(f"  School Districts: {school_districts_count:,}")
        logger.info(f"  Nonprofits: {nonprofits_count:,}")
        logger.info(f"  Events: {events_count:,}")
        logger.info(f"  Contacts: {contacts_count:,}")
        logger.info(f"  Total Revenue: ${financial_stats['total_revenue']:,.0f}")
        logger.info(f"  Total Assets: ${financial_stats['total_assets']:,.0f}")
        
        # Delete existing national stats and insert new
        await conn.execute("""
            DELETE FROM jurisdiction_state_aggregate 
            WHERE level = 'national' AND state IS NULL
        """)
        
        await conn.execute("""
            INSERT INTO jurisdiction_state_aggregate 
            (level, state, county, city, jurisdictions_count, school_districts_count,
             nonprofits_count, events_count, bills_count, contacts_count, 
             total_revenue, total_assets, last_updated)
            VALUES ('national', NULL, NULL, NULL, $1, $2, $3, $4, 0, $5, $6, $7, $8)
        """, jurisdictions_count, school_districts_count, nonprofits_count, 
             events_count, contacts_count, 
             float(financial_stats['total_revenue']), 
             float(financial_stats['total_assets']),
             datetime.now())
        
        logger.success("✅ National statistics updated!")
        
        # Update state-level stats
        await update_state_stats(conn)
        
    finally:
        await conn.close()


async def update_state_stats(conn):
    """Calculate and update state-level statistics"""
    logger.info("📊 Calculating state-level statistics...")
    
    # Get all states with data
    states = await conn.fetch("""
        SELECT DISTINCT state 
        FROM civic_organization 
        WHERE state IS NOT NULL 
        ORDER BY state
    """)
    
    for state_row in states:
        state = state_row['state']
        logger.info(f"  Processing: {state}")
        
        # Count jurisdictions
        jurisdictions_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_jurisdiction WHERE state = $1 AND classification IN ('city', 'county', 'town', 'village')",
            state
        )
        
        school_districts_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_jurisdiction WHERE state = $1 AND classification = 'school_district'",
            state
        )
        
        # Count nonprofits
        nonprofits_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_organization WHERE state = $1",
            state
        )
        
        # Sum financials
        financial_stats = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(revenue), 0) as total_revenue,
                COALESCE(SUM(assets), 0) as total_assets
            FROM civic_organization
            WHERE state = $1
        """, state)
        
        # Count events
        events_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_event WHERE state = $1",
            state
        )
        
        # Count contacts
        contacts_count = await conn.fetchval(
            "SELECT COUNT(*) FROM civic_person WHERE state = $1",
            state
        )
        
        # Insert/update state stats
        await conn.execute("""
            DELETE FROM jurisdiction_state_aggregate 
            WHERE level = 'state' AND state = $1
        """, state)
        
        await conn.execute("""
            INSERT INTO jurisdiction_state_aggregate 
            (level, state, county, city, jurisdictions_count, school_districts_count,
             nonprofits_count, events_count, bills_count, contacts_count, 
             total_revenue, total_assets, last_updated)
            VALUES ('state', $1, NULL, NULL, $2, $3, $4, $5, 0, $6, $7, $8, $9)
        """, state, jurisdictions_count, school_districts_count, nonprofits_count, 
             events_count, contacts_count,
             float(financial_stats['total_revenue']), 
             float(financial_stats['total_assets']),
             datetime.now())
        
        logger.info(f"    {state}: {nonprofits_count:,} nonprofits, {jurisdictions_count:,} jurisdictions")
    
    logger.success(f"✅ Updated statistics for {len(states)} states")


async def main():
    """Main entry point"""
    logger.info("🚀 Starting statistics update...")
    logger.info("ℹ️  Note: Only calculating state-level stats (no national aggregates)")
    
    # Skip national stats - only update state-level
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await update_state_stats(conn)
    finally:
        await conn.close()
    
    logger.success("🎉 Statistics update completed!")
    
    # Show final stats
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stats = await conn.fetch("SELECT * FROM jurisdiction_state_aggregate ORDER BY level, state")
        logger.info("\n📊 Final Statistics:")
        logger.info("=" * 80)
        for stat in stats:
            location = stat['state'] or 'United States'
            logger.info(f"  {location}: {stat['nonprofits_count']:,} nonprofits, {stat['jurisdictions_count']:,} jurisdictions")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Sync place_geoid and county_fips from bronze to production search table

This script updates organization_nonprofit in the production database
with jurisdiction linking fields from bronze_organizations_nonprofits.

Usage:
    python scripts/datasources/census/sync_nonprofit_jurisdictions.py
"""
import psycopg2
from loguru import logger

# Database connections
BRONZE_CONN = {
    'host': 'localhost',
    'port': 5433,
    'database': 'open_navigator_bronze',
    'user': 'postgres',
    'password': 'password'
}

PROD_CONN = {
    'host': 'localhost',
    'port': 5433,
    'database': 'open_navigator',
    'user': 'postgres',
    'password': 'password'
}


def sync_jurisdictions():
    """Sync jurisdiction fields from bronze to production."""
    
    # Connect to both databases
    bronze_conn = psycopg2.connect(**BRONZE_CONN)
    prod_conn = psycopg2.connect(**PROD_CONN)
    
    bronze_cur = bronze_conn.cursor()
    prod_cur = prod_conn.cursor()
    
    try:
        # Step 1: Add columns to production table if they don't exist
        logger.info("Adding place_geoid and county_fips columns to organization_nonprofit...")
        prod_cur.execute("""
            ALTER TABLE organization_nonprofit 
            ADD COLUMN IF NOT EXISTS place_geoid VARCHAR(7),
            ADD COLUMN IF NOT EXISTS county_fips VARCHAR(5);
        """)
        prod_conn.commit()
        logger.success("Columns added")
        
        # Step 2: Fetch jurisdiction data from bronze
        logger.info("Fetching jurisdiction data from bronze_organizations_nonprofits...")
        bronze_cur.execute("""
            SELECT 
                ein,
                place_geoid,
                county_fips
            FROM bronze_organizations_nonprofits
            WHERE ein IS NOT NULL
              AND (place_geoid IS NOT NULL OR county_fips IS NOT NULL)
        """)
        
        records = bronze_cur.fetchall()
        logger.info(f"Found {len(records):,} nonprofits with jurisdiction data")
        
        # Step 3: Update production table in batches
        logger.info("Updating organization_nonprofit...")
        batch_size = 10000
        updated = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            # Build update query
            prod_cur.execute("""
                CREATE TEMP TABLE temp_jurisdictions (
                    ein VARCHAR(10),
                    place_geoid VARCHAR(7),
                    county_fips VARCHAR(5)
                ) ON COMMIT DROP
            """)
            
            # Insert batch into temp table
            prod_cur.executemany("""
                INSERT INTO temp_jurisdictions (ein, place_geoid, county_fips)
                VALUES (%s, %s, %s)
            """, batch)
            
            # Update from temp table
            prod_cur.execute("""
                UPDATE organization_nonprofit AS o
                SET place_geoid = t.place_geoid,
                    county_fips = t.county_fips
                FROM temp_jurisdictions AS t
                WHERE o.ein = t.ein
            """)
            
            updated += prod_cur.rowcount
            prod_conn.commit()
            
            if (i + batch_size) % 50000 == 0:
                logger.info(f"Updated {updated:,} records...")
        
        logger.success(f"✅ Updated {updated:,} nonprofit records with jurisdiction data")
        
        # Step 4: Create indexes
        logger.info("Creating indexes...")
        prod_cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_search_place_geoid 
            ON organization_nonprofit(place_geoid) 
            WHERE place_geoid IS NOT NULL
        """)
        prod_cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_search_county_fips 
            ON organization_nonprofit(county_fips) 
            WHERE county_fips IS NOT NULL
        """)
        prod_conn.commit()
        logger.success("Indexes created")
        
        # Step 5: Report statistics
        prod_cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(place_geoid) as with_place,
                COUNT(county_fips) as with_county,
                ROUND(100.0 * COUNT(place_geoid) / COUNT(*), 1) as pct_place,
                ROUND(100.0 * COUNT(county_fips) / COUNT(*), 1) as pct_county
            FROM organization_nonprofit
        """)
        
        stats = prod_cur.fetchone()
        logger.info("\n" + "="*70)
        logger.info("Final Statistics")
        logger.info("="*70)
        logger.info(f"Total nonprofits:      {stats[0]:,}")
        logger.info(f"With place_geoid:      {stats[1]:,} ({stats[3]}%)")
        logger.info(f"With county_fips:      {stats[2]:,} ({stats[4]}%)")
        
        # Verify Tuscaloosa
        prod_cur.execute("""
            SELECT COUNT(*) 
            FROM organization_nonprofit 
            WHERE place_geoid = '0177256'
        """)
        tuscaloosa_count = prod_cur.fetchone()[0]
        logger.info(f"\nTuscaloosa city nonprofits: {tuscaloosa_count:,}")
        
        logger.success("\n✅ Jurisdiction sync complete!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        bronze_conn.rollback()
        prod_conn.rollback()
        raise
    
    finally:
        bronze_cur.close()
        bronze_conn.close()
        prod_cur.close()
        prod_conn.close()


if __name__ == "__main__":
    sync_jurisdictions()

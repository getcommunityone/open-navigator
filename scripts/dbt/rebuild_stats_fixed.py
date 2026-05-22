"""
Rebuild jurisdiction_state_aggregate with correct city and county counts

FIXES:
1. City nonprofit counts - use actual city count, not state total
2. County event counts - map cities to counties
"""
import psycopg2
from loguru import logger

BRONZE_DB = "postgresql://postgres:password@localhost:5433/open_navigator"
PROD_DB = "postgresql://postgres:password@localhost:5433/open_navigator"

def rebuild_stats():
    """Rebuild jurisdiction_state_aggregate with corrected aggregations"""
    
    logger.info("🔄 Rebuilding jurisdiction_state_aggregate with fixed counts...")
    
    bronze_conn = psycopg2.connect(BRONZE_DB)
    prod_conn = psycopg2.connect(PROD_DB)
    
    try:
        bronze_cur = bronze_conn.cursor()
        prod_cur = prod_conn.cursor()

        # Keep all "bronze" tables in the bronze schema of open_navigator.
        bronze_cur.execute("SET search_path TO bronze, public")
        
        logger.info("📊 Step 1: Drop and recreate jurisdiction_state_aggregate in bronze...")
        bronze_cur.execute("DROP TABLE IF EXISTS jurisdiction_state_aggregate CASCADE")
        bronze_cur.execute("""
            CREATE TABLE jurisdiction_state_aggregate (
                id SERIAL PRIMARY KEY,
                level VARCHAR(20) NOT NULL,
                state_code VARCHAR(2),
                state VARCHAR(50),
                county VARCHAR(100),
                city VARCHAR(100),
                jurisdictions_count INTEGER DEFAULT 0,
                school_districts_count INTEGER DEFAULT 0,
                nonprofits_count INTEGER DEFAULT 0,
                events_count INTEGER DEFAULT 0,
                bills_count INTEGER DEFAULT 0,
                contacts_count INTEGER DEFAULT 0,
                total_revenue BIGINT DEFAULT 0,
                total_assets BIGINT DEFAULT 0,
                trending_causes JSONB,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(level, state_code, county, city)
            )
        """)
        bronze_conn.commit()
        
        logger.info("📊 Step 2: Insert NATIONAL stats...")
        bronze_cur.execute("""
            INSERT INTO jurisdiction_state_aggregate (
                level, state_code, state, county, city,
                nonprofits_count, events_count,
                total_revenue, total_assets
            )
            SELECT
                'national',
                NULL, NULL, NULL, NULL,
                COUNT(*)::INTEGER,
                (SELECT COUNT(*) FROM bronze_events_localview)::INTEGER,
                COALESCE(SUM(irs_revenue_amt), 0),
                COALESCE(SUM(irs_asset_amt), 0)
            FROM bronze_organizations_nonprofits
        """)
        bronze_conn.commit()
        logger.info(f"   ✅ National level inserted")
        
        logger.info("📊 Step 3: Insert STATE stats...")
        bronze_cur.execute("""
            INSERT INTO jurisdiction_state_aggregate (
                level, state_code, state, county, city,
                nonprofits_count, events_count,
                total_revenue, total_assets
            )
            SELECT
                'state',
                state_code,
                NULL,
                NULL,
                NULL,
                COUNT(*)::INTEGER,
                COALESCE((SELECT COUNT(*) FROM bronze_events_localview WHERE bronze_events_localview.state_code = np.state_code), 0)::INTEGER,
                COALESCE(SUM(irs_revenue_amt), 0),
                COALESCE(SUM(irs_asset_amt), 0)
            FROM bronze_organizations_nonprofits np
            WHERE state_code IS NOT NULL
            GROUP BY state_code
        """)
        bronze_conn.commit()
        logger.info(f"   ✅ State level inserted")
        
        logger.info("📊 Step 4: Insert COUNTY stats...")
        bronze_cur.execute("""
            INSERT INTO jurisdiction_state_aggregate (
                level, state_code, state, county, city,
                nonprofits_count, events_count,
                total_revenue, total_assets
            )
            SELECT
                'county',
                np.state_code,
                NULL,
                np.census_county_name,
                NULL,
                COUNT(*)::INTEGER as nonprofits_count,
                COALESCE((
                    SELECT COUNT(*)
                    FROM bronze_events_localview e
                    JOIN (
                        SELECT DISTINCT ON (state_code, city)
                            state_code, city, census_county_name
                        FROM bronze_organizations_nonprofits
                        WHERE city IS NOT NULL AND census_county_name IS NOT NULL
                        ORDER BY state_code, city, census_county_name
                    ) c2c ON e.city = c2c.city AND e.state_code = c2c.state_code
                    WHERE c2c.census_county_name = np.census_county_name
                      AND c2c.state_code = np.state_code
                ), 0)::INTEGER as events_count,
                COALESCE(SUM(irs_revenue_amt), 0),
                COALESCE(SUM(irs_asset_amt), 0)
            FROM bronze_organizations_nonprofits np
            WHERE state_code IS NOT NULL AND census_county_name IS NOT NULL
            GROUP BY np.state_code, np.census_county_name
        """)
        bronze_conn.commit()
        logger.info(f"   ✅ County level inserted")
        
        logger.info("📊 Step 5: Insert CITY stats...")
        bronze_cur.execute("""
            INSERT INTO jurisdiction_state_aggregate (
                level, state_code, state, county, city,
                nonprofits_count, events_count,
                total_revenue, total_assets
            )
            SELECT
                'city',
                e.state_code,
                NULL,
                NULL,
                e.city,
                COALESCE(np_city.nonprofits_count, 0)::INTEGER,
                e.events_count::INTEGER,
                COALESCE(np_city.total_revenue, 0),
                COALESCE(np_city.total_assets, 0)
            FROM (
                SELECT state_code, city, COUNT(*) as events_count
                FROM bronze_events
                WHERE city IS NOT NULL AND state_code IS NOT NULL
                GROUP BY state_code, city
            ) e
            LEFT JOIN (
                SELECT 
                    state_code,
                    city,
                    COUNT(*) as nonprofits_count,
                    COALESCE(SUM(irs_revenue_amt), 0) as total_revenue,
                    COALESCE(SUM(irs_asset_amt), 0) as total_assets
                FROM bronze_organizations_nonprofits
                WHERE city IS NOT NULL AND city != ''
                GROUP BY state_code, city
            ) np_city ON e.city = np_city.city AND e.state_code = np_city.state_code
        """)
        bronze_conn.commit()
        logger.info(f"   ✅ City level inserted")
        
        # Get counts
        bronze_cur.execute("SELECT COUNT(*), COUNT(DISTINCT level) FROM jurisdiction_state_aggregate")
        total, levels = bronze_cur.fetchone()
        logger.info(f"   📊 Total rows: {total:,}, Levels: {levels}")
        
        logger.info("📊 Step 6: Copy to production database...")
        
        # Close connections before pg_dump
        bronze_conn.close()
        prod_conn.close()
        
        import subprocess
        result = subprocess.run(
            [
                "bash",
                "-c",
                "PGPASSWORD=password pg_dump -h localhost -p 5433 -U postgres -d open_navigator -t bronze.jurisdiction_state_aggregate --no-owner --no-acl "
                "| PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator 2>&1",
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0 and "already exists" not in result.stderr:
            logger.error(f"pg_dump error: {result.stderr}")
        else:
            logger.info("   ✅ Table copied to production")
        
        logger.info("✅ Stats aggregates rebuilt successfully!")
        
        # Reconnect to show summary
        prod_conn = psycopg2.connect(PROD_DB)
        prod_cur = prod_conn.cursor()
        prod_cur.execute("""
            SELECT 
                'Boston city' as location,
                nonprofits_count,
                events_count
            FROM jurisdiction_state_aggregate
            WHERE level = 'city' AND city = 'Boston' AND state_code = 'MA'
            UNION ALL
            SELECT 
                'Suffolk County',
                nonprofits_count,
                events_count
            FROM jurisdiction_state_aggregate
            WHERE level = 'county' AND county = 'Suffolk County' AND state_code = 'MA'
            UNION ALL
            SELECT 
                'Massachusetts state',
                nonprofits_count,
                events_count
            FROM jurisdiction_state_aggregate
            WHERE level = 'state' AND state_code = 'MA'
        """)
        
        logger.info("\n📊 Verification - Boston counts:")
        for row in prod_cur.fetchall():
            logger.info(f"   {row[0]:25} {row[1]:>10,} nonprofits, {row[2]:>6,} events")
        
        prod_conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        try:
            if bronze_conn and not bronze_conn.closed:
                bronze_conn.close()
            if prod_conn and not prod_conn.closed:
                prod_conn.close()
        except:
            pass


if __name__ == "__main__":
    rebuild_stats()

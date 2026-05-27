#!/usr/bin/env python3
"""
Migrate school districts from jurisdictions_details_schools to organization_location

This ensures all NCES school districts are searchable in the unified organization_location table.
"""
import psycopg2
from psycopg2.extras import execute_values
from loguru import logger
import json

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "open_navigator",
    "user": "postgres",
    "password": "password"
}


def get_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def migrate_schools_to_organizations():
    """Migrate all school districts to organization_location."""
    logger.info("=" * 80)
    logger.info("Migrating School Districts to organization_location")
    logger.info("=" * 80)
    
    conn = get_connection()
    
    try:
        with conn.cursor() as cur:
            # Check how many school districts exist
            cur.execute("SELECT COUNT(*) FROM jurisdictions_details_schools")
            total_schools = cur.fetchone()[0]
            logger.info(f"Found {total_schools:,} school districts in jurisdictions_details_schools")
            
            # Check if any already exist in organization_location
            cur.execute("""
                SELECT COUNT(*) 
                FROM organization_location 
                WHERE organization_type = 'school_district'
            """)
            existing = cur.fetchone()[0]
            logger.info(f"Found {existing:,} existing school districts in organization_location")
            
            if existing > 0:
                logger.warning("School districts already exist. Clearing them first...")
                cur.execute("DELETE FROM organization_location WHERE organization_type = 'school_district'")
                conn.commit()
                logger.info("Cleared existing school districts")
            
            # Fetch all school districts
            logger.info("Fetching school district data...")
            cur.execute("""
                SELECT 
                    nces_id,
                    district_name,
                    state_code,
                    street_address,
                    city,
                    zip,
                    phone,
                    website,
                    district_type,
                    num_schools,
                    school_year
                FROM jurisdictions_details_schools
                ORDER BY state_code, district_name
            """)
            
            schools = cur.fetchall()
            logger.info(f"Retrieved {len(schools):,} school districts")
            
            # Prepare records for insertion
            records = []
            for school in schools:
                nces_id, name, state, address, city, zip_code, phone, website, \
                    district_type, num_schools, school_year = school
                
                # Build additional_info JSON
                additional_info = {
                    'nces_id': nces_id,
                    'district_type': district_type,
                    'num_schools': num_schools,
                    'school_year': school_year
                }
                
                # Set website to NULL if it's "NOT AVAILABLE"
                clean_website = None if website and website.upper() == 'NOT AVAILABLE' else website
                
                record = (
                    nces_id,  # source_id
                    name,  # name
                    'school_district',  # organization_type
                    address,  # address
                    city,  # city
                    state,  # state (2-letter code)
                    zip_code,  # zip
                    None,  # county
                    None,  # latitude (not in NCES data)
                    None,  # longitude (not in NCES data)
                    phone,  # telephone
                    clean_website,  # website
                    'NCES',  # data_source
                    'jurisdictions_details_schools',  # source_dataset
                    json.dumps(additional_info)  # additional_info
                )
                records.append(record)
            
            # Insert in batches
            logger.info("Inserting school districts into organization_location...")
            batch_size = 1000
            
            insert_query = """
                INSERT INTO organization_location (
                    source_id, name, organization_type, address, city, state, zip,
                    county, latitude, longitude, telephone, website,
                    data_source, source_dataset, additional_info
                ) VALUES %s
            """
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                execute_values(cur, insert_query, batch)
                conn.commit()
                logger.info(f"Inserted batch {i//batch_size + 1}/{(len(records)-1)//batch_size + 1} ({len(batch):,} records)")
            
            logger.success(f"✅ Migrated {len(records):,} school districts")
            
            # Verify
            cur.execute("""
                SELECT COUNT(*) 
                FROM organization_location 
                WHERE organization_type = 'school_district'
            """)
            final_count = cur.fetchone()[0]
            
            logger.info(f"\nVerification: {final_count:,} school districts now in organization_location")
            
            # Show breakdown by state
            cur.execute("""
                SELECT state, COUNT(*) as count
                FROM organization_location
                WHERE organization_type = 'school_district'
                GROUP BY state
                ORDER BY count DESC
                LIMIT 10
            """)
            
            logger.info("\nTop 10 states by school district count:")
            for state, count in cur.fetchall():
                logger.info(f"  {state}: {count:,}")
    
    finally:
        conn.close()
    
    logger.info("\n" + "=" * 80)
    logger.info("Migration complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    migrate_schools_to_organizations()

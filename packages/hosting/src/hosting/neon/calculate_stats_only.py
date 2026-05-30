"""
Calculate aggregate statistics WITHOUT loading individual records
Only stores summary stats in jurisdiction_state_aggregate table
"""
import os
import asyncio
from pathlib import Path
from datetime import datetime
from loguru import logger
import asyncpg
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Database configuration
NEON_DATABASE_URL_DEV = os.getenv('NEON_DATABASE_URL_DEV')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL')
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

if not DATABASE_URL:
    raise ValueError("Neither NEON_DATABASE_URL_DEV nor NEON_DATABASE_URL set in environment")

logger.info(f"Using: {'DEV' if NEON_DATABASE_URL_DEV else 'PROD'} database")

# Paths
SCRIPT_DIR = Path(__file__).parent
# Up from neon/ → hosting/ → src/ → hosting(pkg)/ → packages/ → repo root
PROJECT_ROOT = Path(__file__).resolve().parents[5]
GOLD_DIR = PROJECT_ROOT / "data" / "gold"


async def calculate_national_stats_from_files():
    """Calculate national statistics directly from parquet files"""
    logger.info("📊 Calculating national statistics from parquet files...")
    
    stats = {
        'jurisdictions_count': 0,
        'school_districts_count': 0,
        'nonprofits_count': 0,
        'total_revenue': 0,
        'total_assets': 0,
    }
    
    # Count jurisdictions
    for pattern in ['jurisdictions_cities.parquet', 'jurisdictions_counties.parquet', 
                   'jurisdictions_townships.parquet']:
        file_path = GOLD_DIR / pattern
        if file_path.exists():
            df = pd.read_parquet(file_path)
            count = len(df)
            stats['jurisdictions_count'] += count
            logger.info(f"  {pattern}: {count:,} records")
    
    # Count school districts
    sd_file = GOLD_DIR / 'jurisdictions_school_districts.parquet'
    if sd_file.exists():
        df = pd.read_parquet(sd_file)
        stats['school_districts_count'] = len(df)
        logger.info(f"  School districts: {stats['school_districts_count']:,}")
    
    # Count nonprofits (without loading into database)
    np_file = GOLD_DIR / 'nonprofits_organizations.parquet'
    if np_file.exists():
        logger.info("  Reading nonprofits file (this may take a moment)...")
        df = pd.read_parquet(np_file)
        stats['nonprofits_count'] = len(df)
        
        # Calculate financial totals
        if 'form_990_total_revenue' in df.columns:
            stats['total_revenue'] = int(df['form_990_total_revenue'].fillna(0).sum())
        if 'form_990_total_assets' in df.columns:
            stats['total_assets'] = int(df['form_990_total_assets'].fillna(0).sum())
        
        logger.info(f"  Nonprofits: {stats['nonprofits_count']:,}")
        logger.info(f"  Total Revenue: ${stats['total_revenue']:,}")
        logger.info(f"  Total Assets: ${stats['total_assets']:,}")
    
    return stats


async def calculate_state_stats_from_files(state_code):
    """Calculate state statistics from parquet files"""
    logger.info(f"📊 Calculating {state_code} statistics from parquet files...")
    
    stats = {
        'jurisdictions_count': 0,
        'school_districts_count': 0,
        'nonprofits_count': 0,
        'total_revenue': 0,
        'total_assets': 0,
    }
    
    # Count jurisdictions for this state
    for pattern in ['jurisdictions_cities.parquet', 'jurisdictions_counties.parquet', 
                   'jurisdictions_townships.parquet']:
        file_path = GOLD_DIR / pattern
        if file_path.exists():
            df = pd.read_parquet(file_path)
            state_df = df[df['state'].str.upper() == state_code.upper()]
            stats['jurisdictions_count'] += len(state_df)
    
    # Count school districts
    sd_file = GOLD_DIR / 'jurisdictions_school_districts.parquet'
    if sd_file.exists():
        df = pd.read_parquet(sd_file)
        state_df = df[df['state'].str.upper() == state_code.upper()]
        stats['school_districts_count'] = len(state_df)
    
    # Count nonprofits for this state
    np_file = GOLD_DIR / 'nonprofits_organizations.parquet'
    if np_file.exists():
        df = pd.read_parquet(np_file)
        state_df = df[df['state'].str.upper() == state_code.upper()]
        stats['nonprofits_count'] = len(state_df)
        
        if 'form_990_total_revenue' in state_df.columns:
            stats['total_revenue'] = int(state_df['form_990_total_revenue'].fillna(0).sum())
        if 'form_990_total_assets' in state_df.columns:
            stats['total_assets'] = int(state_df['form_990_total_assets'].fillna(0).sum())
    
    return stats


async def main():
    """Calculate and store only aggregate statistics"""
    logger.info("🚀 Calculating aggregate statistics (not loading individual records)")
    logger.info("=" * 80)
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Calculate national stats
        national = await calculate_national_stats_from_files()
        
        # Store national stats
        await conn.execute("""
            DELETE FROM jurisdiction_state_aggregate WHERE level = 'national'
        """)
        
        await conn.execute("""
            INSERT INTO jurisdiction_state_aggregate 
            (level, state, county, city, jurisdictions_count, school_districts_count,
             nonprofits_count, events_count, bills_count, contacts_count, 
             total_revenue, total_assets, last_updated)
            VALUES ('national', NULL, NULL, NULL, $1, $2, $3, 0, 0, 0, $4, $5, $6)
        """, national['jurisdictions_count'], national['school_districts_count'],
             national['nonprofits_count'], national['total_revenue'],
             national['total_assets'], datetime.now())
        
        logger.success(f"✅ National stats: {national['nonprofits_count']:,} nonprofits, {national['jurisdictions_count']:,} jurisdictions")
        
        # Calculate state-level stats for states with data
        logger.info("\n📊 Calculating state-level statistics...")
        
        # Get unique states from nonprofits file
        np_file = GOLD_DIR / 'nonprofits_organizations.parquet'
        if np_file.exists():
            df = pd.read_parquet(np_file, columns=['state'])
            states = df['state'].dropna().unique()
            
            for state in sorted(states):
                state_stats = await calculate_state_stats_from_files(state)
                
                # Only store if has data
                if state_stats['nonprofits_count'] > 0:
                    await conn.execute("""
                        DELETE FROM jurisdiction_state_aggregate WHERE level = 'state' AND state = $1
                    """, state)
                    
                    await conn.execute("""
                        INSERT INTO jurisdiction_state_aggregate 
                        (level, state, county, city, jurisdictions_count, school_districts_count,
                         nonprofits_count, events_count, bills_count, contacts_count, 
                         total_revenue, total_assets, last_updated)
                        VALUES ('state', $1, NULL, NULL, $2, $3, $4, 0, 0, 0, $5, $6, $7)
                    """, state, state_stats['jurisdictions_count'], state_stats['school_districts_count'],
                         state_stats['nonprofits_count'], state_stats['total_revenue'],
                         state_stats['total_assets'], datetime.now())
                    
                    logger.info(f"  {state}: {state_stats['nonprofits_count']:,} nonprofits")
        
        logger.success("\n🎉 Statistics calculation completed!")
        logger.info("\n💡 Note: Individual nonprofit records NOT loaded to database")
        logger.info("   Only aggregate statistics are stored in jurisdiction_state_aggregate table")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

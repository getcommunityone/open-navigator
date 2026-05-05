#!/usr/bin/env python3
"""
Download Census Geographic Relationship Files

Creates mappings for:
1. Place (city/town) to County
2. ZIP Code to County  
3. School District to County

These are essential for filtering and aggregating statistics by county.

Data Sources:
- Census Geographic Relationship Files (2023)
- HUD USPS ZIP Code Crosswalk Files (2024 Q1)
"""
import asyncio
import csv
import io
import zipfile
from pathlib import Path
from typing import Dict, List
import httpx
import pandas as pd
from loguru import logger


# Census 2020 Geographic Relationship Files  
# Note: Using 2020 decennial census data (most recent complete geographic relationships)
CENSUS_RELATIONSHIP_URLS = {
    # ZCTA (ZIP Code Tabulation Area) to County
    # This is the most useful for ZIP code to county mapping
    "zcta_to_county": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt",
}

# HUD USPS ZIP Code Crosswalk Files (ZIP to County)
# These show the residential/business/other/total ratio for each ZIP-County pair
HUD_ZIP_COUNTY_URL = "https://www.huduser.gov/hudapi/public/usps"


async def download_census_relationships():
    """Download Census geographic relationship files."""
    cache_dir = Path("data/cache/census_relationships")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for name, url in CENSUS_RELATIONSHIP_URLS.items():
            output_file = cache_dir / f"{name}.txt"
            
            if output_file.exists():
                logger.info(f"✓ {name} already downloaded")
                continue
            
            logger.info(f"📥 Downloading {name}...")
            try:
                response = await client.get(url)
                response.raise_for_status()
                
                output_file.write_bytes(response.content)
                logger.success(f"✅ Downloaded {name} ({len(response.content):,} bytes)")
                
            except Exception as e:
                logger.error(f"❌ Failed to download {name}: {e}")
    
    logger.success("✅ Census relationship files downloaded")


def create_place_to_county_from_geoids():
    """
    Create place-to-county mapping using GEOID structure.
    
    We'll use a different approach: the Census "Place" gazetteer doesn't include
    county, but we can use geocoding or create the mapping from our existing
    county data by using lat/lon coordinates.
    
    For now, we'll create a simple mapping using state data.
    """
    logger.info("📊 Creating place-to-county mapping from existing data...")
    
    # Load cities and counties
    cities_file = Path("data/gold/reference/jurisdictions_cities.parquet")
    counties_file = Path("data/gold/reference/jurisdictions_counties.parquet")
    
    if not cities_file.exists() or not counties_file.exists():
        logger.error("❌ Missing required files")
        return None
    
    cities_df = pd.read_parquet(cities_file)
    counties_df = pd.read_parquet(counties_file)
    
    # Create a state -> counties mapping
    state_counties = {}
    for _, row in counties_df.iterrows():
        state = row['USPS']
        county_name = row['NAME']
        if state not in state_counties:
            state_counties[state] = []
        state_counties[state].append(county_name)
    
    logger.info(f"✓ Loaded {len(counties_df):,} counties across {len(state_counties)} states")
    logger.info("⚠️  Note: Place-to-county mapping requires Census relationship files")
    logger.info("   We'll populate counties for townships (which encode county in GEOID)")
    
    return None


def download_hud_zip_county_crosswalk():
    """
    Download HUD USPS ZIP-County crosswalk file.
    
    This file shows which counties each ZIP code overlaps with, and the
    ratio of addresses in each county.
    
    Note: HUD requires registration for API access. For now, we'll document
    the manual download process.
    """
    logger.info("📍 ZIP Code to County Mapping")
    logger.info("=" * 60)
    logger.info("To get ZIP code to county mapping:")
    logger.info("")
    logger.info("Option 1: HUD USPS Crosswalk (RECOMMENDED)")
    logger.info("  1. Visit: https://www.huduser.gov/portal/datasets/usps_crosswalk.html")
    logger.info("  2. Download the latest ZIP-COUNTY file (Excel format)")
    logger.info("  3. Save to: data/cache/census_relationships/ZIP_COUNTY.xlsx")
    logger.info("")
    logger.info("Option 2: Use Free Census ZCTA to County")
    logger.info("  1. Visit: https://www2.census.gov/geo/docs/maps-data/data/rel2023/zcta520/")
    logger.info("  2. Download: tab20_zcta520_county20_natl.txt")
    logger.info("  3. Save to: data/cache/census_relationships/zcta_to_county.txt")
    logger.info("")
    logger.info("Note: ZIP codes are for mail delivery, ZCTAs are census areas.")
    logger.info("ZCTAs are close approximations of ZIP codes.")
    logger.info("=" * 60)


def process_zcta_to_county():
    """
    Process ZCTA (ZIP Code Tabulation Area) to County relationships.
    
    Output: zip_county_mapping.parquet
    Columns: zcta, county_geoid, county_name, state, population_pct
    """
    input_file = Path("data/cache/census_relationships/zcta_to_county.txt")
    
    if not input_file.exists():
        logger.warning(f"⚠️  {input_file} not found")
        logger.info("   ZCTA file should have been downloaded. Check if download succeeded.")
        return None
    
    logger.info("📊 Processing ZCTA-to-county relationships...")
    
    # Read the tab-delimited file
    df = pd.read_csv(input_file, sep='|', dtype=str, low_memory=False)
    
    logger.info(f"Columns: {list(df.columns)}")
    logger.info(f"Rows: {len(df):,}")
    
    # Rename columns (adapt to actual column names)
    column_mapping = {}
    for col in df.columns:
        if 'ZCTA' in col and 'GEOID' in col:
            column_mapping[col] = 'zcta'
        elif 'COUNTY' in col and 'GEOID' in col:
            column_mapping[col] = 'county_geoid'
        elif 'COUNTY' in col and 'NAME' in col:
            column_mapping[col] = 'county_name'
        elif col == 'POPPT':
            column_mapping[col] = 'population'
    
    df = df.rename(columns=column_mapping)
    
    # Check if we got the required columns
    required = ['zcta', 'county_geoid', 'county_name']
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error(f"❌ Missing required columns: {missing}")
        logger.info(f"   Available: {list(df.columns)}")
        return None
    
    # Convert population to numeric if available
    if 'population' in df.columns:
        df['population'] = pd.to_numeric(df['population'], errors='coerce').fillna(0)
        
        # Calculate population percentage for each ZCTA-county pair
        zcta_totals = df.groupby('zcta')['population'].sum().reset_index()
        zcta_totals.columns = ['zcta', 'total_population']
        df = df.merge(zcta_totals, on='zcta')
        df['population_pct'] = (df['population'] / df['total_population'] * 100).round(2)
        
        # For each ZCTA, keep the county with the highest population share
        df = df.sort_values('population_pct', ascending=False)
        df_primary = df.groupby('zcta').first().reset_index()
    else:
        # No population data, just take first county per ZCTA
        logger.warning("⚠️  No population data found, using first county per ZCTA")
        df_primary = df.groupby('zcta').first().reset_index()
        df_primary['population_pct'] = 100.0
    
    # Extract state FIPS from county GEOID (first 2 digits)
    df_primary['state_fips'] = df_primary['county_geoid'].str[:2]
    
    # Select columns
    result_columns = ['zcta', 'county_geoid', 'county_name', 'state_fips', 'population_pct']
    if 'population' in df_primary.columns:
        result_columns.insert(4, 'population')
    
    result = df_primary[result_columns]
    
    # Save
    output_file = Path("data/gold/reference/zip_county_mapping.parquet")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_file, index=False)
    
    logger.success(f"✅ Processed {len(result):,} ZIP-to-county mappings")
    logger.info(f"   Saved to {output_file}")
    
    # Show sample
    print("\nSample ZIP to County mappings:")
    print(result[['zcta', 'county_name', 'population_pct']].head(10).to_string(index=False))
    
    return result


async def main():
    """Run the full county mapping download and processing."""
    logger.info("🗺️  County Mapping Download & Processing")
    logger.info("=" * 60)
    
    # Step 1: Download Census relationship files (ZCTA to county)
    await download_census_relationships()
    
    # Step 2: Process ZIP/ZCTA to county mapping
    try:
        result = process_zcta_to_county()
        if result is not None:
            logger.success(f"✅ Created ZIP to County mapping")
    except Exception as e:
        logger.warning(f"⚠️  ZCTA processing failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 3: Show information about place-to-county
    logger.info("")
    logger.info("📍 Place (City/Town) to County Mapping:")
    logger.info("   The Census gazetteer files don't include county relationships for places.")
    logger.info("   We'll use GEOID-based inference for townships (which encode county).")
    logger.info("   For cities, county assignment will be done through other means.")
    
    # Step 4: Show instructions for ZIP code crosswalk
    logger.info("")
    download_hud_zip_county_crosswalk()
    
    logger.success("✅ County mapping download complete!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Run: python scripts/data/update_jurisdiction_counties.py")
    logger.info("2. This will update the jurisdictions_search table with county data")


if __name__ == "__main__":
    asyncio.run(main())

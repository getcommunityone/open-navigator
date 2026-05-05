"""
Download American Community Survey (ACS) Data to D Drive

This script demonstrates downloading comprehensive demographic data from the
U.S. Census Bureau's American Community Survey and storing it on the D drive.

Usage:
    # Download all key tables for all U.S. counties to D drive
    python download_acs_to_d_drive.py --geography county --state *
    
    # Download California county data only
    python download_acs_to_d_drive.py --geography county --state 06
    
    # Download city-level data for Texas
    python download_acs_to_d_drive.py --geography place --state 48
    
    # List all available tables
    python download_acs_to_d_drive.py --list-tables
"""
import asyncio
import argparse
from pathlib import Path
from typing import Optional
import sys

# Add project root to path for imports
# __file__ = .../examples/download_acs_to_d_drive.py
# parent = .../examples
# parent.parent = .../open-navigator (project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.datasources.census.acs_ingestion import ACSDataIngestion
from loguru import logger


async def download_comprehensive_acs_data(
    data_dir: Path,
    geography: str = "county",
    state: str = "*",
    tables: Optional[list] = None
):
    """
    Download comprehensive ACS demographic data.
    
    Args:
        data_dir: Directory to store data (e.g., D:/open-navigator-data/acs)
        geography: Geographic level (county, place, tract)
        state: State FIPS code (* for all states)
        tables: List of table codes (None = download key tables)
    """
    logger.info("=" * 80)
    logger.info("ACS Data Download to D Drive")
    logger.info("=" * 80)
    logger.info(f"Data Directory: {data_dir.absolute()}")
    logger.info(f"Geography: {geography}")
    logger.info(f"State: {state}")
    logger.info("=" * 80)
    
    # Initialize ACS ingestion with D drive path
    acs = ACSDataIngestion(data_dir=data_dir)
    
    # Default key tables if none specified
    if tables is None:
        tables = [
            # Demographics
            "B01001",  # Sex by Age
            "B02001",  # Race
            "B03002",  # Hispanic or Latino Origin
            
            # Economics  
            "B19013",  # Median Household Income
            "B17001",  # Poverty Status
            "B23025",  # Employment Status
            
            # Health Insurance (CRITICAL for oral health policy!)
            "B27001",  # Health Insurance Coverage by Age
            "B27010",  # Health Insurance Coverage (Under 19)
            
            # Education
            "B15003",  # Educational Attainment
            "B14001",  # School Enrollment
            
            # Housing
            "B25077",  # Median Home Value
            "B25064",  # Median Gross Rent
        ]
    
    logger.info(f"Downloading {len(tables)} tables...")
    
    # Download each table
    results = {}
    for i, table in enumerate(tables, 1):
        try:
            table_name = acs.ACS_TABLES.get(table, "Unknown")
            logger.info(f"\n[{i}/{len(tables)}] Downloading {table}: {table_name}")
            
            df = await acs.download_acs_data_api(
                table=table,
                geography=geography,
                state=state
            )
            
            results[table] = df
            logger.success(f"✅ {table}: {len(df)} records")
            
            # Rate limiting - be nice to Census API
            await asyncio.sleep(1.5)
            
        except Exception as e:
            logger.error(f"❌ Failed to download {table}: {e}")
            continue
    
    logger.info("\n" + "=" * 80)
    logger.info("Download Complete!")
    logger.info("=" * 80)
    logger.info(f"Successfully downloaded: {len(results)}/{len(tables)} tables")
    logger.info(f"Data saved to: {data_dir.absolute()}")
    
    # Print summary
    print("\n📊 Downloaded Tables Summary:\n")
    for table_code, df in results.items():
        table_name = acs.ACS_TABLES.get(table_code, "Unknown")
        file_path = data_dir / f"{table_code}_{geography}_{state}_2022.parquet"
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        
        print(f"  {table_code}: {table_name}")
        print(f"    Records: {len(df):,}")
        print(f"    File: {file_path.name}")
        print(f"    Size: {file_size_mb:.2f} MB")
        print()
    
    # Calculate total storage used
    total_size_mb = sum(
        (data_dir / f"{t}_{geography}_{state}_2022.parquet").stat().st_size / (1024 * 1024)
        for t in results.keys()
    )
    
    logger.info(f"Total storage used: {total_size_mb:.2f} MB")
    
    return results


async def download_health_insurance_focus(data_dir: Path, state: str = "*"):
    """
    Download health insurance focused tables for oral health policy analysis.
    
    This downloads detailed health insurance coverage data by age, type, and
    geographic area - critical for analyzing dental coverage gaps.
    """
    logger.info("=" * 80)
    logger.info("Health Insurance Data Download (Oral Health Policy Focus)")
    logger.info("=" * 80)
    
    acs = ACSDataIngestion(data_dir=data_dir)
    
    # Health insurance tables
    health_tables = {
        "B27001": "Health Insurance Coverage Status by Age",
        "B27010": "Health Insurance Coverage by Age (Under 19) ⭐ CRITICAL",
        "C27007": "Medicaid/Means-Tested Public Coverage",
        "B18101": "Disability Status (impacts dental needs)",
        "B17001": "Poverty Status (Medicaid eligibility)",
    }
    
    logger.info(f"Downloading {len(health_tables)} health insurance tables...")
    
    results = {}
    for table_code, description in health_tables.items():
        try:
            logger.info(f"\nDownloading: {table_code} - {description}")
            
            df = await acs.download_acs_data_api(
                table=table_code,
                geography="county",
                state=state
            )
            
            results[table_code] = df
            logger.success(f"✅ Downloaded {len(df)} counties")
            
            await asyncio.sleep(1.5)
            
        except Exception as e:
            logger.error(f"❌ Failed: {e}")
            continue
    
    logger.success(f"\n✅ Downloaded {len(results)} health insurance tables to {data_dir}")
    
    return results


async def download_by_state_batch(data_dir: Path, states: list, geography: str = "county"):
    """
    Download data for multiple states in batch.
    
    This is more efficient than downloading all states at once if you only
    need data for specific states.
    
    Args:
        data_dir: Storage directory
        states: List of state FIPS codes (e.g., ["06", "48", "36"])
        geography: Geographic level
    """
    acs = ACSDataIngestion(data_dir=data_dir)
    
    logger.info(f"Downloading data for {len(states)} states: {states}")
    
    # Key tables
    tables = ["B19013", "B27010", "B17001"]  # Income, child insurance, poverty
    
    for state_fips in states:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing State: {state_fips}")
        logger.info(f"{'=' * 60}")
        
        for table in tables:
            try:
                df = await acs.download_acs_data_api(table, geography, state_fips)
                logger.success(f"✅ {table}: {len(df)} records")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ {table}: {e}")
                continue


def verify_d_drive_setup(data_dir: Path):
    """
    Verify that D drive is accessible and has enough space.
    """
    logger.info("Verifying D drive setup...")
    
    # Check if directory exists
    if not data_dir.exists():
        logger.warning(f"Directory does not exist: {data_dir}")
        logger.info("Creating directory...")
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.success(f"✅ Created: {data_dir}")
    
    # Check write permissions
    test_file = data_dir / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
        logger.success("✅ Write permissions OK")
    except Exception as e:
        logger.error(f"❌ Cannot write to directory: {e}")
        return False
    
    # Check available space
    import shutil
    stat = shutil.disk_usage(data_dir)
    free_gb = stat.free / (1024**3)
    
    logger.info(f"Available space: {free_gb:.2f} GB")
    
    if free_gb < 5:
        logger.warning(f"⚠️ Low disk space: {free_gb:.2f} GB available")
        logger.warning("Consider freeing up space or using a different drive")
        return False
    
    logger.success(f"✅ D drive setup verified: {data_dir}")
    return True


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Download ACS demographic data to D drive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all key tables for all U.S. counties to D drive (WSL)
  python download_acs_to_d_drive.py --geography county --state *
  
  # Download California counties only
  python download_acs_to_d_drive.py --geography county --state 06
  
  # Download health insurance data only
  python download_acs_to_d_drive.py --health-insurance-only
  
  # Download for multiple states
  python download_acs_to_d_drive.py --states 06 48 36  # CA, TX, NY
  
  # Use Windows native path (if running in Windows, not WSL)
  python download_acs_to_d_drive.py --data-dir D:/open-navigator-data/acs
  
  # Use custom data directory
  python download_acs_to_d_drive.py --data-dir /mnt/d/acs-data
  
  # List available tables
  python download_acs_to_d_drive.py --list-tables
        """
    )
    
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("/mnt/d/open-navigator-data/acs"),
        help="Directory to store ACS data (default: /mnt/d/open-navigator-data/acs for WSL, D:/open-navigator-data/acs for Windows)"
    )
    
    parser.add_argument(
        "--geography",
        choices=["county", "place", "tract", "cousub"],
        default="county",
        help="Geographic level (default: county)"
    )
    
    parser.add_argument(
        "--state",
        default="*",
        help="State FIPS code or * for all states (default: *)"
    )
    
    parser.add_argument(
        "--states",
        nargs="+",
        help="Multiple state FIPS codes (e.g., 06 48 36 for CA TX NY)"
    )
    
    parser.add_argument(
        "--health-insurance-only",
        action="store_true",
        help="Download only health insurance tables (oral health focus)"
    )
    
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="List all available ACS tables and exit"
    )
    
    args = parser.parse_args()
    
    # List tables if requested
    if args.list_tables:
        acs = ACSDataIngestion()
        acs.list_available_tables()
        return
    
    # Verify D drive setup
    if not verify_d_drive_setup(args.data_dir):
        logger.error("D drive setup verification failed. Please fix errors above.")
        return
    
    # Download data based on options
    if args.health_insurance_only:
        # Health insurance focus
        asyncio.run(download_health_insurance_focus(args.data_dir, args.state))
    
    elif args.states:
        # Multiple states
        asyncio.run(download_by_state_batch(args.data_dir, args.states, args.geography))
    
    else:
        # Comprehensive download
        asyncio.run(download_comprehensive_acs_data(
            args.data_dir,
            args.geography,
            args.state
        ))
    
    logger.success("\n🎉 All downloads complete!")
    logger.info(f"Data stored in: {args.data_dir.absolute()}")
    logger.info("\nNext steps:")
    logger.info("1. Verify data using: ls -lh " + str(args.data_dir))
    logger.info("2. Load data in your analysis scripts")
    logger.info("3. Join with jurisdiction data for enriched analysis")


if __name__ == "__main__":
    main()

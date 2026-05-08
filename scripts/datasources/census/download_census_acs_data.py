"""
Download American Community Survey (ACS) Data

Downloads comprehensive demographic data from the U.S. Census Bureau's
American Community Survey (5-year estimates) and caches each table as a
parquet file under ``--data-dir`` (default: ``data/cache/census/acs``).

Designed to be invoked either standalone or as a step in
``scripts/download_bronze.py``.

Usage:
    # Download all key tables for all U.S. counties (default cache dir)
    python scripts/datasources/census/download_census_acs_data.py

    # California counties only
    python scripts/datasources/census/download_census_acs_data.py --state 06

    # City-level data for Texas
    python scripts/datasources/census/download_census_acs_data.py \\
        --geography place --state 48

    # Re-download even if cached
    python scripts/datasources/census/download_census_acs_data.py --force

    # Different ACS 5-year vintage
    python scripts/datasources/census/download_census_acs_data.py --year 2021

    # List all available tables
    python scripts/datasources/census/download_census_acs_data.py --list-tables
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.datasources.census.load_acs import ACSDataIngestion
from loguru import logger


async def download_comprehensive_acs_data(
    data_dir: Path,
    geography: str = "county",
    state: str = "*",
    tables: Optional[list] = None,
    year: int = 2022,
    force: bool = False,
):
    """
    Download comprehensive ACS demographic data.

    Args:
        data_dir: Directory to store data
        geography: Geographic level (county, place, tract)
        state: State FIPS code (* for all states)
        tables: List of table codes (None = download key tables)
        year: ACS 5-year vintage (e.g., 2022)
        force: If True, re-download even if cached parquet already exists
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
    
    logger.info(f"Downloading {len(tables)} tables (year={year}, force={force})...")

    failures: list[tuple[str, str]] = []
    results = {}
    for i, table in enumerate(tables, 1):
        table_name = acs.ACS_TABLES.get(table, "Unknown")
        cache_file = data_dir / f"{table}_{geography}_{state}_{year}.parquet"

        if cache_file.exists() and not force:
            logger.info(f"[{i}/{len(tables)}] {table}: cached → {cache_file.name}")
            results[table] = None
            continue

        try:
            logger.info(f"\n[{i}/{len(tables)}] Downloading {table}: {table_name}")

            df = await acs.download_acs_data_api(
                table=table,
                geography=geography,
                state=state,
                year=year,
            )

            results[table] = df
            logger.success(f"✅ {table}: {len(df)} records")

            # Rate limiting — be nice to the Census API
            await asyncio.sleep(1.5)

        except Exception as e:
            logger.error(f"❌ Failed to download {table}: {e}")
            failures.append((table, str(e)))
            continue

    logger.info("\n" + "=" * 80)
    logger.info("Download Complete!")
    logger.info("=" * 80)
    n_ok = len(results)
    logger.info(f"Successfully downloaded or cached: {n_ok}/{len(tables)} tables")
    logger.info(f"Data saved to: {data_dir.absolute()}")

    print("\n📊 Downloaded Tables Summary:\n")
    total_bytes = 0
    for table_code in results:
        table_name = acs.ACS_TABLES.get(table_code, "Unknown")
        file_path = data_dir / f"{table_code}_{geography}_{state}_{year}.parquet"
        if not file_path.exists():
            continue
        file_size = file_path.stat().st_size
        total_bytes += file_size
        print(f"  {table_code}: {table_name}")
        print(f"    File: {file_path.name}")
        print(f"    Size: {file_size / (1024 * 1024):.2f} MB")
        print()

    logger.info(f"Total storage used: {total_bytes / (1024 * 1024):.2f} MB")

    return results, failures


async def download_health_insurance_focus(
    data_dir: Path,
    state: str = "*",
    year: int = 2022,
    force: bool = False,
):
    """
    Download health-insurance-focused tables for oral-health policy analysis.

    Detailed health insurance coverage data by age, type, and geographic area —
    useful for analyzing dental coverage gaps.
    """
    logger.info("=" * 80)
    logger.info("Health Insurance Data Download (Oral Health Policy Focus)")
    logger.info("=" * 80)

    acs = ACSDataIngestion(data_dir=data_dir)

    health_tables = {
        "B27001": "Health Insurance Coverage Status by Age",
        "B27010": "Health Insurance Coverage by Age (Under 19) ⭐ CRITICAL",
        "C27007": "Medicaid/Means-Tested Public Coverage",
        "B18101": "Disability Status (impacts dental needs)",
        "B17001": "Poverty Status (Medicaid eligibility)",
    }

    logger.info(f"Downloading {len(health_tables)} health insurance tables (year={year}, force={force})...")

    failures: list[tuple[str, str]] = []
    results: dict = {}
    for table_code, description in health_tables.items():
        cache_file = data_dir / f"{table_code}_county_{state}_{year}.parquet"
        if cache_file.exists() and not force:
            logger.info(f"{table_code}: cached → {cache_file.name}")
            results[table_code] = None
            continue

        try:
            logger.info(f"\nDownloading: {table_code} - {description}")
            df = await acs.download_acs_data_api(
                table=table_code,
                geography="county",
                state=state,
                year=year,
            )
            results[table_code] = df
            logger.success(f"✅ Downloaded {len(df)} counties")
            await asyncio.sleep(1.5)
        except Exception as e:
            logger.error(f"❌ Failed: {e}")
            failures.append((table_code, str(e)))
            continue

    logger.success(f"\n✅ Downloaded {len(results)} health insurance tables to {data_dir}")

    return results, failures


async def download_by_state_batch(
    data_dir: Path,
    states: list,
    geography: str = "county",
    year: int = 2022,
    force: bool = False,
):
    """
    Download data for multiple states in batch.

    More efficient than downloading all states at once if you only need data
    for specific states.

    Args:
        data_dir: Storage directory
        states: List of state FIPS codes (e.g., ["06", "48", "36"])
        geography: Geographic level
        year: ACS 5-year vintage
        force: If True, re-download even if cached
    """
    acs = ACSDataIngestion(data_dir=data_dir)

    logger.info(f"Downloading data for {len(states)} states: {states} (year={year}, force={force})")

    tables = ["B19013", "B27010", "B17001"]  # Income, child insurance, poverty
    failures: list[tuple[str, str]] = []

    for state_fips in states:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing State: {state_fips}")
        logger.info(f"{'=' * 60}")

        for table in tables:
            cache_file = data_dir / f"{table}_{geography}_{state_fips}_{year}.parquet"
            if cache_file.exists() and not force:
                logger.info(f"{table} ({state_fips}): cached → {cache_file.name}")
                continue

            try:
                df = await acs.download_acs_data_api(table, geography, state_fips, year=year)
                logger.success(f"✅ {table}: {len(df)} records")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ {table}: {e}")
                failures.append((f"{table}/{state_fips}", str(e)))
                continue

    return failures


def verify_data_dir(data_dir: Path) -> bool:
    """
    Verify that ``data_dir`` exists, is writable, and has enough free space.
    """
    logger.info(f"Verifying data directory: {data_dir}")

    if not data_dir.exists():
        logger.info(f"Creating directory: {data_dir}")
        data_dir.mkdir(parents=True, exist_ok=True)

    test_file = data_dir / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        logger.error(f"❌ Cannot write to {data_dir}: {e}")
        return False

    import shutil
    stat = shutil.disk_usage(data_dir)
    free_gb = stat.free / (1024 ** 3)
    logger.info(f"Available space: {free_gb:.2f} GB")

    if free_gb < 5:
        logger.warning(f"⚠️ Low disk space: {free_gb:.2f} GB available")
        return False

    logger.success(f"✅ Data directory ready: {data_dir}")
    return True


def main() -> int:
    """Main CLI interface. Returns process exit code."""
    parser = argparse.ArgumentParser(
        description="Download ACS demographic data into the local cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download key tables for all U.S. counties (default cache dir)
  python scripts/datasources/census/download_census_acs_data.py

  # California counties only
  python scripts/datasources/census/download_census_acs_data.py --state 06

  # Health-insurance focused tables only
  python scripts/datasources/census/download_census_acs_data.py --health-insurance-only

  # Multi-state batch (CA, TX, NY)
  python scripts/datasources/census/download_census_acs_data.py --states 06 48 36

  # Re-download even if cached
  python scripts/datasources/census/download_census_acs_data.py --force

  # Different ACS 5-year vintage
  python scripts/datasources/census/download_census_acs_data.py --year 2021

  # Custom data directory
  python scripts/datasources/census/download_census_acs_data.py --data-dir /mnt/d/acs

  # List available tables
  python scripts/datasources/census/download_census_acs_data.py --list-tables
        """,
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/cache/census/acs"),
        help="Directory to store ACS data (default: data/cache/census/acs)",
    )
    parser.add_argument(
        "--geography",
        choices=["county", "place", "tract", "cousub"],
        default="county",
        help="Geographic level (default: county)",
    )
    parser.add_argument(
        "--state",
        default="*",
        help="State FIPS code or * for all states (default: *)",
    )
    parser.add_argument(
        "--states",
        nargs="+",
        help="Multiple state FIPS codes (e.g., 06 48 36 for CA TX NY)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2022,
        help="ACS 5-year vintage (default: 2022 — most recent complete release)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if a cached parquet already exists",
    )
    parser.add_argument(
        "--health-insurance-only",
        action="store_true",
        help="Download only health-insurance tables (oral-health focus)",
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="List all available ACS tables and exit",
    )

    args = parser.parse_args()

    if args.list_tables:
        acs = ACSDataIngestion()
        acs.list_available_tables()
        return 0

    if not verify_data_dir(args.data_dir):
        logger.error("Data directory verification failed. See errors above.")
        return 1

    failures: list[tuple[str, str]] = []
    if args.health_insurance_only:
        _, failures = asyncio.run(download_health_insurance_focus(
            args.data_dir, args.state, year=args.year, force=args.force,
        ))
    elif args.states:
        failures = asyncio.run(download_by_state_batch(
            args.data_dir, args.states, args.geography,
            year=args.year, force=args.force,
        ))
    else:
        _, failures = asyncio.run(download_comprehensive_acs_data(
            args.data_dir, args.geography, args.state,
            year=args.year, force=args.force,
        ))

    logger.info(f"Data stored in: {args.data_dir.absolute()}")

    if failures:
        logger.error(f"\n❌ {len(failures)} table(s) failed:")
        for name, err in failures:
            logger.error(f"  - {name}: {err}")
        return 1

    logger.success("\n🎉 All downloads complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

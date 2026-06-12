"""
Download American Community Survey (ACS) Data

Downloads comprehensive demographic data from the U.S. Census Bureau's
American Community Survey (5-year estimates) and caches each table as a
parquet file under ``--data-dir`` (default: ``data/cache/census/acs``).

Designed to be invoked either standalone or as a step in
``scripts/download_bronze.py``.

``--all-years`` discovers vintages from ``https://api.census.gov/data.json``
(``acs/acs5``); on failure it falls back to 2009 through the latest known year.

Usage:
    # Download all key tables for all U.S. counties (default cache dir)
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py

    # California counties only
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --state 06

    # State-level estimates (all states / DC / PR — one row per state per table)
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography state --state '*'

    # Single state summary (e.g. Alabama only)
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography state --state 01

    # City / places — requires state FIPS (same cache pattern as B19013_place_01_2022.parquet)
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography place --state 01

    # Unified school districts (K–12) for Alabama
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography sduni --state 01

    # Elementary-only districts (empty parquet in states with none of this type)
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography sdelem --state 06

    # Re-download even if cached
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --force

    # Different ACS 5-year vintage
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --year 2021

    # Every ACS 5-year vintage published on the Census API (trend panels)
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --all-years

    # Unified school districts — all states + DC + PR, all vintages (very large run)
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography sduni --all-states --all-years

    # List all available tables
    python packages/scrapers/src/scrapers/census/download_census_acs_data.py --list-tables
"""
import asyncio
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional
import sys

# First ACS 5-year API vintage; used only if data.json cannot be read.
_ACS5_FALLBACK_FIRST_YEAR = 2009
_ACS5_FALLBACK_LAST_YEAR = 2024
_CENSUS_DATA_CATALOG_URL = "https://api.census.gov/data.json"

# Default ACS detail/subject tables when ``--tables`` is omitted. Keep table set aligned with
# ``export_census_map_static.METRICS`` (each map metric must have matching county/state parquets).
DEFAULT_DOWNLOAD_TABLES: tuple[str, ...] = (
    "B01001",
    "B01002",
    "B01003",
    "B02001",
    "B03002",
    "B14001",
    "B15003",
    "B17001",
    "B19013",
    "B19083",
    "B19301",
    "B23025",
    "B25001",
    "B25064",
    "B25071",
    "B25077",
    "B25103",
    "B27001",
    "B27010",
    "S0801",
)

# U.S. states, the District of Columbia, and Puerto Rico (two-digit FIPS) for
# per-state ACS pulls (place, school districts, state-scoped county, etc.).
CENSUS_ACS_STATE_FIPS: tuple[str, ...] = (
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17",
    "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
    "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "44", "45", "46",
    "47", "48", "49", "50", "51", "53", "54", "55", "56", "72",
)
# Add project root to path for imports
# __file__ = .../examples/download_acs_to_d_drive.py
# parent = .../examples
# parent.parent = .../open-navigator (project root)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from ingestion.census.acs import ACSDataIngestion
from loguru import logger
import httpx


def _census_api_bad_request(exc: BaseException) -> bool:
    """True if ``exc`` is a Census HTTP 400 (often: table not in that vintage)."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400


def list_acs5_api_vintages() -> list[int]:
    """
    Return sorted ACS 5-year API vintage years (e.g. 2009, …, 2024).

    Reads the public Census dataset catalog. Falls back to a fixed range if
    the request fails or the catalog shape changes.
    """
    try:
        with urllib.request.urlopen(_CENSUS_DATA_CATALOG_URL, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        logger.warning(
            f"Could not fetch ACS5 vintages from {_CENSUS_DATA_CATALOG_URL} ({e!r}); "
            f"using fallback {_ACS5_FALLBACK_FIRST_YEAR}–{_ACS5_FALLBACK_LAST_YEAR}"
        )
        return list(range(_ACS5_FALLBACK_FIRST_YEAR, _ACS5_FALLBACK_LAST_YEAR + 1))

    years: set[int] = set()
    for item in payload.get("dataset", []):
        if not isinstance(item, dict):
            continue
        ds = item.get("c_dataset") or []
        if list(ds)[:2] == ["acs", "acs5"]:
            v = item.get("c_vintage")
            if v is not None:
                years.add(int(v))
    if not years:
        logger.warning(
            "Catalog contained no acs/acs5 entries; "
            f"using fallback {_ACS5_FALLBACK_FIRST_YEAR}–{_ACS5_FALLBACK_LAST_YEAR}"
        )
        return list(range(_ACS5_FALLBACK_FIRST_YEAR, _ACS5_FALLBACK_LAST_YEAR + 1))
    return sorted(years)


async def download_comprehensive_acs_data(
    data_dir: Path,
    geography: str = "county",
    state: str = "*",
    tables: Optional[list] = None,
    year: int = 2022,
    force: bool = False,
    skip_http_400: bool = False,
):
    """
    Download comprehensive ACS demographic data.

    Args:
        data_dir: Directory to store data
        geography: Geographic level (county, place, tract, cousub, state, sduni, sdelem, sdsec)
        state: State FIPS code (* for all states)
        tables: List of table codes (None = download key tables)
        year: ACS 5-year vintage (e.g., 2022)
        force: If True, re-download even if cached parquet already exists
        skip_http_400: If True, log and continue on HTTP 400 (missing table for vintage)
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
        tables = list(DEFAULT_DOWNLOAD_TABLES)
    
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
            if skip_http_400 and _census_api_bad_request(e):
                logger.warning(
                    f"Skipping {table} for {year}: Census API HTTP 400 "
                    f"(table may not exist for this 5-year vintage)"
                )
                continue
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
    skip_http_400: bool = False,
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
            if skip_http_400 and _census_api_bad_request(e):
                logger.warning(
                    f"Skipping {table_code} for {year}: Census API HTTP 400 "
                    f"(table may not exist for this 5-year vintage)"
                )
                continue
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
    skip_http_400: bool = False,
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
                if skip_http_400 and _census_api_bad_request(e):
                    logger.warning(
                        f"Skipping {table} ({state_fips}) for {year}: Census API HTTP 400 "
                        f"(table may not exist for this 5-year vintage)"
                    )
                    continue
                logger.error(f"❌ {table}: {e}")
                failures.append((f"{table}/{state_fips}", str(e)))
                continue

    return failures


async def download_acs_for_years(
    data_dir: Path,
    geography: str,
    state: str,
    states: Optional[list[str]],
    years: list[int],
    force: bool,
    health_insurance_only: bool,
    skip_http_400: bool = False,
    comprehensive_state_fips: Optional[list[str]] = None,
) -> list[tuple[str, str]]:
    """
    Run the appropriate download path for each ACS vintage in ``years``.

    ``comprehensive_state_fips``: when set (e.g. all U.S. states from ``--all-states``),
    run the comprehensive table set once per state in this list, then per year.

    Failure keys are prefixed with state and/or year when multiple states or years
    are requested.
    """
    failures: list[tuple[str, str]] = []
    multi_year = len(years) > 1
    state_loop = comprehensive_state_fips if comprehensive_state_fips is not None else [state]
    multi_state = bool(comprehensive_state_fips and len(comprehensive_state_fips) > 1)

    def tag(name: str, y: int, state_slug: Optional[str]) -> str:
        parts: list[str] = []
        if multi_state and state_slug is not None:
            parts.append(state_slug)
        if multi_year:
            parts.append(str(y))
        parts.append(name)
        return "/".join(parts) if parts else name

    if health_insurance_only:
        for idx, year in enumerate(years, 1):
            logger.info(f"\n{'=' * 20} ACS vintage {year} ({idx}/{len(years)}) {'=' * 20}")
            _, f = await download_health_insurance_focus(
                data_dir, state, year=year, force=force, skip_http_400=skip_http_400,
            )
            failures.extend((tag(n, year, None), e) for n, e in f)
        return failures

    if states is not None:
        for idx, year in enumerate(years, 1):
            logger.info(f"\n{'=' * 20} ACS vintage {year} ({idx}/{len(years)}) {'=' * 20}")
            f = await download_by_state_batch(
                data_dir, states, geography, year=year, force=force, skip_http_400=skip_http_400,
            )
            failures.extend((tag(n, year, None), e) for n, e in f)
        return failures

    for st in state_loop:
        for idx, year in enumerate(years, 1):
            log_state = f" state {st} " if multi_state else " "
            logger.info(
                f"\n{'=' * 20}{log_state}ACS vintage {year} ({idx}/{len(years)}) {'=' * 20}"
            )
            _, f = await download_comprehensive_acs_data(
                data_dir, geography, st, year=year, force=force, skip_http_400=skip_http_400,
            )
            failures.extend(
                (tag(n, year, st if multi_state else None), e) for n, e in f
            )
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
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py

  # State-level tables (all states / DC / PR)
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography state --state '*'

  # State-level for Alabama only (one row per table)
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography state --state 01

  # California counties only
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --state 06

  # Places (cities/CDPs) — requires state FIPS; files like B19013_place_01_2022.parquet
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography place --state 01

  # Unified school districts — requires state FIPS; files like B19013_sduni_01_2022.parquet
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography sduni --state 01

  # Health-insurance focused tables only
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --health-insurance-only

  # Multi-state batch (CA, TX, NY)
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --states 06 48 36

  # Re-download even if cached
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --force

  # Different ACS 5-year vintage
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --year 2021

  # Early vintage: some tables are not published (HTTP 400) — skip and continue
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --year 2011 --skip-http-400

  # Every ACS 5-year vintage (Census API catalog)
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --all-years

  # Unified school districts — all states + DC + PR, all vintages (very large)
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --geography sduni --all-states --all-years

  # Custom data directory
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --data-dir /mnt/d/acs

  # List available tables
  python packages/scrapers/src/scrapers/census/download_census_acs_data.py --list-tables
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
        choices=["state", "county", "place", "tract", "cousub", "sduni", "sdelem", "sdsec"],
        default="county",
        help=(
            "Geographic level (default: county). sduni/sdelem/sdsec = ACS school districts "
            "(unified / elementary / secondary). place and sd* require --state FIPS "
            "(or use --all-states for every state + DC + PR)."
        ),
    )
    parser.add_argument(
        "--state",
        default="*",
        help=(
            "State FIPS or * (default: *). place / sduni / sdelem / sdsec require a "
            "2-digit FIPS (not *) unless you use --states for multi-state batch or "
            "--all-states for every state + DC + PR."
        ),
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
        help="ACS 5-year vintage when not using --all-years (default: 2022)",
    )
    parser.add_argument(
        "--all-years",
        action="store_true",
        help=(
            "Download every ACS 5-year vintage listed for acs/acs5 in the Census "
            "data catalog (https://api.census.gov/data.json). Ignores --year. "
            "HTTP 400 responses (table not published that vintage) are skipped with a warning."
        ),
    )
    parser.add_argument(
        "--all-states",
        action="store_true",
        help=(
            "Loop every U.S. state, DC, and Puerto Rico (52 two-digit FIPS from "
            "CENSUS_ACS_STATE_FIPS). Only for place, sduni, sdelem, or sdsec. "
            "Cannot be combined with --states or --health-insurance-only."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if a cached parquet already exists",
    )
    parser.add_argument(
        "--skip-http-400",
        action="store_true",
        help=(
            "On Census HTTP 400 (table not in that vintage), log a warning and continue. "
            "Useful with --year for early ACS releases; implied when using --all-years."
        ),
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

    _GEO_NEEDS_STATE = frozenset({"place", "sduni", "sdelem", "sdsec"})

    if args.all_states and args.states:
        parser.error("Cannot combine --all-states with --states")

    if args.all_states:
        if args.geography not in _GEO_NEEDS_STATE:
            parser.error(
                "--all-states is only supported for --geography "
                "place, sduni, sdelem, or sdsec"
            )
        if args.health_insurance_only:
            parser.error("--all-states cannot be used with --health-insurance-only")

    if args.geography in _GEO_NEEDS_STATE and not args.states and not args.all_states:
        st = (args.state or "").strip()
        if st in ("*", ""):
            parser.error(
                f"--geography {args.geography} requires a 2-digit state FIPS "
                f"(e.g. --state 01), not '*', unless you pass --all-states. "
                f"Per-state parquet names look like B19013_place_01_2022.parquet. "
                f"For a hand-picked multi-state list use --states 01 06 …"
            )

    if not verify_data_dir(args.data_dir):
        logger.error("Data directory verification failed. See errors above.")
        return 1

    years = list_acs5_api_vintages() if args.all_years else [args.year]
    if args.all_years:
        logger.info(
            f"--all-years: {len(years)} vintages ({years[0]} … {years[-1]}); "
            f"~{len(years)}× the usual API traffic — ensure quota and disk space."
        )

    if args.all_states:
        logger.info(
            f"--all-states: {len(CENSUS_ACS_STATE_FIPS)} areas "
            f"(50 states + DC + PR); each gets a full comprehensive table set per year."
        )

    comp_state_list = list(CENSUS_ACS_STATE_FIPS) if args.all_states else None

    failures = asyncio.run(
        download_acs_for_years(
            args.data_dir,
            args.geography,
            args.state,
            args.states,
            years,
            args.force,
            args.health_insurance_only,
            skip_http_400=args.all_years or args.skip_http_400,
            comprehensive_state_fips=comp_state_list,
        )
    )

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

"""
American Community Survey (ACS) Data Ingestion

Downloads and processes demographic, economic, housing, and social data from the
U.S. Census Bureau's American Community Survey (ACS) 5-Year Estimates.

Data Coverage:
- Demographics (age, race, ethnicity, language)
- Economics (income, employment, poverty)
- Housing (occupancy, value, rent)
- Social (education, disability, veteran status)
- Health insurance coverage

Data Granularity:
- National, State, County, Place (city/town), Tract, Block Group
"""
import asyncio
import csv
import zipfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import re
import httpx
import pandas as pd
from loguru import logger

from config import settings

# Subject summary tables (e.g. ``S0801``) use ``…/acs/acs5/subject``; detailed ``B*`` / ``C*`` use ``…/acs/acs5``.
_SUBJECT_TABLE_RE = re.compile(r"^S\d{4}$", re.I)


class ACSDataIngestion:
    """
    Ingest American Community Survey (ACS) data for civic engagement analysis.
    
    The ACS provides demographic, economic, housing, and social characteristics
    for all areas of the United States, Puerto Rico, and Island Areas.
    
    We use 5-Year Estimates (most reliable, covers all geographies).
    """
    
    # ACS 5-Year Estimates (2022) - Most recent complete dataset
    # These are summary files with pre-aggregated tables
    ACS_BASE_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2022/data"
    
    # Key ACS tables for civic engagement and oral health policy
    ACS_TABLES = {
        # Demographics
        "B01001": "Sex by Age",
        "B02001": "Race",
        "B03002": "Hispanic or Latino Origin by Race",
        "B05001": "Nativity and Citizenship Status",
        "B16001": "Language Spoken at Home",
        
        # Economics
        "B19013": "Median Household Income",
        "B17001": "Poverty Status (Individual)",
        "B23025": "Employment Status",
        "C24010": "Sex by Occupation",
        
        # Housing
        "B25001": "Housing Units",
        "B25003": "Tenure (Owner vs Renter)",
        "B25077": "Median Home Value",
        "B25064": "Median Gross Rent",
        "B01002": "Median Age by Sex",
        "B19301": "Per Capita Income",
        "B19083": "Gini Index of Income Inequality",
        "B08303": "Travel Time to Work (time buckets; total in _001E is worker count)",
        "S0801": "Commuting Characteristics by Sex (subject; includes mean travel time)",
        "B25070": "Gross Rent as Percentage of Household Income (distribution)",
        "B25071": "Median Gross Rent as a Percentage of Household Income",
        "B01003": "Total Population",
        
        # Education
        "B15003": "Educational Attainment",
        "B14001": "School Enrollment by Age",
        
        # Health Insurance (Critical for oral health policy)
        "B27001": "Health Insurance Coverage Status by Age",
        "B27010": "Health Insurance Coverage by Age (Under 19)",
        "C27007": "Medicaid/Means-Tested Public Coverage",
        
        # Disability
        "B18101": "Sex by Age by Disability Status",
        
        # Veterans
        "B21001": "Veteran Status",
    }
    
    # Geography levels available
    GEO_LEVELS = {
        "us": "United States",
        "state": "State",
        "county": "County",
        "place": "Place (City/Town)",
        "tract": "Census Tract",
        "cousub": "County Subdivision",
        "sduni": "School District (Unified)",
        "sdelem": "School District (Elementary)",
        "sdsec": "School District (Secondary)",
    }

    # Geographies that must use ``in=state:XX`` with a concrete state FIPS (not ``*``).
    _GEO_REQUIRES_STATE_FIPS = frozenset({"place", "sduni", "sdelem", "sdsec"})
    
    def __init__(self, data_dir: Optional[Path] = None, spark: Any = None):
        """
        Initialize ACS ingestion.
        
        Args:
            data_dir: Base directory for data storage (default: data/cache/acs)
                     Can be set to D:/ for D drive storage
            spark: Reserved; API + parquet paths use pandas only. Pass a Spark session
                   only if you extend this class for Delta Lake (not used today).
        """
        if data_dir is None:
            self.data_dir = Path("data/cache/acs")
        else:
            self.data_dir = Path(data_dir)
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.spark = spark  # always None unless caller injects a session for custom use
        
        # Census API key: env ``CENSUS_API_KEY`` → Settings field ``census_api_key`` (not ``CENSUS_API_KEY`` on model)
        raw = getattr(settings, "census_api_key", None) or getattr(settings, "CENSUS_API_KEY", None)
        self.api_key = (str(raw).strip() if raw else None) or None
        
        logger.info(f"ACS data directory: {self.data_dir.absolute()}")
    
    async def download_acs_data_api(
        self, 
        table: str, 
        geography: str = "county",
        state: str = "*",
        year: int = 2022
    ) -> pd.DataFrame:
        """
        Download ACS data using Census API.
        
        This is the recommended approach for targeted data extraction.
        Requires a Census API key for higher rate limits.
        
        Args:
            table: ACS table code (e.g., "B19013" for median household income)
            geography: Geographic level (state, county, place, tract, cousub,
                sduni, sdelem, sdsec). ``place`` and ``sd*`` require a 2-digit state FIPS
                (same cache pattern as ``B19013_place_01_2022.parquet``).
            state: For county/tract/cousub: parent state FIPS or ``*`` (national).
                   For ``place`` / ``sduni`` / ``sdelem`` / ``sdsec``: a single state FIPS only.
                   For ``geography="state"``: ``*`` = all states/DC/PR; else one state FIPS.
            year: ACS year (2022 is most recent 5-year estimate)
        
        Returns:
            pandas DataFrame with requested data
        
        Example:
            # Get median household income for all counties
            df = await acs.download_acs_data_api("B19013", "county", "*")
            # State-level estimates (all states, one row per state)
            df = await acs.download_acs_data_api("B19013", "state", "*")
        """
        if not self.api_key:
            logger.warning("No Census API key found. Get one at: https://api.census.gov/data/key_signup.html")
            logger.info("Without API key, you're limited to 500 requests/day")
        
        # Construct API URL (subject vs detailed 5-year endpoint)
        base_tail = "acs/acs5/subject" if _SUBJECT_TABLE_RE.match(table.strip()) else "acs/acs5"
        base_url = f"https://api.census.gov/data/{year}/{base_tail}"
        
        # Nested geographies use ``for=...&in=state:XX``. State summary uses ``for=state:*`` or ``for=state:06`` only.
        geo_params = {
            "county": "county:*",
            "place": "place:*",
            "tract": "tract:*",
            "cousub": "county subdivision:*",
            "sduni": "school district (unified):*",
            "sdelem": "school district (elementary):*",
            "sdsec": "school district (secondary):*",
        }

        # Get all variables for this table
        variables = f"group({table})"

        state_token = "*" if state == "*" else str(state).strip().zfill(2)

        if geography in self._GEO_REQUIRES_STATE_FIPS and state_token == "*":
            raise ValueError(
                f"geography={geography!r} requires a 2-digit state FIPS (e.g. '01'), not '*'"
            )

        params: Dict[str, str] = {"get": variables}

        if geography == "us":
            # Single national row (cache files like ``B19013_us_1_{year}.parquet`` with state token ``1``).
            params["for"] = "us:1"
        elif geography == "state":
            if state_token == "*":
                params["for"] = "state:*"
            else:
                params["for"] = f"state:{state_token}"
        elif geography != "us":
            try:
                params["for"] = geo_params[geography]
            except KeyError as e:
                raise ValueError(f"Unknown geography level: {geography!r}") from e
            if state_token != "*":
                params["in"] = f"state:{state_token}"
        
        if self.api_key:
            params["key"] = self.api_key
        
        logger.info(f"Downloading ACS table {table} ({self.ACS_TABLES.get(table, 'Unknown')})...")
        logger.info(f"Geography: {geography}, State: {state}, Year: {year}")
        
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=False) as client:
            try:
                response = await client.get(base_url, params=params)
                if response.status_code in (301, 302, 303, 307, 308):
                    loc = (response.headers.get("location") or "").lower()
                    if "invalid_key" in loc:
                        raise ValueError(
                            "api.census.gov rejected this API key (invalid or revoked). "
                            "Create or verify your key at https://api.census.gov/data/key_signup.html "
                            "and set CENSUS_API_KEY in the project root .env. "
                            "To use the anonymous tier (lower daily limits), remove or blank CENSUS_API_KEY."
                        )
                response.raise_for_status()

                if response.status_code == 204:
                    logger.warning(
                        f"Census API returned 204 No Content — no {geography!r} rows for "
                        f"state {state_token} year {year} (e.g. no districts of this type)"
                    )
                    df = pd.DataFrame()
                    cache_file = self.data_dir / f"{table}_{geography}_{state}_{year}.parquet"
                    df.to_parquet(cache_file, index=False)
                    logger.info(f"Cached empty result to: {cache_file}")
                    return df

                # Parse JSON response
                data = response.json()

                # First row is headers, rest is data
                headers = data[0]
                rows = data[1:]

                df = pd.DataFrame(rows, columns=headers)

                logger.success(f"Downloaded {len(df)} records for table {table}")

                # Cache the data
                cache_file = self.data_dir / f"{table}_{geography}_{state}_{year}.parquet"
                df.to_parquet(cache_file, index=False)
                logger.info(f"Cached to: {cache_file}")

                return df
                
            except httpx.HTTPStatusError as e:
                # 400 often means the table was not published for this ACS 5-year vintage (e.g. B27010 in 2011).
                if e.response.status_code == 400:
                    snippet = (e.response.text or "")[:240]
                    logger.warning(
                        f"Census API HTTP 400 for {table} ({geography}, state={state}, year={year}): {snippet!r}"
                    )
                else:
                    logger.error(f"API request failed: {e}")
                    logger.error(f"Status: {e.response.status_code}")
                    logger.error(f"Response: {e.response.text[:500]}")
                raise
    
    async def download_all_demographics(self, geography: str = "county", state: str = "*") -> Dict[str, pd.DataFrame]:
        """
        Download all key demographic tables for a geography level.
        
        This downloads the most important tables for civic engagement analysis:
        - Demographics (age, race, language)
        - Economics (income, poverty, employment)
        - Health insurance coverage
        - Education
        
        Args:
            geography: Geographic level (county, place, tract)
            state: State FIPS code (* for all states)
        
        Returns:
            Dictionary mapping table codes to DataFrames
        
        Example:
            # Get all demographic data for California counties
            dfs = await acs.download_all_demographics("county", "06")
        """
        key_tables = [
            "B01001",  # Age/Sex
            "B02001",  # Race
            "B03002",  # Hispanic origin
            "B19013",  # Median household income
            "B17001",  # Poverty
            "B27001",  # Health insurance
            "B15003",  # Education
        ]
        
        results = {}
        
        for table in key_tables:
            try:
                df = await self.download_acs_data_api(table, geography, state)
                results[table] = df
                
                # Rate limiting - be nice to Census API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to download table {table}: {e}")
                continue
        
        logger.success(f"Downloaded {len(results)}/{len(key_tables)} tables")
        
        return results
    
    async def download_bulk_files(self, state: str = "ALL", year: int = 2022) -> Path:
        """
        Download bulk ACS summary files (ZIP archives).
        
        This is useful for downloading ALL ACS data at once.
        Warning: Files are LARGE (several GB per state).
        
        Args:
            state: State abbreviation (e.g., "CA", "TX") or "ALL" for all states
            year: ACS year (2022 is most recent)
        
        Returns:
            Path to extracted data directory
        
        Note:
            - ALL states file is ~15 GB
            - Individual state files are 200-500 MB each
            - Consider using API for targeted data extraction instead
        """
        if state == "ALL":
            filename = f"All_Geographies_Not_Tracts_Block_Groups.zip"
        else:
            filename = f"{year}_5yr_Summary_FileTemplates.zip"
        
        url = f"{self.ACS_BASE_URL}/{filename}"
        
        output_dir = self.data_dir / f"acs_{year}_{state}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        zip_path = output_dir / filename
        
        # Check if already downloaded
        if zip_path.exists():
            logger.info(f"Using cached file: {zip_path}")
            return output_dir
        
        logger.warning(f"Downloading bulk ACS file: {filename}")
        logger.warning(f"This may be several GB and take 10-30 minutes...")
        
        async with httpx.AsyncClient(timeout=3600.0) as client:  # 1 hour timeout
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get("content-length", 0))
                
                with open(zip_path, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes(chunk_size=8192 * 1024):  # 8 MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            pct = (downloaded / total_size) * 100
                            logger.info(f"Progress: {pct:.1f}% ({downloaded / 1e9:.2f} GB / {total_size / 1e9:.2f} GB)")
        
        logger.success(f"Downloaded: {zip_path}")
        
        # Extract ZIP
        logger.info("Extracting ZIP file...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        
        logger.success(f"Extracted to: {output_dir}")
        
        return output_dir
    
    def get_cached_data(self, table: str, geography: str = "county", state: str = "*") -> Optional[pd.DataFrame]:
        """
        Load cached ACS data if available.
        
        Args:
            table: ACS table code
            geography: Geographic level
            state: State FIPS code
        
        Returns:
            DataFrame if cached, None otherwise
        """
        cache_file = self.data_dir / f"{table}_{geography}_{state}_2022.parquet"
        
        if cache_file.exists():
            logger.info(f"Loading cached data: {cache_file}")
            return pd.read_parquet(cache_file)
        
        return None
    
    def list_available_tables(self) -> None:
        """Print all available ACS tables."""
        print("\n📊 Available ACS Tables\n")
        print("=" * 80)
        
        categories = {
            "Demographics": ["B01001", "B02001", "B03002", "B05001", "B16001"],
            "Economics": ["B19013", "B17001", "B23025", "C24010"],
            "Housing": ["B25001", "B25003", "B25077", "B25064"],
            "Education": ["B15003", "B14001"],
            "Health Insurance": ["B27001", "B27010", "C27007"],
            "Other": ["B18101", "B21001"],
        }
        
        for category, tables in categories.items():
            print(f"\n{category}:")
            for table in tables:
                description = self.ACS_TABLES.get(table, "Unknown")
                print(f"  {table}: {description}")
        
        print("\n" + "=" * 80)
        print(f"\nTotal: {len(self.ACS_TABLES)} tables available")
        print("\nFor complete table list, visit:")
        print("https://www.census.gov/programs-surveys/acs/technical-documentation/table-shells.html")


async def main():
    """Example usage of ACS ingestion."""
    
    # Option 1: Use default data directory (data/cache/acs)
    acs = ACSDataIngestion()
    
    # Option 2: Use D drive (WSL - Windows Subsystem for Linux)
    # acs = ACSDataIngestion(data_dir=Path("/mnt/d/open-navigator-data/acs"))
    
    # Option 3: Use D drive (Windows native)
    # acs = ACSDataIngestion(data_dir=Path("D:/open-navigator-data/acs"))
    
    # Option 4: Use external drive (Linux/Mac)
    # acs = ACSDataIngestion(data_dir=Path("/mnt/external/open-navigator-data/acs"))
    
    # List available tables
    acs.list_available_tables()
    
    print("\n" + "=" * 80)
    print("Example 1: Download median household income for all counties")
    print("=" * 80)
    
    # Download median household income for all U.S. counties
    income_df = await acs.download_acs_data_api("B19013", geography="county", state="*")
    print(f"\nDownloaded {len(income_df)} counties")
    print(income_df.head())
    
    print("\n" + "=" * 80)
    print("Example 2: Download health insurance data for California counties")
    print("=" * 80)
    
    # Download health insurance data for California only
    health_df = await acs.download_acs_data_api("B27001", geography="county", state="06")
    print(f"\nDownloaded {len(health_df)} California counties")
    print(health_df.head())
    
    print("\n" + "=" * 80)
    print("Example 3: Download all key demographic tables")
    print("=" * 80)
    
    # Download comprehensive demographic package
    all_data = await acs.download_all_demographics(geography="county", state="06")
    
    print(f"\nDownloaded {len(all_data)} tables:")
    for table_code, df in all_data.items():
        table_name = acs.ACS_TABLES.get(table_code, "Unknown")
        print(f"  {table_code} ({table_name}): {len(df)} records")


if __name__ == "__main__":
    asyncio.run(main())

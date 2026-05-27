#!/usr/bin/env python3
"""
American Community Survey (ACS) pipeline: load cached ACS parquet into bronze.

Ported from load_acs.py to the core_lib DataSourcePipeline contract.

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

DEVIATION (NOTED): the legacy load_acs.py is an *API downloader* that caches each
ACS table as a wide, variable-column parquet (``{table}_{geography}_{state}_{year}.parquet``).
ACS tables do not share a fixed column set (``group(B01001)`` vs ``group(S0801)`` etc.),
so they do not fit a fixed RawRow. To preserve behavior best-fit, the pipeline reads
those cached parquet artifacts and *melts* each wide row into long EAV cells -- one
``AcsCellRow`` per (table, geography, state, year, geo_id, variable) -- written to
bronze.bronze_census_acs. The original ``ACSDataIngestion`` class (API download,
bulk-file download, caching, table listing) is preserved verbatim below so the
download/cache path is unchanged. ``from config import settings`` is lazily imported
inside ``ACSDataIngestion.__init__`` (the repo-root ``config`` package is not on the
ingestion package path) so the module imports cleanly under the package contract.

Usage:
    python -m ingestion.census.acs
    python -m ingestion.census.acs --truncate
    python -m ingestion.census.acs --path data/cache/census/acs/B19013_county_06_2022.parquet --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2/localhost connections).
"""
from __future__ import annotations

import argparse
import asyncio
import re
import zipfile
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import httpx
import pandas as pd
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# Cache directory for ACS parquet artifacts (produced by download_census_acs_data.py).
CACHE_DIR = Path("data/cache/census/acs")

# Subject summary tables (e.g. ``S0801``) use ``…/acs/acs5/subject``; detailed ``B*`` / ``C*`` use ``…/acs/acs5``.
_SUBJECT_TABLE_RE = re.compile(r"^S\d{4}$", re.I)

# Parquet filenames look like ``{table}_{geography}_{state}_{year}.parquet``.
_PARQUET_NAME_RE = re.compile(
    r"^(?P<table>[A-Za-z0-9]+)_(?P<geography>[a-z]+)_(?P<state>[^_]+)_(?P<year>\d{4})\.parquet$"
)

# Census API "group(TABLE)" responses include geography identity columns alongside
# the estimate/margin variables. These are not melted into EAV cells.
_GEO_IDENTITY_COLS = frozenset(
    {
        "GEO_ID",
        "NAME",
        "us",
        "state",
        "county",
        "place",
        "tract",
        "county subdivision",
        "school district (unified)",
        "school district (elementary)",
        "school district (secondary)",
    }
)


def parse_parquet_name(path: Path) -> dict[str, str]:
    """Parse ``{table}_{geography}_{state}_{year}.parquet`` into its parts.

    Raises ValueError if the filename does not match the cache naming scheme.
    """
    m = _PARQUET_NAME_RE.match(path.name)
    if not m:
        raise ValueError(
            f"Unrecognized ACS parquet filename: {path.name!r} "
            "(expected {table}_{geography}_{state}_{year}.parquet)"
        )
    return m.groupdict()


def find_acs_parquets() -> list[Path]:
    """Return all cached ACS parquet files, sorted by filename."""
    parquets = sorted(CACHE_DIR.glob("*.parquet"))
    if not parquets:
        raise FileNotFoundError(
            f"No cached ACS parquet found in {CACHE_DIR}. "
            "Run download_census_acs_data.py first."
        )
    return parquets


def _geo_id_for_row(row: dict[str, Any]) -> str:
    """Best-effort stable geography id for a melted ACS row.

    Prefers GEO_ID (the Census geographic identifier); falls back to a composite
    of any present geography identity columns; finally to NAME.
    """
    geo_id = row.get("GEO_ID")
    if geo_id is not None and str(geo_id).strip():
        return str(geo_id).strip()
    parts = [
        str(row[c]).strip()
        for c in ("state", "county", "place", "tract")
        if row.get(c) is not None and str(row.get(c)).strip()
    ]
    if parts:
        return ":".join(parts)
    name = row.get("NAME")
    return str(name).strip() if name is not None else ""


def _safe_str(val: Any) -> str | None:
    """Stringify a cell value, returning None for NaN/None/empty."""
    if val is None:
        return None
    try:
        if isinstance(val, float) and pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return s or None


class AcsCellRow(RawRow):
    """One melted ACS cell (long/EAV form), validated before upsert into bronze.bronze_census_acs."""

    table: str = Field(min_length=1, max_length=16)
    geography: str = Field(min_length=1, max_length=32)
    state: str = Field(min_length=1, max_length=8)
    year: int
    geo_id: str = Field(min_length=1, max_length=64)
    geo_name: str | None = Field(default=None, max_length=255)
    variable: str = Field(min_length=1, max_length=64)
    value: str | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_census_acs (
        table_code      VARCHAR(16)  NOT NULL,
        geography       VARCHAR(32)  NOT NULL,
        state           VARCHAR(8)   NOT NULL,
        year            INTEGER      NOT NULL,
        geo_id          VARCHAR(64)  NOT NULL,
        geo_name        VARCHAR(255),
        variable        VARCHAR(64)  NOT NULL,
        value           TEXT,
        ingestion_date  TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (table_code, geography, state, year, geo_id, variable)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bca_table    ON bronze.bronze_census_acs(table_code)"),
    text("CREATE INDEX IF NOT EXISTS idx_bca_geo      ON bronze.bronze_census_acs(geography, state)"),
    text("CREATE INDEX IF NOT EXISTS idx_bca_variable ON bronze.bronze_census_acs(variable)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_census_acs")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_census_acs
        (table_code, geography, state, year, geo_id, geo_name, variable, value)
    VALUES
        (:table, :geography, :state, :year, :geo_id, :geo_name, :variable, :value)
    ON CONFLICT (table_code, geography, state, year, geo_id, variable) DO UPDATE SET
        geo_name       = EXCLUDED.geo_name,
        value          = EXCLUDED.value,
        ingestion_date = NOW()
    """
)


class CensusAcsPipeline(DataSourcePipeline[AcsCellRow]):
    source = "census_acs"
    batch_size = 5_000
    row_schema = AcsCellRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        paths = [self._path] if self._path is not None else find_acs_parquets()
        emitted = 0
        for path in paths:
            meta = parse_parquet_name(path)
            table = meta["table"]
            geography = meta["geography"]
            state = meta["state"]
            year = int(meta["year"])
            source_version = path.stem

            df = pd.read_parquet(path)
            if df.empty:
                continue

            value_cols = [c for c in df.columns if c not in _GEO_IDENTITY_COLS]

            for record in df.to_dict(orient="records"):
                geo_id = _geo_id_for_row(record)
                if not geo_id:
                    continue
                geo_name = _safe_str(record.get("NAME"))
                for variable in value_cols:
                    if self._limit is not None and emitted >= self._limit:
                        return
                    yield {
                        "source": self.source,
                        "source_version": source_version,
                        "natural_key": f"{table}:{geography}:{state}:{year}:{geo_id}:{variable}",
                        "table": table,
                        "geography": geography,
                        "state": state,
                        "year": year,
                        "geo_id": geo_id,
                        "geo_name": geo_name,
                        "variable": str(variable),
                        "value": _safe_str(record.get(variable)),
                    }
                    emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[AcsCellRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "table": r.table,
                "geography": r.geography,
                "state": r.state,
                "year": r.year,
                "geo_id": r.geo_id,
                "geo_name": r.geo_name,
                "variable": r.variable,
                "value": r.value,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


# ---------------------------------------------------------------------------
# Preserved verbatim from load_acs.py: the ACS API downloader / cacher.
# The pipeline above consumes the parquet artifacts this class produces.
# (``from config import settings`` is lazily imported inside __init__ so this
# module loads under the ingestion package path; runtime behavior is unchanged.)
# ---------------------------------------------------------------------------


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
        # Lazy import: the repo-root ``config`` package is not on the ingestion
        # package path; importing here keeps module-level import clean.
        from config import settings

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached ACS parquet artifacts into bronze.bronze_census_acs"
    )
    parser.add_argument(
        "--path", type=Path,
        help="Path to a single ACS parquet (default: all in data/cache/census/acs/)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of cells (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = CensusAcsPipeline(path=args.path, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

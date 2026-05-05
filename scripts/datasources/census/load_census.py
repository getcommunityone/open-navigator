"""
Census Bureau Data Ingestion

Downloads and processes Census of Governments data to create master list
of all U.S. local government jurisdictions.

Data Sources:
- Census Bureau Government Integrated Directory (GID)
- Individual State Descriptions
- FIPS codes for standardized identification
"""
import asyncio
import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import httpx
from loguru import logger

try:
    from pyspark.sql import SparkSession, DataFrame
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType
    from pyspark.sql.functions import lit
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkSession = None
    DataFrame = None

from config import settings


class CensusGovernmentIngestion:
    """Ingest Census Bureau government entity data."""
    
    # Census Bureau API endpoint
    CENSUS_API_BASE = "https://api.census.gov/data"
    
    # Census Gazetteer Files 2024 - Actual individual jurisdiction listings with names, FIPS, coordinates, population
    # These provide complete listings of all government entities, not summary statistics
    GID_URLS = {
        # All 3,144 counties with names, FIPS codes, lat/lon, land area, water area
        "counties": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip",
        # All 19,502+ incorporated places (cities, towns, villages, boroughs)
        "municipalities": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip",
        # All 36,011+ county subdivisions (townships, boroughs, census county divisions, unorganized territories)
        "townships": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_cousubs_national.zip",
        # Elementary school districts
        "school_districts_elem": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_elsd_national.zip",
        # Secondary school districts  
        "school_districts_sec": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_scsd_national.zip",
        # Unified school districts
        "school_districts_unified": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_unsd_national.zip",
    }
    
    # Set to False to use real Census data
    USE_MOCK_DATA = False
    
    def __init__(self, spark: Optional[SparkSession] = None):
        """Initialize ingestion with Spark session."""
        if not PYSPARK_AVAILABLE:
            logger.warning("PySpark not available - using mock data mode")
            self.spark = None
        else:
            self.spark = spark or SparkSession.builder.appName("CensusIngestion").getOrCreate()
        self.cache_dir = Path("data/cache/census")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_mock_data(self, jurisdiction_type: str) -> List[Dict[str, Any]]:
        """
        Create mock jurisdiction data for local testing.
        
        This allows the system to run without downloading Census data.
        """
        logger.info(f"Using mock data for {jurisdiction_type}")
        
        mock_data = {
            "counties": [
                {"name": "Los Angeles County", "state": "CA", "state_code": "06", "fips": "06037", "population": "10014009"},
                {"name": "Cook County", "state": "IL", "state_code": "17", "fips": "17031", "population": "5275541"},
                {"name": "Harris County", "state": "TX", "state_code": "48", "fips": "48201", "population": "4731145"},
                {"name": "Maricopa County", "state": "AZ", "state_code": "04", "fips": "04013", "population": "4485414"},
                {"name": "San Diego County", "state": "CA", "state_code": "06", "fips": "06073", "population": "3286069"},
                {"name": "Orange County", "state": "CA", "state_code": "06", "fips": "06059", "population": "3167809"},
                {"name": "Miami-Dade County", "state": "FL", "state_code": "12", "fips": "12086", "population": "2716940"},
                {"name": "Dallas County", "state": "TX", "state_code": "48", "fips": "48113", "population": "2647787"},
                {"name": "Kings County", "state": "NY", "state_code": "36", "fips": "36047", "population": "2559903"},
                {"name": "Riverside County", "state": "CA", "state_code": "06", "fips": "06065", "population": "2470546"},
            ],
            "municipalities": [
                {"name": "New York City", "state": "NY", "state_code": "36", "fips": "3651000", "population": "8336817"},
                {"name": "Los Angeles", "state": "CA", "state_code": "06", "fips": "0644000", "population": "3979576"},
                {"name": "Chicago", "state": "IL", "state_code": "17", "fips": "1714000", "population": "2746388"},
                {"name": "Houston", "state": "TX", "state_code": "48", "fips": "4835000", "population": "2314157"},
                {"name": "Phoenix", "state": "AZ", "state_code": "04", "fips": "0455000", "population": "1680992"},
                {"name": "Philadelphia", "state": "PA", "state_code": "42", "fips": "4260000", "population": "1584064"},
                {"name": "San Antonio", "state": "TX", "state_code": "48", "fips": "4865000", "population": "1547253"},
                {"name": "San Diego", "state": "CA", "state_code": "06", "fips": "0666000", "population": "1423851"},
                {"name": "Dallas", "state": "TX", "state_code": "48", "fips": "4819000", "population": "1343573"},
                {"name": "San Jose", "state": "CA", "state_code": "06", "fips": "0668000", "population": "1013240"},
            ],
            "townships": [
                {"name": "Bloomfield Township", "state": "MI", "state_code": "26", "fips": "2609320", "population": "44253"},
                {"name": "Canton Township", "state": "MI", "state_code": "26", "fips": "2613960", "population": "98659"},
                {"name": "Wayne Township", "state": "IN", "state_code": "18", "fips": "1883718", "population": "97878"},
            ],
            "school_districts": [
                {"name": "Los Angeles Unified School District", "state": "CA", "state_code": "06", "fips": "0600001", "population": "600000"},
                {"name": "Chicago Public Schools", "state": "IL", "state_code": "17", "fips": "1700002", "population": "340000"},
                {"name": "Miami-Dade County Public Schools", "state": "FL", "state_code": "12", "fips": "1200003", "population": "330000"},
            ],
            "special_districts": [
                {"name": "Metropolitan Water District", "state": "CA", "state_code": "06", "fips": "06SD001", "population": "19000000"},
                {"name": "Port Authority of NY & NJ", "state": "NY", "state_code": "36", "fips": "36SD002", "population": "21000000"},
            ]
        }
        
        return mock_data.get(jurisdiction_type, [])
    
    async def download_census_data(self, jurisdiction_type: str) -> Path:
        """
        Download Census Gazetteer data for a jurisdiction type.
        
        Census Gazetteer files are tab-delimited text files inside ZIP archives.
        These contain actual jurisdiction listings with names, FIPS codes, coordinates, and population.
        
        Args:
            jurisdiction_type: One of 'counties', 'municipalities', 'townships', 
                             'school_districts', 'census_places'
        
        Returns:
            Path to extracted CSV file
        """
        if jurisdiction_type not in self.GID_URLS:
            raise ValueError(f"Invalid jurisdiction type: {jurisdiction_type}")
        
        url = self.GID_URLS[jurisdiction_type]
        cache_file = self.cache_dir / f"{jurisdiction_type}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        # Use cached file if exists and is recent (< 7 days old)
        if cache_file.exists() and (datetime.now().timestamp() - cache_file.stat().st_mtime) < 604800:
            logger.info(f"Using cached {jurisdiction_type} data from {cache_file}")
            return cache_file
        
        logger.info(f"Downloading {jurisdiction_type} data from Census Bureau...")
        logger.info(f"URL: {url}")
        logger.info(f"This may take 2-5 minutes for large files...")
        
        # Increase timeout for large Census files (some are 100MB+)
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                
                # Save ZIP file
                zip_file = self.cache_dir / f"{jurisdiction_type}_temp.zip"
                zip_file.write_bytes(response.content)
                logger.success(f"Downloaded {len(response.content)} bytes")
                
                # Extract ZIP file
                import zipfile
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    # Extract all files
                    extract_dir = self.cache_dir / f"{jurisdiction_type}_extracted"
                    extract_dir.mkdir(exist_ok=True)
                    zip_ref.extractall(extract_dir)
                    
                    # Find tab-delimited text file (.txt) for Gazetteer files
                    # or CSV/Excel for school districts
                    txt_files = list(extract_dir.glob("*.txt"))
                    csv_files = list(extract_dir.glob("*.csv"))
                    excel_files = list(extract_dir.glob("*.xlsx")) + list(extract_dir.glob("*.xls"))
                    
                    data_file = None
                    if txt_files:
                        # Gazetteer files (tab-delimited)
                        data_file = txt_files[0]
                        logger.info(f"Found Gazetteer file: {data_file.name}")
                        
                        # Convert tab-delimited to CSV using pandas
                        import pandas as pd
                        df = pd.read_csv(data_file, sep='\t', encoding='latin-1', low_memory=False)
                        df.to_csv(cache_file, index=False)
                        logger.success(f"Converted to CSV: {cache_file}")
                        
                    elif csv_files:
                        # Already CSV (some sources)
                        data_file = csv_files[0]
                        logger.info(f"Found CSV file: {data_file.name}")
                        import shutil
                        shutil.copy(data_file, cache_file)
                        logger.success(f"Copied to cache: {cache_file}")
                        
                    elif excel_files:
                        # Excel files (school districts)
                        data_file = excel_files[0]
                        logger.info(f"Found Excel file: {data_file.name}")
                        
                        import pandas as pd
                        df = pd.read_excel(data_file, engine='openpyxl')
                        df.to_csv(cache_file, index=False)
                        logger.success(f"Converted to CSV: {cache_file}")
                        
                    else:
                        raise FileNotFoundError(f"No data file found in ZIP for {jurisdiction_type}")
                    
                    # Clean up
                    zip_file.unlink()
                    import shutil
                    shutil.rmtree(extract_dir)
                    
                    return cache_file
                
            except httpx.TimeoutException as e:
                logger.error(f"Timeout downloading {jurisdiction_type} data after 5 minutes")
                logger.error(f"URL: {url}")
                logger.warning(f"Census server may be slow or file is very large. Try again later or skip {jurisdiction_type}.")
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP error downloading {jurisdiction_type} data: {e}")
                logger.error(f"URL that failed: {url}")
                logger.warning(f"Check if Census Bureau website is accessible or file exists.")
                raise
            except Exception as e:
                logger.error(f"Error processing {jurisdiction_type} data: {e}")
                logger.error(f"File: {url}")
                raise
    
    def parse_csv_to_dataframe(self, csv_path: Path, jurisdiction_type: str) -> DataFrame:
        """
        Parse Census Gazetteer CSV into Spark DataFrame.
        
        Gazetteer files contain actual jurisdiction listings with names, FIPS codes,
        coordinates, land area, and population (when available).
        
        Args:
            csv_path: Path to CSV file
            jurisdiction_type: Type of jurisdiction
        
        Returns:
            Spark DataFrame with standardized columns
        """
        logger.info(f"Parsing {csv_path} into DataFrame...")
        
        # Read CSV with Spark 
        df = self.spark.read.csv(
            str(csv_path),
            header=True,
            inferSchema=True
        )
        
        # Clean column names (Delta Lake doesn't allow spaces or special chars)
        for col_name in df.columns:
            clean_name = col_name.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "_").replace(".", "_")
            if clean_name != col_name:
                df = df.withColumnRenamed(col_name, clean_name)
        
        # Add standardized metadata columns
        df = df.withColumn("jurisdiction_type", lit(jurisdiction_type))
        df = df.withColumn("ingestion_date", lit(datetime.now().isoformat()))
        
        # Gazetteer files have columns like:
        # - USPS (state abbreviation)
        # - GEOID (FIPS code)
        # - NAME (jurisdiction name)
        # - INTPTLAT, INTPTLONG (coordinates)
        # - ALAND, AWATER (land and water area in sq meters)
        # - ALAND_SQMI, AWATER_SQMI (in square miles)
        
        # Add aliases for common columns (if they exist)
        if "USPS" in df.columns:
            df = df.withColumnRenamed("USPS", "state_code")
        if "GEOID" in df.columns:
            df = df.withColumnRenamed("GEOID", "fips_code")
        if "NAME" in df.columns:
            df = df.withColumnRenamed("NAME", "name")
        if "INTPTLAT" in df.columns:
            df = df.withColumnRenamed("INTPTLAT", "latitude")
        if "INTPTLONG" in df.columns:
            df = df.withColumnRenamed("INTPTLONG", "longitude")
        
        logger.success(f"Parsed {df.count()} records from {csv_path}")
        return df
    
    async def ingest_all_jurisdictions(self, skip_school_districts: bool = False) -> Dict[str, DataFrame]:
        """
        Download and parse all jurisdiction types.
        
        Args:
            skip_school_districts: If True, skip school districts (they're large and optional)
        
        Returns:
            Dictionary mapping jurisdiction type to DataFrame
        """
        logger.info("Starting full Census data ingestion...")
        
        dataframes = {}
        
        jurisdiction_types = list(self.GID_URLS.keys())
        
        # Optionally skip school districts (they're very large files and optional for core functionality)
        if skip_school_districts:
            jurisdiction_types = [jt for jt in jurisdiction_types if not jt.startswith('school_districts')]
            logger.info("Skipping school districts (use skip_school_districts=False to include)")
        
        for jurisdiction_type in jurisdiction_types:
            try:
                # Download
                csv_path = await self.download_census_data(jurisdiction_type)
                
                # Parse
                df = self.parse_csv_to_dataframe(csv_path, jurisdiction_type)
                dataframes[jurisdiction_type] = df
                
            except Exception as e:
                logger.error(f"Failed to ingest {jurisdiction_type}: {e}")
                
                # School districts are optional - warn but continue
                if jurisdiction_type.startswith('school_districts'):
                    logger.warning(f"Skipping {jurisdiction_type} (optional). Counties, municipalities, and townships are sufficient for most use cases.")
                
                continue
        
        logger.success(f"Ingested {len(dataframes)} jurisdiction types")
        return dataframes
    
    def write_to_bronze_layer(self, dataframes: Dict[str, DataFrame]):
        """
        Write jurisdiction data to Delta Lake Bronze layer.
        
        Bronze layer stores raw Census Gazetteer data with individual jurisdiction listings.
        Each jurisdiction has name, FIPS code, state, coordinates, and area information.
        
        Args:
            dataframes: Dictionary of jurisdiction DataFrames
        """
        logger.info("Writing jurisdiction data to Bronze layer...")
        
        bronze_path = f"{settings.delta_lake_path}/bronze/jurisdictions"
        
        # Write individual tables
        for jurisdiction_type, df in dataframes.items():
            table_path = f"{bronze_path}/{jurisdiction_type}"
            
            # Write without partitioning for Bronze (raw data)
            df.write \
                .format("delta") \
                .mode("overwrite") \
                .save(table_path)
            
            logger.success(f"Wrote {jurisdiction_type} to {table_path}")
        
        # Note: Each jurisdiction type is stored separately in Bronze layer
        # Gazetteer files have similar schemas (name, FIPS, state, coordinates)
        # Silver layer will create a unified view with standardized columns
        
        total_records = sum(df.count() for df in dataframes.values())
        logger.success(f"Bronze layer complete: {len(dataframes)} tables with {total_records:,} total records")
        
        return {
            "total_records": total_records,
            "tables": len(dataframes)
        }


async def main():
    """Run Census ingestion pipeline."""
    ingestion = CensusGovernmentIngestion()
    
    # Download and parse all data
    # Skip school districts by default (very large files, optional for core functionality)
    # Set skip_school_districts=False if you specifically need school district data
    dataframes = await ingestion.ingest_all_jurisdictions(skip_school_districts=True)
    
    # Write to Delta Lake
    ingestion.write_to_bronze_layer(dataframes)
    
    # Print summary statistics
    for jtype, df in dataframes.items():
        count = df.count()
        states = df.select("state_fips").distinct().count()
        print(f"{jtype}: {count:,} jurisdictions across {states} states")


if __name__ == "__main__":
    asyncio.run(main())

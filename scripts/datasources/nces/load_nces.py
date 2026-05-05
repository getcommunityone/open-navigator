"""
NCES School District Data Ingestion to PostgreSQL

Downloads and processes National Center for Education Statistics (NCES)
Common Core of Data (CCD) to get comprehensive school district information.

Data Source: https://nces.ed.gov/ccd/
Primary Dataset: Local Education Agency (School District) Universe Survey

Loads into PostgreSQL tables:
- jurisdictions_details_schools: District directory info (addresses, websites, phones)
- contacts_school_members: Student enrollment by district
- contacts_school_staff: Staff counts by district and category
"""
import asyncio
import csv
import zipfile
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

import httpx
import psycopg2
from psycopg2.extras import execute_batch
from bs4 import BeautifulSoup
from loguru import logger


class NCESSchoolDistrictIngestion:
    """Ingest NCES Common Core of Data for school districts to PostgreSQL."""
    
    # NCES CCD Files page
    NCES_FILES_PAGE = "https://nces.ed.gov/ccd/files.asp"
    NCES_BASE_URL = "https://nces.ed.gov"
    
    # PostgreSQL connection
    DB_HOST = "localhost"
    DB_PORT = 5433
    DB_NAME = "open_navigator"
    DB_USER = "postgres"
    DB_PASSWORD = "password"
    
    def __init__(self, directory_file: Optional[Path] = None):
        """Initialize ingestion."""
        self.cache_dir = Path("data/cache/nces")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manual_file = directory_file
        self.conn = None
    
    def get_nces_files(self) -> dict:
        """
        Get NCES file URLs for Directory, Membership, and Staff data.
        
        Currently uses known URLs for SY 2024-25 version 1a release.
        
        NCES organizes files by sections on https://nces.ed.gov/ccd/files.asp:
        - Directory → Flat and SAS Files (2.76 MB) - District info, addresses, websites
        - Membership → Flat and SAS Files (62 MB) - Student enrollment by grade/race/sex
        - Staff → Flat and SAS Files (5.8 MB) - Staff counts by professional category
        - Documentation → Companion Files, Release Notes, Data Notes
        
        Future enhancement: Parse HTML to find these section headings and extract
        associated download links dynamically.
        
        Returns:
            Dictionary with 'directory', 'membership', 'staff' file info
        """
        logger.info("Using known NCES file URLs for SY 2024-25 version 1a...")
        
        # SY 2024-25 version 1a Data Release (December 2025)
        # These URLs come from: https://nces.ed.gov/ccd/files.asp
        # Select: Nonfiscal → LEA → 2024-25
        nces_files = {
            'directory': {
                'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_lea_029_2425_w_1a_073025.zip',
                'size': '2.76 MB',
                'description': 'Directory - Flat and SAS Files',
                'cache_file': 'nces_directory.csv'
            },
            'membership': {
                'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_lea_052_2425_l_1a_073025.zip',
                'size': '62 MB',
                'description': 'Membership - Flat and SAS Files',
                'cache_file': 'nces_membership.csv'
            },
            'staff': {
                'url': 'https://nces.ed.gov/ccd/Data/zip/ccd_lea_059_2425_l_1a_073025.zip',
                'size': '5.8 MB',
                'description': 'Staff - Flat and SAS Files',
                'cache_file': 'nces_staff.csv'
            },
            'directory_companion': {
                'url': 'https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Directory_Companion_2026-005d.xlsx',
                'size': '53 KB',
                'description': 'Directory Companion File'
            },
            'membership_companion': {
                'url': 'https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Membership_Companion_2026-005d.xlsx',
                'size': '40 KB',
                'description': 'Membership Companion File'
            },
            'staff_companion': {
                'url': 'https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Staff_Companion_2026-005d.xlsx',
                'size': '44 KB',
                'description': 'Staff Companion File'
            },
            'release_notes': {
                'url': 'https://nces.ed.gov/ccd/doc/SY_2024-25_Universe_1a_CCD_Nonfiscal_Release_Notes.docx',
                'size': '79 KB',
                'description': 'Release Notes'
            },
            'data_notes': {
                'url': 'https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_1a_Data_Notes.xlsx',
                'size': '206 KB',
                'description': 'State Data Notes'
            }
        }
        
        nces_files['school_year'] = "2024-25"
        
        return nces_files
    
    async def download_or_use_manual_file(self) -> Path:
        """
        Get NCES data file - tries automatic discovery first, falls back to manual.
        
        Returns:
            Path to CSV file
        """
        cache_file = self.cache_dir / "nces_school_districts.csv"
        
        # If user provided a manual file, use that
        if self.manual_file and self.manual_file.exists():
            logger.info(f"Using manually provided file: {self.manual_file}")
            return self.manual_file
        
        # Check if cached file exists and is recent
        if cache_file.exists():
            age_days = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).days
            if age_days < 30:
                logger.info(f"Using cached NCES data (age: {age_days} days)")
                return cache_file
        
        # Try automatic discovery and download
        try:
            download_url, school_year = await self.discover_directory_file()
            logger.info(f"Downloading NCES Directory for {school_year}...")
            return await self._download_from_url(download_url, cache_file, school_year)
        except Exception as e:
            logger.error(f"Automatic download failed: {e}")
            logger.error("=" * 80)
            logger.error("AUTOMATIC DOWNLOAD FAILED - MANUAL DOWNLOAD REQUIRED")
            logger.error("=" * 80)
            logger.error("Please manually download NCES Directory data:")
            logger.error("")
            logger.error("Option 1 - Direct Download (SY 2024-25):")
            logger.error("  wget https://nces.ed.gov/ccd/Data/zip/ccd_lea_029_2425_w_1a_073025.zip")
            logger.error("  unzip ccd_lea_029_2425_w_1a_073025.zip")
            logger.error("  mv ccd_lea*.csv data/cache/nces/nces_school_districts.csv")
            logger.error("")
            logger.error("Option 2 - From NCES Website:")
            logger.error("1. Visit: https://nces.ed.gov/ccd/files.asp")
            logger.error("2. Select: Nonfiscal → LEA → Latest year")
            logger.error("3. Find section: 'Directory' → 'Flat and SAS Files' (ZIP)")
            logger.error("4. Extract the CSV file")
            logger.error("5. Place CSV at: data/cache/nces/nces_school_districts.csv")
            logger.error("=" * 80)
            raise FileNotFoundError(f"NCES data not found. Please download manually to {cache_file}")
    
    async def _download_from_url(self, url: str, output_file: Path, school_year: str = "unknown", file_type: str = "unknown") -> Path:
        """Download NCES file from URL and extract if ZIP."""
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:  # 5 min timeout for large files
            logger.info(f"Downloading from: {url}")
            response = await client.get(url)
            response.raise_for_status()
            
            # Check if ZIP or CSV
            if url.endswith('.zip') or 'zip' in url.lower():
                zip_path = self.cache_dir / f"nces_{file_type}_{school_year.replace('-', '')}.zip"
                zip_path.write_bytes(response.content)
                logger.info(f"✅ Downloaded {len(response.content) / 1024 / 1024:.2f} MB ZIP")
                
                # Extract CSV from ZIP
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # List all files
                    all_files = zip_ref.namelist()
                    logger.info(f"ZIP contains {len(all_files)} files")
                    
                    # Find CSV/TXT files
                    csv_files = [f for f in all_files if f.endswith(('.csv', '.txt')) and not f.startswith('__MACOSX')]
                    
                    if not csv_files:
                        logger.warning(f"No CSV/TXT found. Files in ZIP: {all_files[:10]}")
                        raise ValueError(f"No CSV/TXT in ZIP. Found: {all_files}")
                    
                    # Prefer files with 'lea' in name for LEA-level data
                    preferred = [f for f in csv_files if 'lea' in f.lower()]
                    csv_filename = preferred[0] if preferred else csv_files[0]
                    
                    logger.info(f"Extracting {csv_filename}...")
                    zip_ref.extract(csv_filename, self.cache_dir)
                    extracted = self.cache_dir / csv_filename
                    extracted.rename(output_file)
                    logger.info(f"✅ Extracted to {output_file}")
            else:
                # Direct CSV
                output_file.write_bytes(response.content)
                logger.info(f"✅ Downloaded {len(response.content) / 1024 / 1024:.2f} MB CSV")
            
            return output_file
    
    async def download_all_files(self) -> dict:
        """Download Directory, Membership, and Staff files.
        
        Returns:
            Dictionary with paths to 'directory', 'membership', 'staff' CSV files
        """
        files_info = self.get_nces_files()
        school_year = files_info['school_year']
        downloaded_files = {}
        
        # Download each data file
        for file_type in ['directory', 'membership', 'staff']:
            file_info = files_info[file_type]
            cache_file = self.cache_dir / file_info['cache_file']
            
            # Check if cached file exists and is recent
            if cache_file.exists():
                age_days = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).days
                if age_days < 30:
                    logger.info(f"✅ Using cached {file_type} data (age: {age_days} days)")
                    downloaded_files[file_type] = cache_file
                    continue
            
            # Download the file
            try:
                logger.info(f"📥 Downloading {file_type}: {file_info['description']} ({file_info['size']})")
                downloaded_path = await self._download_from_url(file_info['url'], cache_file, school_year, file_type)
                downloaded_files[file_type] = downloaded_path
                logger.info(f"✅ Downloaded {file_type} to {downloaded_path}")
            except Exception as e:
                logger.error(f"❌ Failed to download {file_type}: {e}")
                raise
        
        return downloaded_files
    
    def parse_csv_to_dataframe(self, csv_path: Path) -> DataFrame:
        """
        Parse NCES CSV into standardized DataFrame.
        
        Args:
            csv_path: Path to NCES CSV file
            
        Returns:
            Spark DataFrame with standardized schema
            
        NCES Directory CSV Columns (SY 2024-25):
        - LEAID: NCES district ID
        - LEA_NAME: District name
        - ST: State abbreviation (AL, MA, etc.)
        - FIPST: State FIPS code
        - LSTREET1-3: Location address
        - LCITY: Location city
        - LSTATE: Location state
        - LZIP: Location ZIP code
        - PHONE: Phone number
        - WEBSITE: Website URL
        - LEA_TYPE_TEXT: District type (Regular, Charter, etc.)
        - OPERATIONAL_SCHOOLS: Number of schools
        """
        # Read raw CSV
        raw_df = self.spark.read.csv(
            str(csv_path),
            header=True,
            inferSchema=False
        )
        
        # Map NCES column names to our schema
        mapped_df = raw_df.select(
            col("LEAID").alias("nces_id"),
            col("LEA_NAME").alias("district_name"),
            col("ST").alias("state"),  # State abbreviation
            col("FIPST").alias("state_fips"),
            col("LSTREET1").alias("street_address"),
            col("LCITY").alias("city"),
            col("LZIP").alias("zip"),
            col("PHONE").alias("phone"),
            col("WEBSITE").alias("website"),
            col("LEA_TYPE_TEXT").alias("district_type"),
            col("OPERATIONAL_SCHOOLS").cast("int").alias("num_schools"),
        )
        
        # Clean and standardize
        cleaned_df = mapped_df \
            .withColumn("district_name", trim(col("district_name"))) \
            .withColumn("state", trim(col("state"))) \
            .withColumn("website", trim(lower(col("website")))) \
            .withColumn("website", regexp_replace(col("website"), r"^https?://", "")) \
            .withColumn("website", regexp_replace(col("website"), r"/$", "")) \
            .filter(col("district_name").isNotNull())
        
        logger.info(f"Parsed {cleaned_df.count()} school districts from NCES data")
        
        return cleaned_df
    
    def write_to_bronze_layer(self, df: DataFrame) -> None:
        """
        Write NCES data to Bronze layer.
        
        Args:
            df: NCES school district DataFrame
        """
        # Try Delta Lake if available, otherwise fall back to Parquet
        output_path = f"{self.delta_lake_path}/bronze/nces_school_districts"
        
        try:
            df.write \
                .format("delta") \
                .mode("overwrite") \
                .partitionBy("state") \
                .option("overwriteSchema", "true") \
                .save(output_path)
            logger.info(f"✅ Wrote NCES data to Delta Lake: {output_path}")
        except Exception as e:
            logger.warning(f"Delta Lake not available ({e}), writing to Parquet instead...")
            parquet_path = f"{self.delta_lake_path}/bronze/nces_school_districts_parquet"
            df.write \
                .format("parquet") \
                .mode("overwrite") \
                .partitionBy("state") \
                .option("compression", "snappy") \
                .save(parquet_path)
            logger.info(f"✅ Wrote NCES data to Parquet: {parquet_path}")
    
    def parse_membership_csv(self, csv_path: Path) -> DataFrame:
        """
        Parse NCES Membership CSV (student enrollment data).
        
        Contains: Student counts disaggregated by grade, race/ethnicity, and sex
        Columns: LEAID, GRADE, RACE_ETHNICITY, SEX, STUDENT_COUNT, TOTAL_INDICATOR
        
        We aggregate all rows to get total enrollment per district.
        """
        raw_df = self.spark.read.csv(str(csv_path), header=True, inferSchema=False)
        
        # Sum all student counts per district
        from pyspark.sql.functions import sum as spark_sum
        
        membership_df = raw_df \
            .filter(col("STUDENT_COUNT").isNotNull()) \
            .filter(col("STUDENT_COUNT") != "") \
            .withColumn("student_count_int", col("STUDENT_COUNT").cast("int")) \
            .groupBy("LEAID", "ST", "FIPST") \
            .agg(
                spark_sum("student_count_int").alias("total_students")
            ) \
            .select(
                col("LEAID").alias("nces_id"),
                col("ST").alias("state"),
                col("FIPST").alias("state_fips"),
                col("total_students")
            )
        
        count = membership_df.count()
        logger.info(f"Parsed {count:,} membership records")
        return membership_df
    
    def parse_staff_csv(self, csv_path: Path) -> DataFrame:
        """
        Parse NCES Staff CSV (staff counts by category).
        
        Contains: FTE counts by professional category  
        Columns: LEAID, STAFF (category), STAFF_COUNT, TOTAL_INDICATOR
        
        Categories include: Teachers, Principals, Counselors, Librarians, etc.
        We'll keep the data in long format with staff_category and staff_count columns.
        """
        raw_df = self.spark.read.csv(str(csv_path), header=True, inferSchema=False)
        
        # Filter for rows with actual counts and select key columns
        staff_df = raw_df \
            .filter(col("STAFF_COUNT").isNotNull()) \
            .filter(col("STAFF_COUNT") != "") \
            .select(
                col("LEAID").alias("nces_id"),
                col("ST").alias("state"),
                col("FIPST").alias("state_fips"),
                col("STAFF").alias("staff_category"),
                col("STAFF_COUNT").cast("float").alias("staff_count")
            )
        
        count = staff_df.count()
        logger.info(f"Parsed {count:,} staff records")
        return staff_df
    
    async def ingest_school_districts(self) -> DataFrame:
        """
        Complete ingestion pipeline for NCES school district data.
        
        Returns:
            DataFrame with school district information
        """
        # Get data file (manual or automatic)
        csv_path = await self.download_or_use_manual_file()
        
        # Parse to DataFrame
        df = self.parse_csv_to_dataframe(csv_path)
        
        # Write to Bronze layer
        self.write_to_bronze_layer(df)
        
        return df
    
    async def ingest_all_datasets(self) -> dict:
        """
        Complete ingestion pipeline for ALL NCES datasets.
        
        Downloads and processes:
        - Directory: District info, addresses, websites
        - Membership: Student enrollment counts
        - Staff: Teacher/staff FTE counts
        
        Returns:
            Dictionary with 'directory', 'membership', 'staff' DataFrames
        """
        # Download all files
        file_paths = await self.download_all_files()
        
        results = {}
        
        # Parse Directory data
        logger.info("\n" + "=" * 80)
        logger.info("📁 Processing Directory data...")
        directory_df = self.parse_csv_to_dataframe(file_paths['directory'])
        self.write_to_bronze_layer(directory_df)
        results['directory'] = directory_df
        
        # Parse Membership data
        logger.info("\n" + "=" * 80)
        logger.info("👥 Processing Membership data...")
        membership_df = self.parse_membership_csv(file_paths['membership'])
        membership_path = f"{self.delta_lake_path}/bronze/nces_membership_parquet"
        membership_df.write.format("parquet").mode("overwrite").partitionBy("state").save(membership_path)
        logger.info(f"✅ Wrote membership data to {membership_path}")
        results['membership'] = membership_df
        
        # Parse Staff data
        logger.info("\n" + "=" * 80)
        logger.info("👨‍🏫 Processing Staff data...")
        staff_df = self.parse_staff_csv(file_paths['staff'])
        staff_path = f"{self.delta_lake_path}/bronze/nces_staff_parquet"
        staff_df.write.format("parquet").mode("overwrite").partitionBy("state").save(staff_path)
        logger.info(f"✅ Wrote staff data to {staff_path}")
        results['staff'] = staff_df
        
        return results


async def main():
    """Test NCES ingestion with all datasets."""
    ingestion = NCESSchoolDistrictIngestion()
    
    # Ingest all three datasets
    results = await ingestion.ingest_all_datasets()
    
    # Show Directory data
    print("\n" + "=" * 80)
    print("📁 DIRECTORY DATA - District Info, Addresses, Websites")
    print("=" * 80)
    results['directory'].show(10, truncate=False)
    print(f"\nTotal districts: {results['directory'].count():,}")
    
    # Show Membership data
    print("\n" + "=" * 80)
    print("👥 MEMBERSHIP DATA - Student Enrollment")
    print("=" * 80)
    results['membership'].show(10, truncate=False)
    print(f"\nTotal enrollment records: {results['membership'].count():,}")
    
    # Show Staff data
    print("\n" + "=" * 80)
    print("👨‍🏫 STAFF DATA - Teacher/Staff Counts")
    print("=" * 80)
    results['staff'].show(10, truncate=False)
    print(f"\nTotal staff records: {results['staff'].count():,}")
    
    # Statistics
    print("\n" + "=" * 80)
    print("📈 STATISTICS BY STATE")
    print("=" * 80)
    results['directory'].groupBy("state").count().orderBy(col("count").desc()).show(15)


if __name__ == "__main__":
    asyncio.run(main())

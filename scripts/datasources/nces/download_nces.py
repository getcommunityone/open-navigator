"""
NCES School District Data Ingestion (local Parquet)

Downloads and processes National Center for Education Statistics (NCES)
Common Core of Data (CCD) for school districts — **pandas + PyArrow only**
(no Spark/Java). Outputs Hive-style partitioned Parquet under ``data/lake/bronze/``.

Data Source: https://nces.ed.gov/ccd/
Primary Dataset: Local Education Agency (School District) Universe Survey

Written artifacts:
- ``data/lake/bronze/nces_school_districts_parquet`` (partitioned by ``state``)
- ``data/lake/bronze/nces_membership_parquet``
- ``data/lake/bronze/nces_staff_parquet``
"""
from __future__ import annotations

import asyncio
import re
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from loguru import logger


class NCESSchoolDistrictIngestion:
    """Ingest NCES Common Core of Data for school districts into local Parquet."""

    NCES_FILES_PAGE = "https://nces.ed.gov/ccd/files.asp"
    NCES_BASE_URL = "https://nces.ed.gov"

    DB_HOST = "localhost"
    DB_PORT = 5433
    DB_NAME = "open_navigator"
    DB_USER = "postgres"
    DB_PASSWORD = "password"

    def __init__(self, directory_file: Optional[Path] = None):
        self.cache_dir = Path("data/cache/nces")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manual_file = directory_file
        self.conn = None
        lake_root = Path.cwd() / "data" / "lake"
        lake_root.mkdir(parents=True, exist_ok=True)
        self.delta_lake_path = str(lake_root.resolve())

    async def discover_directory_file(self) -> tuple[str, str]:
        meta = self.get_nces_files()
        return meta["directory"]["url"], meta["school_year"]

    def get_nces_files(self) -> dict:
        logger.info("Using known NCES file URLs for SY 2024-25 version 1a...")
        nces_files = {
            "directory": {
                "url": "https://nces.ed.gov/ccd/Data/zip/ccd_lea_029_2425_w_1a_073025.zip",
                "size": "2.76 MB",
                "description": "Directory - Flat and SAS Files",
                "cache_file": "nces_directory.csv",
            },
            "membership": {
                "url": "https://nces.ed.gov/ccd/Data/zip/ccd_lea_052_2425_l_1a_073025.zip",
                "size": "62 MB",
                "description": "Membership - Flat and SAS Files",
                "cache_file": "nces_membership.csv",
            },
            "staff": {
                "url": "https://nces.ed.gov/ccd/Data/zip/ccd_lea_059_2425_l_1a_073025.zip",
                "size": "5.8 MB",
                "description": "Staff - Flat and SAS Files",
                "cache_file": "nces_staff.csv",
            },
            "directory_companion": {
                "url": "https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Directory_Companion_2026-005d.xlsx",
                "size": "53 KB",
                "description": "Directory Companion File",
            },
            "membership_companion": {
                "url": "https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Membership_Companion_2026-005d.xlsx",
                "size": "40 KB",
                "description": "Membership Companion File",
            },
            "staff_companion": {
                "url": "https://nces.ed.gov/ccd/xls/SY_2024-25_LEA_Staff_Companion_2026-005d.xlsx",
                "size": "44 KB",
                "description": "Staff Companion File",
            },
            "release_notes": {
                "url": "https://nces.ed.gov/ccd/doc/SY_2024-25_Universe_1a_CCD_Nonfiscal_Release_Notes.docx",
                "size": "79 KB",
                "description": "Release Notes",
            },
            "data_notes": {
                "url": "https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_1a_Data_Notes.xlsx",
                "size": "206 KB",
                "description": "State Data Notes",
            },
        }
        nces_files["school_year"] = "2024-25"
        return nces_files

    async def download_or_use_manual_file(self) -> Path:
        from datetime import datetime

        cache_file = self.cache_dir / "nces_school_districts.csv"
        if self.manual_file and self.manual_file.exists():
            logger.info(f"Using manually provided file: {self.manual_file}")
            return self.manual_file
        if cache_file.exists():
            age_days = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).days
            if age_days < 30:
                logger.info(f"Using cached NCES data (age: {age_days} days)")
                return cache_file
        try:
            download_url, school_year = await self.discover_directory_file()
            logger.info(f"Downloading NCES Directory for {school_year}...")
            return await self._download_from_url(download_url, cache_file, school_year)
        except Exception as e:
            logger.error(f"Automatic download failed: {e}")
            logger.error("MANUAL DOWNLOAD REQUIRED — see README under scripts/datasources/nces/")
            raise FileNotFoundError(f"NCES data not found. Please download manually to {cache_file}") from e

    async def _download_from_url(
        self,
        url: str,
        output_file: Path,
        school_year: str = "unknown",
        file_type: str = "unknown",
    ) -> Path:
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            logger.info(f"Downloading from: {url}")
            response = await client.get(url)
            response.raise_for_status()
            if url.endswith(".zip") or "zip" in url.lower():
                zip_path = self.cache_dir / f"nces_{file_type}_{school_year.replace('-', '')}.zip"
                zip_path.write_bytes(response.content)
                logger.info(f"✅ Downloaded {len(response.content) / 1024 / 1024:.2f} MB ZIP")
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    all_files = zip_ref.namelist()
                    csv_files = [
                        f for f in all_files if f.endswith((".csv", ".txt")) and not f.startswith("__MACOSX")
                    ]
                    if not csv_files:
                        raise ValueError(f"No CSV/TXT in ZIP. Found: {all_files}")
                    preferred = [f for f in csv_files if "lea" in f.lower()]
                    csv_filename = preferred[0] if preferred else csv_files[0]
                    logger.info(f"Extracting {csv_filename}...")
                    zip_ref.extract(csv_filename, self.cache_dir)
                    extracted = self.cache_dir / csv_filename
                    extracted.rename(output_file)
                    logger.info(f"✅ Extracted to {output_file}")
            else:
                output_file.write_bytes(response.content)
                logger.info(f"✅ Downloaded {len(response.content) / 1024 / 1024:.2f} MB CSV")
            return output_file

    async def download_all_files(self) -> dict:
        from datetime import datetime

        files_info = self.get_nces_files()
        school_year = files_info["school_year"]
        downloaded_files: dict[str, Path] = {}
        for file_type in ["directory", "membership", "staff"]:
            file_info = files_info[file_type]
            cache_file = self.cache_dir / file_info["cache_file"]
            if cache_file.exists():
                age_days = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).days
                if age_days < 30:
                    logger.info(f"✅ Using cached {file_type} data (age: {age_days} days)")
                    downloaded_files[file_type] = cache_file
                    continue
            logger.info(f"📥 Downloading {file_type}: {file_info['description']} ({file_info['size']})")
            downloaded_path = await self._download_from_url(
                file_info["url"], cache_file, school_year, file_type
            )
            downloaded_files[file_type] = downloaded_path
            logger.info(f"✅ Downloaded {file_type} to {downloaded_path}")
        return downloaded_files

    @staticmethod
    def _clean_website(series: pd.Series) -> pd.Series:
        def one(val: object) -> str | float:
            if pd.isna(val) or val is None or str(val).strip() == "":
                return pd.NA
            t = str(val).strip().lower()
            t = re.sub(r"^https?://", "", t)
            t = re.sub(r"/$", "", t)
            return t

        return series.map(one)

    def parse_csv_to_dataframe(self, csv_path: Path) -> pd.DataFrame:
        raw = pd.read_csv(csv_path, dtype=str, low_memory=False)
        rename_map = {
            "LEAID": "nces_id",
            "LEA_NAME": "district_name",
            "ST": "state",
            "FIPST": "state_fips",
            "LSTREET1": "street_address",
            "LCITY": "city",
            "LZIP": "zip",
            "PHONE": "phone",
            "WEBSITE": "website",
            "LEA_TYPE_TEXT": "district_type",
            "OPERATIONAL_SCHOOLS": "num_schools",
        }
        missing = [c for c in rename_map if c not in raw.columns]
        if missing:
            logger.warning(f"NCES directory CSV missing columns (skipped): {missing}")
        use = {k: v for k, v in rename_map.items() if k in raw.columns}
        df = raw[list(use.keys())].rename(columns=use)
        if "district_name" in df.columns:
            df["district_name"] = df["district_name"].astype(str).str.strip()
        if "state" in df.columns:
            df["state"] = df["state"].astype(str).str.strip()
        if "website" in df.columns:
            df["website"] = self._clean_website(df["website"])
        if "num_schools" in df.columns:
            df["num_schools"] = pd.to_numeric(df["num_schools"], errors="coerce").astype("Int64")
        df = df[df["district_name"].notna() & (df["district_name"].astype(str).str.len() > 0)]
        logger.info(f"Parsed {len(df):,} school districts from NCES directory")
        return df

    def _write_hive_partitioned_parquet(
        self, df: pd.DataFrame, dest: Path, partition_cols: list[str]
    ) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        df.to_parquet(
            dest,
            partition_cols=partition_cols,
            engine="pyarrow",
            compression="snappy",
            index=False,
        )

    def write_to_bronze_layer(self, df: pd.DataFrame) -> None:
        output_path = Path(self.delta_lake_path) / "bronze" / "nces_school_districts_parquet"
        self._write_hive_partitioned_parquet(df, output_path, ["state"])
        logger.info(f"✅ Wrote NCES directory Parquet (partitioned by state): {output_path}")

    def parse_membership_csv(self, csv_path: Path) -> pd.DataFrame:
        raw = pd.read_csv(csv_path, dtype=str, low_memory=False)
        if "STUDENT_COUNT" not in raw.columns:
            raise ValueError("Membership CSV missing STUDENT_COUNT column")
        raw = raw[raw["STUDENT_COUNT"].notna() & (raw["STUDENT_COUNT"].astype(str).str.strip() != "")]
        raw["student_count_int"] = pd.to_numeric(raw["STUDENT_COUNT"], errors="coerce")
        raw = raw.dropna(subset=["student_count_int"])
        grouped = (
            raw.groupby(["LEAID", "ST", "FIPST"], as_index=False)["student_count_int"]
            .sum()
            .rename(
                columns={
                    "LEAID": "nces_id",
                    "ST": "state",
                    "FIPST": "state_fips",
                    "student_count_int": "total_students",
                }
            )
        )
        grouped["total_students"] = grouped["total_students"].astype("Int64")
        logger.info(f"Parsed {len(grouped):,} membership (district) rows")
        return grouped

    def parse_staff_csv(self, csv_path: Path) -> pd.DataFrame:
        raw = pd.read_csv(csv_path, dtype=str, low_memory=False)
        need = ["LEAID", "ST", "FIPST", "STAFF", "STAFF_COUNT"]
        for c in need:
            if c not in raw.columns:
                raise ValueError(f"Staff CSV missing column {c}")
        raw = raw[raw["STAFF_COUNT"].notna() & (raw["STAFF_COUNT"].astype(str).str.strip() != "")]
        staff_df = pd.DataFrame(
            {
                "nces_id": raw["LEAID"],
                "state": raw["ST"],
                "state_fips": raw["FIPST"],
                "staff_category": raw["STAFF"],
                "staff_count": pd.to_numeric(raw["STAFF_COUNT"], errors="coerce"),
            }
        )
        staff_df = staff_df.dropna(subset=["staff_count"])
        logger.info(f"Parsed {len(staff_df):,} staff rows")
        return staff_df

    async def ingest_school_districts(self) -> pd.DataFrame:
        csv_path = await self.download_or_use_manual_file()
        df = self.parse_csv_to_dataframe(csv_path)
        self.write_to_bronze_layer(df)
        return df

    async def ingest_all_datasets(self) -> dict:
        file_paths = await self.download_all_files()
        results: dict[str, pd.DataFrame] = {}
        logger.info("\n" + "=" * 80)
        logger.info("📁 Processing Directory data...")
        directory_df = self.parse_csv_to_dataframe(file_paths["directory"])
        self.write_to_bronze_layer(directory_df)
        results["directory"] = directory_df

        logger.info("\n" + "=" * 80)
        logger.info("👥 Processing Membership data...")
        membership_df = self.parse_membership_csv(file_paths["membership"])
        membership_path = Path(self.delta_lake_path) / "bronze" / "nces_membership_parquet"
        self._write_hive_partitioned_parquet(membership_df, membership_path, ["state"])
        logger.info(f"✅ Wrote membership data to {membership_path}")
        results["membership"] = membership_df

        logger.info("\n" + "=" * 80)
        logger.info("👨‍🏫 Processing Staff data...")
        staff_df = self.parse_staff_csv(file_paths["staff"])
        staff_path = Path(self.delta_lake_path) / "bronze" / "nces_staff_parquet"
        self._write_hive_partitioned_parquet(staff_df, staff_path, ["state"])
        logger.info(f"✅ Wrote staff data to {staff_path}")
        results["staff"] = staff_df
        return results


async def main():
    ingestion = NCESSchoolDistrictIngestion()
    results = await ingestion.ingest_all_datasets()

    print("\n" + "=" * 80)
    print("📁 DIRECTORY DATA - District Info, Addresses, Websites")
    print("=" * 80)
    print(results["directory"].head(10).to_string())
    print(f"\nTotal districts: {len(results['directory']):,}")

    print("\n" + "=" * 80)
    print("👥 MEMBERSHIP DATA - Student Enrollment")
    print("=" * 80)
    print(results["membership"].head(10).to_string())
    print(f"\nTotal enrollment rows (districts): {len(results['membership']):,}")

    print("\n" + "=" * 80)
    print("👨‍🏫 STAFF DATA - Teacher/Staff Counts")
    print("=" * 80)
    print(results["staff"].head(10).to_string())
    print(f"\nTotal staff rows: {len(results['staff']):,}")

    print("\n" + "=" * 80)
    print("📈 TOP STATES BY DISTRICT COUNT")
    print("=" * 80)
    top = results["directory"].groupby("state").size().sort_values(ascending=False).head(15)
    print(top.to_string())


if __name__ == "__main__":
    asyncio.run(main())

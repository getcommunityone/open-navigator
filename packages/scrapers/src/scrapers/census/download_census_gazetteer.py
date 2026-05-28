"""
Census Bureau Gazetteer Downloader

Downloads Census Gazetteer files and writes gold-layer parquet files:
  data/gold/jurisdictions_cities.parquet
  data/gold/jurisdictions_counties.parquet
  data/gold/jurisdictions_townships.parquet
  data/gold/jurisdictions_postal_codes.parquet
  data/gold/jurisdictions_school_districts.parquet

Data Sources:
- Census Bureau Gazetteer Files (tab-delimited, inside ZIP archives)
- https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html

Usage:
    python3 packages/scrapers/src/scrapers/census/download_census_gazetteer.py
    python3 packages/scrapers/src/scrapers/census/download_census_gazetteer.py --skip-school-districts
    python3 packages/scrapers/src/scrapers/census/download_census_gazetteer.py --types counties municipalities
"""
import sys
import asyncio
import argparse
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import pandas as pd
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


CACHE_DIR = Path("data/cache/census/gazetteer")
GOLD_DIR = Path("data/gold")

GID_URLS = {
    "states": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_state_national.zip",
    "counties": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip",
    "municipalities": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip",
    "townships": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_cousubs_national.zip",
    "zcta": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip",
    "school_districts_elem": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_elsd_national.zip",
    "school_districts_sec": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_scsd_national.zip",
    "school_districts_unified": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_unsd_national.zip",
}

# Maps download type → gold output file (school district types are merged into one file)
GOLD_OUTPUT = {
    "states": "jurisdictions_states.parquet",
    "counties": "jurisdictions_counties.parquet",
    "municipalities": "jurisdictions_cities.parquet",
    "townships": "jurisdictions_townships.parquet",
    "zcta": "jurisdictions_postal_codes.parquet",
    "school_districts_elem": "jurisdictions_school_districts.parquet",
    "school_districts_sec": "jurisdictions_school_districts.parquet",
    "school_districts_unified": "jurisdictions_school_districts.parquet",
}

# State FIPS → abbreviation lookup (for types that only carry FIPS, not USPS)
STATE_FIPS_TO_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY", "60": "AS", "66": "GU", "69": "MP",
    "72": "PR", "78": "VI",
}


async def download_gazetteer(jurisdiction_type: str) -> Optional[Path]:
    """Download and extract a Census Gazetteer ZIP, returning the CSV cache path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    url = GID_URLS[jurisdiction_type]
    cache_file = CACHE_DIR / f"{jurisdiction_type}.csv"

    if cache_file.exists() and (datetime.now().timestamp() - cache_file.stat().st_mtime) < 604800:
        logger.info(f"✅ Using cached {jurisdiction_type}: {cache_file}")
        return cache_file

    logger.info(f"📥 Downloading {jurisdiction_type} from Census Bureau...")
    logger.info(f"   {url}")

    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code} for {jurisdiction_type}: {url}")
            return None
        except httpx.TimeoutException:
            logger.error(f"❌ Timeout downloading {jurisdiction_type} (>5 min)")
            return None

    zip_path = CACHE_DIR / f"{jurisdiction_type}_temp.zip"
    zip_path.write_bytes(response.content)
    logger.success(f"   Downloaded {len(response.content) / 1024 / 1024:.1f} MB")

    extract_dir = CACHE_DIR / f"{jurisdiction_type}_extracted"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # Gazetteer files are tab-delimited .txt; some sources use .csv or .xlsx
    txt_files = list(extract_dir.glob("*.txt"))
    csv_files = list(extract_dir.glob("*.csv"))
    excel_files = list(extract_dir.glob("*.xlsx")) + list(extract_dir.glob("*.xls"))

    df = None
    if txt_files:
        df = pd.read_csv(txt_files[0], sep="\t", encoding="latin-1", low_memory=False)
    elif csv_files:
        df = pd.read_csv(csv_files[0], low_memory=False)
    elif excel_files:
        df = pd.read_excel(excel_files[0], engine="openpyxl")
    else:
        logger.error(f"❌ No data file found in ZIP for {jurisdiction_type}")
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)
        return None

    df.columns = [c.strip() for c in df.columns]
    df.to_csv(cache_file, index=False)
    logger.success(f"   Saved {len(df):,} rows → {cache_file}")

    zip_path.unlink(missing_ok=True)
    shutil.rmtree(extract_dir, ignore_errors=True)
    return cache_file


def normalize_dataframe(df: pd.DataFrame, jurisdiction_type: str) -> pd.DataFrame:
    """Standardize column names to match what migrate.py expects."""
    df.columns = [c.strip() for c in df.columns]

    # Derive USPS (state abbreviation) from GEOID prefix if missing
    if "USPS" not in df.columns and "GEOID" in df.columns:
        df["USPS"] = df["GEOID"].astype(str).str.zfill(5).str[:2].map(STATE_FIPS_TO_ABBR)

    df["jurisdiction_type"] = jurisdiction_type
    return df


def write_gold_parquets(dataframes: Dict[str, pd.DataFrame]) -> None:
    """Merge dataframes by output file and write to data/gold/."""
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    # Group types that share an output file
    output_groups: Dict[str, List[pd.DataFrame]] = {}
    for jtype, df in dataframes.items():
        out = GOLD_OUTPUT[jtype]
        output_groups.setdefault(out, []).append(df)

    for filename, dfs in output_groups.items():
        combined = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        # Coerce mixed-type object columns to string so PyArrow can serialize them
        for col in combined.select_dtypes(include="object").columns:
            combined[col] = combined[col].astype(str)
        out_path = GOLD_DIR / filename
        combined.to_parquet(out_path, index=False)
        logger.success(f"✅ Wrote {len(combined):,} rows → {out_path}")


async def main(types: List[str] = None, skip_school_districts: bool = False) -> None:
    if types is None:
        types = list(GID_URLS.keys())
    if skip_school_districts:
        types = [t for t in types if not t.startswith("school_districts")]

    logger.info(f"Downloading {len(types)} Gazetteer file(s): {', '.join(types)}")

    dataframes: Dict[str, pd.DataFrame] = {}
    for jtype in types:
        csv_path = await download_gazetteer(jtype)
        if csv_path is None:
            continue
        df = pd.read_csv(csv_path, low_memory=False)
        df = normalize_dataframe(df, jtype)
        dataframes[jtype] = df
        logger.info(f"  {jtype}: {len(df):,} records")

    if not dataframes:
        logger.error("No data downloaded — nothing to write.")
        return

    write_gold_parquets(dataframes)
    logger.success(f"Done. {len(dataframes)} dataset(s) written to {GOLD_DIR}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Census Gazetteer files → gold parquet")
    parser.add_argument(
        "--types", nargs="+", choices=list(GID_URLS.keys()),
        help="Specific types to download (default: all)"
    )
    parser.add_argument(
        "--skip-school-districts", action="store_true",
        help="Skip school district files (large, optional)"
    )
    args = parser.parse_args()
    asyncio.run(main(types=args.types, skip_school_districts=args.skip_school_districts))

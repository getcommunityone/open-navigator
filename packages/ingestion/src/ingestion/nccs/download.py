#!/usr/bin/env python3
"""NCCS (National Center for Charitable Statistics) Bulk Downloader.

Download-only port to core_lib.http.BaseAsyncClient. Fetches Unified BMF
(Business Master File), Transformed BMF, and Raw BMF data from the National
Center for Charitable Statistics S3 bucket into the local cache.

Directory Structure (CACHE_DIR = data/cache/nccs/):
    data/cache/nccs/
    ├── unified-bmf/
    │   └── v1.2/
    │       ├── full/
    │       │   └── UNIFIED_BMF_V1.2.csv
    │       ├── by-state/
    │       │   ├── AL.csv
    │       │   └── ...
    │       └── data-dictionary/
    │           └── harmonized_data_dictionary.xlsx
    ├── transformed-bmf/
    │   └── {YYYY_MM}/
    └── raw-bmf/

Website: https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html

Usage:
    # Download everything
    python -m ingestion.nccs.download

    # Download specific states only
    python -m ingestion.nccs.download --dataset unified --states CA,NY,TX

    # Force re-download (ignore cached files)
    python -m ingestion.nccs.download --force
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from loguru import logger

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging


CACHE_DIR = Path("data/cache/nccs")

# S3 host serving the bulk data files (base_url for the client).
BASE_URL = "https://nccsdata.s3.us-east-1.amazonaws.com"
# Catalog page scraped to discover the actual per-state file URLs.
CATALOG_URL = "https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html"

# Minimum size (bytes) for a cached file to count as a real download.
_MIN_FILE_SIZE = 1024

STATES = {
    'AK': 'Alaska', 'AL': 'Alabama', 'AR': 'Arkansas', 'AS': 'American Samoa',
    'AZ': 'Arizona', 'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut',
    'DC': 'District of Columbia', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'GU': 'Guam', 'HI': 'Hawaii', 'IA': 'Iowa', 'ID': 'Idaho', 'IL': 'Illinois',
    'IN': 'Indiana', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'MA': 'Massachusetts', 'MD': 'Maryland', 'ME': 'Maine', 'MI': 'Michigan',
    'MN': 'Minnesota', 'MO': 'Missouri', 'MP': 'Northern Mariana Islands',
    'MS': 'Mississippi', 'MT': 'Montana', 'NC': 'North Carolina', 'ND': 'North Dakota',
    'NE': 'Nebraska', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
    'NV': 'Nevada', 'NY': 'New York', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
    'PA': 'Pennsylvania', 'PR': 'Puerto Rico', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VA': 'Virginia', 'VI': 'U.S. Virgin Islands', 'VT': 'Vermont', 'WA': 'Washington',
    'WI': 'Wisconsin', 'WV': 'West Virginia', 'WY': 'Wyoming', 'ZZ': 'Unmapped'
}

TRANSFORMED_MONTHS = [
    '2023_06', '2023_07', '2023_08', '2023_09', '2023_10', '2023_11', '2023_12',
    '2024_01', '2024_02', '2024_03', '2024_04', '2024_05', '2024_06', '2024_07',
    '2024_08', '2024_09', '2024_10', '2024_11', '2024_12',
    '2025_01', '2025_02', '2025_03', '2025_04', '2025_05', '2025_06', '2025_07',
    '2025_08', '2025_09', '2025_10', '2025_11', '2025_12',
    '2026_01'
]

RAW_MONTHS = [
    '2023-06', '2023-07', '2023-08', '2023-09', '2023-10', '2023-11', '2023-12',
    '2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06', '2024-07',
    '2024-08', '2024-09', '2024-10', '2024-11', '2024-12',
    '2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', '2025-07',
    '2025-08', '2025-09', '2025-10', '2025-11', '2025-12',
    '2026-01'
]


def _is_fresh(path: Path) -> bool:
    """A cached file is fresh if it exists and is larger than the min size.

    Mirrors the original ``_is_downloaded`` heuristic (exists and > 1KB), which
    guards against truncated/zero-byte writes from interrupted downloads.
    """
    return path.exists() and path.stat().st_size > _MIN_FILE_SIZE


def _parse_state_files(html: bytes) -> dict[str, tuple[str, str]]:
    """Parse the NCCS catalog HTML to discover per-state file URLs.

    Returns a mapping ``state_code -> (url, state_name)``. Pure helper preserved
    verbatim from the original ``_discover_state_files`` scraping logic.
    """
    from bs4 import BeautifulSoup  # lazy: optional dep, only needed for scraping

    soup = BeautifulSoup(html, 'html.parser')
    state_files: dict[str, tuple[str, str]] = {}

    for link in soup.find_all('a', class_='button'):
        href = link.get('href', '')

        if '/bmf/unified/' in href and '_BMF_' in href and href.endswith('.csv'):
            filename = href.split('/')[-1]
            state_code = filename.split('_')[0].upper()

            row = link.find_parent('tr')
            if row:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    state_name = cells[2].get_text(strip=True)
                else:
                    state_name = STATES.get(state_code, state_code)
            else:
                state_name = STATES.get(state_code, state_code)

            if not href.startswith('http'):
                href = f"https:{href}" if href.startswith('//') else f"https://nccsdata.s3.amazonaws.com{href}"

            state_files[state_code] = (href, state_name)

    return state_files


def _unified_specs(
    cache_dir: Path,
    discovered_states: dict[str, tuple[str, str]],
    states: list[str] | None,
    download_full: bool,
) -> list[tuple[str, Path, str]]:
    """Build (url, dest_path, description) specs for the Unified BMF dataset."""
    unified_dir = cache_dir / "unified-bmf" / "v1.2"
    specs: list[tuple[str, Path, str]] = []

    dict_url = f"{BASE_URL}/harmonized/harmonized_data_dictionary.xlsx"
    dict_path = unified_dir / "data-dictionary" / "harmonized_data_dictionary.xlsx"
    specs.append((dict_url, dict_path, "Data Dictionary"))

    if download_full:
        full_url = f"{BASE_URL}/bmf/unified/v1.2/UNIFIED_BMF_V1.2.csv"
        full_path = unified_dir / "full" / "UNIFIED_BMF_V1.2.csv"
        specs.append((full_url, full_path, "Full Unified BMF"))

    states_to_download = states if states else list(STATES.keys())

    if not states and discovered_states:
        for state_code in discovered_states:
            if state_code not in states_to_download and state_code == 'ZZ':
                states_to_download.append(state_code)

    for state_code in states_to_download:
        if state_code in discovered_states:
            state_url, state_name = discovered_states[state_code]
        elif state_code in STATES:
            state_name_enc = STATES[state_code].replace(' ', '%20')
            state_url = f"{BASE_URL}/bmf/unified/v1.2/{state_name_enc}.csv"
            state_name = STATES[state_code]
        else:
            logger.warning(f"Unknown state code: {state_code}")
            continue

        state_path = unified_dir / "by-state" / f"{state_code}.csv"
        specs.append((state_url, state_path, f"Unified BMF - {state_name} ({state_code})"))

    return specs


def _transformed_specs(cache_dir: Path, months: list[str] | None) -> list[tuple[str, Path, str]]:
    """Build (url, dest_path, description) specs for the Transformed BMF dataset."""
    transformed_dir = cache_dir / "transformed-bmf"
    specs: list[tuple[str, Path, str]] = []

    for month in (months or TRANSFORMED_MONTHS):
        if month not in TRANSFORMED_MONTHS:
            logger.warning(f"Invalid month: {month}")
            continue
        specs.extend([
            (
                f"{BASE_URL}/processed/bmf/{month}/bmf_{month}_processed.csv",
                transformed_dir / month / f"bmf_{month}_processed.csv",
                f"Transformed BMF {month}",
            ),
            (
                f"{BASE_URL}/processed/bmf/{month}/bmf_{month}_data_dictionary.csv",
                transformed_dir / month / f"bmf_{month}_data_dictionary.csv",
                f"Data Dictionary {month}",
            ),
        ])

    return specs


def _raw_specs(cache_dir: Path, months: list[str] | None) -> list[tuple[str, Path, str]]:
    """Build (url, dest_path, description) specs for the Raw BMF dataset."""
    raw_dir = cache_dir / "raw-bmf"
    specs: list[tuple[str, Path, str]] = []

    for month in (months or RAW_MONTHS):
        if month not in RAW_MONTHS:
            logger.warning(f"Invalid month: {month}")
            continue
        specs.append((
            f"{BASE_URL}/raw/bmf/{month}-BMF.csv",
            raw_dir / f"{month}-BMF.csv",
            f"Raw BMF {month}",
        ))

    return specs


class NccsClient(BaseAsyncClient):
    """Async client for the NCCS S3 bucket and catalog page."""

    def __init__(self) -> None:
        super().__init__(
            HttpClientConfig(
                base_url=BASE_URL,
                source="nccs",
                # NCCS bulk pulls many files (data dict, full BMF, ~57 states,
                # transformed + raw months); throttle to be polite to S3.
                rate_limit_per_sec=5.0,
                timeout_s=120.0,
                default_headers={"User-Agent": "Mozilla/5.0 (NCCS Bulk Downloader/1.0)"},
            )
        )

    async def discover_state_files(self) -> dict[str, tuple[str, str]]:
        """Scrape the catalog page to discover actual per-state file URLs."""
        logger.info("Discovering state file URLs from catalog page...")
        try:
            resp = await self.get(CATALOG_URL)
            state_files = _parse_state_files(resp.content)
            logger.info(f"Discovered {len(state_files)} state files from catalog")
            return state_files
        except Exception as exc:  # noqa: BLE001 - fall back to constructed URLs
            logger.warning(f"Failed to scrape catalog page: {exc}")
            logger.info("Falling back to constructed URLs...")
            return {}

    async def fetch_to(self, url: str, dest_path: Path) -> bool:
        """Download ``url`` into ``dest_path``. Returns True on success.

        A failed fetch (e.g. 404/403 for a month/state not published yet) is
        treated as a soft miss, matching the original skip-on-unavailable
        behaviour.
        """
        try:
            resp = await self.get(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"File not available (skipping): {dest_path.name} ({exc})")
            return False

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(resp.content)
        logger.success(f"Downloaded: {dest_path.name} ({len(resp.content):,} bytes)")
        return True


async def download(
    *,
    force: bool = False,
    dataset: str = "all",
    states: list[str] | None = None,
    months: list[str] | None = None,
    download_full: bool = True,
    cache_dir: Path | None = None,
    **_: object,
) -> list[Path]:
    """Download NCCS BMF bulk file(s) into the cache, returning the local paths.

    Per-file cache-freshness reuse: a file already present and larger than the
    minimum size is skipped unless ``force=True``.
    """
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    async with NccsClient() as client:
        specs: list[tuple[str, Path, str]] = []

        if dataset in ("all", "unified"):
            discovered = await client.discover_state_files()
            specs.extend(
                _unified_specs(
                    cache_dir,
                    discovered,
                    states,
                    download_full=download_full and states is None,
                )
            )
        if dataset in ("all", "transformed"):
            specs.extend(_transformed_specs(cache_dir, months))
        if dataset in ("all", "raw"):
            specs.extend(_raw_specs(cache_dir, months))

        logger.info(f"NCCS: {len(specs)} files to process")

        for url, dest_path, description in specs:
            if not force and _is_fresh(dest_path):
                logger.info(f"Skipping (cached): {dest_path.name}")
                written.append(dest_path)
                continue
            if await client.fetch_to(url, dest_path):
                written.append(dest_path)

    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download NCCS BMF bulk data files")
    parser.add_argument(
        "--dataset", choices=["all", "unified", "transformed", "raw"], default="all",
        help="Which dataset to download (default: all)",
    )
    parser.add_argument(
        "--states", type=str,
        help="Comma-separated state codes for Unified BMF (e.g., CA,NY,TX)",
    )
    parser.add_argument(
        "--months", type=str,
        help="Comma-separated months for Transformed/Raw BMF (e.g., 2025_12,2026_01)",
    )
    parser.add_argument(
        "--no-full", action="store_true",
        help="Skip the full Unified BMF file (only download state files)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if a fresh cached copy exists",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    states = args.states.split(",") if args.states else None
    months = args.months.split(",") if args.months else None
    paths = await download(
        force=args.force,
        dataset=args.dataset,
        states=states,
        months=months,
        download_full=not args.no_full,
    )
    logger.info(f"NCCS download complete: {len(paths)} files in cache")


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

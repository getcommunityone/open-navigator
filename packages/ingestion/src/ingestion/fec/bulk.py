#!/usr/bin/env python3
"""FEC bulk-data file manifest pipeline: discover bulk files into bronze.

Ported from load_fec_bulk.py to the core_lib DataSourcePipeline contract.

DEVIATION NOTE
--------------
The legacy ``load_fec_bulk.py`` is NOT a tabular DB loader: it is a web
*downloader* that scrapes https://www.fec.gov/data/browse-data/?tab=bulk-data,
parses each ``/files/bulk-downloads/`` link into ``(url, type, category, year,
dest_path)`` and downloads the files to ``data/cache/fec_data/bulk-downloads``.
There is no source bronze table and no row-level data in the legacy script.

To port it faithfully onto ``DataSourcePipeline[RawRow]`` while preserving its
behavior, this pipeline records each *discovered* bulk file as one row in a
bronze manifest/catalog table (``bronze.bronze_fec_bulk_files``). The pure
discovery/parse logic (``parse_file_info`` / ``discover_files`` / ``filter_files``)
is preserved verbatim from the legacy ``FECBulkDownloader``. The actual file
download side effect (requests / tqdm / disk writes) lives in ``download_files``
and is opted into with ``--download``; it is intentionally outside the
extract -> validate -> load contract since it produces files, not rows.

Usage:
    python -m ingestion.fec.bulk
    python -m ingestion.fec.bulk --truncate
    python -m ingestion.fec.bulk --years 2020,2022,2024 --types indiv,cn,cm
    python -m ingestion.fec.bulk --base-dir /path/to/fec_data --download --resume

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces the legacy on-disk-only download layout for DB writes).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


BASE_URL = "https://www.fec.gov"
BULK_DATA_URL = f"{BASE_URL}/data/browse-data/?tab=bulk-data"

_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_FEC_DATA_DIR = _REPO_ROOT / "data" / "cache" / "fec_data"

TARGET_TABLE = "bronze.bronze_fec_bulk_files"

# FEC Page Categories (matching website organization)
FILE_CATEGORIES = {
    "cn": "candidate-master",
    "weball": "all-candidates",
    "webk": "house-senate-campaigns",
    "webl": "house-senate-campaigns",
    "cm": "committee-master",
    "pas2": "pac-summary",
    "indiv": "contributions-by-individuals",
    "ccl": "candidate-committee-linkages",
    "oth": "committee-to-committee",
    "oppexp": "operating-expenditures",
}

# CSV file patterns (by year)
CSV_FILE_PATTERNS = [
    "candidate_summary",
    "committee_summary",
    "independent_expenditure",
    "CommunicationCosts",
    "ElectioneeringComm",
    "Form1Filer",
    "Form2Filer",
    "leadership",
]

# Header files (one-time downloads)
HEADER_FILES = [
    "cm_header_file.csv",
    "cn_header_file.csv",
    "ccl_header_file.csv",
    "indiv_header_file.csv",
    "pas2_header_file.csv",
    "oth_header_file.csv",
    "oppexp_header_file.csv",
]

# Other special files
SPECIAL_FILES = [
    "lobbyist.csv",
    "lobbyist_bundle.csv",
    "FalseFictitiousFilings.csv",
    "Contributions_by_3Zip.csv",
    "Contributions_by_Size.csv",
]


# ---------------------------------------------------------------------------
# Pure discovery / parse helpers (behavior preserved verbatim from the legacy
# FECBulkDownloader.discover_files / _parse_file_info / download_all filters).
# ---------------------------------------------------------------------------


def default_fec_data_dir() -> Path:
    """Resolved base dir: ``$FEC_DATA_DIR`` or ``data/cache/fec_data``."""
    override = (os.environ.get("FEC_DATA_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_FEC_DATA_DIR.resolve()


def parse_file_info(href: str, filename: str, bulk_dir: Path) -> Optional[dict]:
    """Parse file information from an FEC bulk-downloads href.

    Returns a dict with url / path / filename / type / category / year, or
    None. Logic mirrors FECBulkDownloader._parse_file_info exactly.
    """
    parts = href.split("/")

    # Extract year from path
    year = None
    for part in parts:
        if part.isdigit() and len(part) == 4:
            year = part
            break

    # Determine file type and category
    file_type = "other"
    category = "other"

    if filename in HEADER_FILES:
        file_type = "header"
        category = "headers"
        dest_path = bulk_dir / "headers" / filename
    elif filename in SPECIAL_FILES:
        file_type = "special"
        category = "special-files"
        dest_path = bulk_dir / "special-files" / filename
    elif year:
        # Determine category based on file prefix
        for prefix, cat in FILE_CATEGORIES.items():
            if filename.startswith(prefix):
                file_type = prefix
                category = cat
                break

        # Check CSV patterns
        for csv_pattern in CSV_FILE_PATTERNS:
            if csv_pattern in filename:
                file_type = csv_pattern
                category = "summary-reports"
                break

        # Organize by category, then year
        dest_path = bulk_dir / category / year / filename
    else:
        dest_path = bulk_dir / "other" / filename

    url = f"{BASE_URL}{href}" if href.startswith("/") else href

    return {
        "url": url,
        "path": dest_path,
        "filename": filename,
        "type": file_type,
        "category": category,
        "year": year,
    }


def discover_files(html: str, bulk_dir: Path) -> list[dict]:
    """Discover all bulk-download files from FEC bulk-data page HTML.

    Mirrors FECBulkDownloader.discover_files (sans network I/O): given the
    page HTML, find every ``/files/bulk-downloads/`` anchor and parse it.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    files: list[dict] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/files/bulk-downloads/" not in href:
            continue
        filename = href.split("/")[-1]
        file_info = parse_file_info(href, filename, bulk_dir)
        if file_info:
            files.append(file_info)
    return files


def filter_files(
    files: list[dict],
    years: list[str] | None = None,
    file_types: list[str] | None = None,
) -> list[dict]:
    """Filter discovered files by year and type (mirrors download_all)."""
    if years:
        files = [f for f in files if f["year"] in years or f["year"] is None]
    if file_types:
        files = [
            f
            for f in files
            if f["type"] in file_types or f["type"] in ["header", "special"]
        ]
    return files


def fetch_bulk_index() -> str:
    """Fetch the FEC bulk-data page HTML (network I/O, isolated for testing)."""
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (FEC Bulk Downloader/1.0)"})
    response = session.get(BULK_DATA_URL, timeout=30)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class FecBulkRow(RawRow):
    """One discovered FEC bulk file, validated before upsert."""

    url: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    dest_path: str = Field(min_length=1)
    file_type: str | None = None
    category: str | None = None
    year: int | None = None


_ENSURE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_ENSURE_TABLE_SQL = text(
    f"""
    CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
        url text PRIMARY KEY,
        filename text NOT NULL,
        dest_path text NOT NULL,
        file_type text,
        category text,
        year integer,
        discovered_at timestamptz NOT NULL DEFAULT now()
    )
    """
)

_ENSURE_INDEXES_SQL = (
    text(f"CREATE INDEX IF NOT EXISTS idx_fbf_category ON {TARGET_TABLE}(category)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_fbf_year ON {TARGET_TABLE}(year)"),
    text(f"CREATE INDEX IF NOT EXISTS idx_fbf_type ON {TARGET_TABLE}(file_type)"),
)

_TRUNCATE_SQL = text(f"TRUNCATE TABLE {TARGET_TABLE}")

_UPSERT_SQL = text(
    f"""
    INSERT INTO {TARGET_TABLE}
        (url, filename, dest_path, file_type, category, year, discovered_at)
    VALUES
        (:url, :filename, :dest_path, :file_type, :category, :year, :discovered_at)
    ON CONFLICT (url) DO UPDATE SET
        filename      = EXCLUDED.filename,
        dest_path     = EXCLUDED.dest_path,
        file_type     = EXCLUDED.file_type,
        category      = EXCLUDED.category,
        year          = EXCLUDED.year,
        discovered_at = EXCLUDED.discovered_at
    """
)


class FecBulkPipeline(DataSourcePipeline[FecBulkRow]):
    source = "fec_bulk"
    batch_size = 1_000
    row_schema = FecBulkRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        limit: int | None = None,
        years: list[str] | None = None,
        file_types: list[str] | None = None,
    ):
        self._base_dir = path or default_fec_data_dir()
        self._limit = limit
        self._years = years
        self._file_types = file_types

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        bulk_dir = self._base_dir / "bulk-downloads"
        html = fetch_bulk_index()
        files = discover_files(html, bulk_dir)
        files = filter_files(files, self._years, self._file_types)
        emitted = 0
        for file_info in files:
            if self._limit is not None and emitted >= self._limit:
                return
            year = file_info["year"]
            yield {
                "source": self.source,
                "source_version": datetime.now(timezone.utc).strftime("%Y%m%d"),
                "natural_key": file_info["url"],
                "url": file_info["url"],
                "filename": file_info["filename"],
                "dest_path": str(file_info["path"]),
                "file_type": file_info["type"],
                "category": file_info["category"],
                "year": int(year) if year else None,
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[FecBulkRow],
        ctx: PipelineContext,
    ) -> None:
        discovered_at = datetime.now(timezone.utc)
        params = [
            {
                "url": r.url,
                "filename": r.filename,
                "dest_path": r.dest_path,
                "file_type": r.file_type,
                "category": r.category,
                "year": r.year,
                "discovered_at": discovered_at,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


# ---------------------------------------------------------------------------
# Optional download side effect (preserved from legacy FECBulkDownloader, kept
# out of the extract/load contract; invoked only with --download).
# ---------------------------------------------------------------------------


def _load_log(log_file: Path) -> dict:
    if log_file.exists():
        with open(log_file) as f:
            return json.load(f)
    return {
        "started": datetime.now().isoformat(),
        "last_updated": None,
        "completed_files": {},
        "failed_files": {},
    }


def _save_log(log_file: Path, download_log: dict) -> None:
    download_log["last_updated"] = datetime.now().isoformat()
    with open(log_file, "w") as f:
        json.dump(download_log, f, indent=2)


def download_files(
    files: list[dict],
    base_dir: Path,
    resume: bool = False,
) -> None:
    """Download discovered files to disk (legacy download_all side effect)."""
    import requests
    from loguru import logger
    from tqdm import tqdm

    base_dir.mkdir(parents=True, exist_ok=True)
    log_file = base_dir / "download_log.json"
    download_log = _load_log(log_file)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (FEC Bulk Downloader/1.0)"})

    def _is_downloaded(url: str, dest_path: Path) -> bool:
        if not resume or not dest_path.exists():
            return False
        if url in download_log["completed_files"]:
            file_info = download_log["completed_files"][url]
            if dest_path.stat().st_size == file_info.get("size", 0):
                return True
        return False

    successful = failed = skipped = 0
    for i, file_info in enumerate(files, 1):
        url = file_info["url"]
        dest_path = file_info["path"]
        logger.info(f"[{i}/{len(files)}] {file_info['filename']}")
        if _is_downloaded(url, dest_path):
            skipped += 1
            continue
        try:
            response = session.head(url, allow_redirects=True, timeout=30)
            total_size = int(response.headers.get("content-length", 0))
            response = session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                with tqdm(total=total_size, unit="B", unit_scale=True, leave=False) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            download_log["completed_files"][url] = {
                "path": str(dest_path),
                "size": dest_path.stat().st_size,
                "downloaded_at": datetime.now().isoformat(),
            }
            _save_log(log_file, download_log)
            successful += 1
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            download_log["failed_files"][url] = {
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
            }
            _save_log(log_file, download_log)
            failed += 1
        time.sleep(0.5)

    logger.info(
        f"Download summary: successful={successful} skipped={skipped} failed={failed}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_ENSURE_SCHEMA_SQL)
        await session.execute(_ENSURE_TABLE_SQL)
        for idx in _ENSURE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover FEC bulk-data files into bronze.bronze_fec_bulk_files"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=f"Base directory for downloads (default: {default_fec_data_dir()})",
    )
    parser.add_argument(
        "--years",
        type=str,
        help="Comma-separated list of years to keep (e.g., 2020,2022,2024)",
    )
    parser.add_argument(
        "--types",
        type=str,
        help="Comma-separated list of file types (e.g., indiv,cm,cn)",
    )
    parser.add_argument("--limit", type=int, help="Limit discovered files (for testing)")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help=f"TRUNCATE {TARGET_TABLE} before loading",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted download (only with --download)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Also download the discovered files to disk (legacy side effect)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    base_dir = args.base_dir or default_fec_data_dir()
    years = args.years.split(",") if args.years else None
    file_types = args.types.split(",") if args.types else None

    await _prepare_target(args.truncate)
    pipeline = FecBulkPipeline(
        path=base_dir,
        limit=args.limit,
        years=years,
        file_types=file_types,
    )
    await pipeline.run()

    if args.download:
        files = filter_files(
            discover_files(fetch_bulk_index(), base_dir / "bulk-downloads"),
            years,
            file_types,
        )
        download_files(files, base_dir, resume=args.resume)


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

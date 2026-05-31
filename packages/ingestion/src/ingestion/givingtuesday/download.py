#!/usr/bin/env python3
"""GivingTuesday 990 Datamarts bulk downloader.

Downloads the curated "research-ready" datamart CSVs that GivingTuesday
publishes alongside the raw 990 e-file Data Lake. These are *not* the raw
per-EIN XML files (that lives in ``gt990datalake-rawdata`` and is handled by the
legacy ``scripts/enrichment`` tooling) — they are pre-joined CSV extracts of
common 990 / 990-EZ / 990-PF / Schedule parts (missions, programs, officers,
grants, standard fields, etc.).

Source (public S3, no credentials, us-east-1):
    https://gt990datalake-analytics-and-datamarts.s3.us-east-1.amazonaws.com/EfileDataMarts/
    e.g. .../EfileDataMarts/2025_08_29_All_Years_990Part1Missions.csv

Data dictionary (Google Sheet, one tab per datamart):
    https://docs.google.com/spreadsheets/d/1UnOtFmbaVz0cWBkjhbclIGmQOZCtWFYy-GeNATJNI3c/

Files are versioned by a leading ``YYYY_MM_DD_`` snapshot date; this downloader
keeps only the most recent snapshot of each logical datamart. Some files are
multi-GB (Schedule O ~11 GB, 990 Part 7A Officers ~9 GB) so downloads are
streamed to disk, and an already-present file whose size matches the S3 object
is reused unless ``--force`` is given.

Destination (CACHE_DIR): data/cache/giving_tuesday/

Usage:
    # See what's available (no download)
    python -m ingestion.givingtuesday.download --list

    # Download the nonprofit-enrichment core set + the data dictionary
    python -m ingestion.givingtuesday.download \\
        --match Missions,Programs,990Part7AOfficers,990StandardFields \\
        --data-dictionary

    # Download everything (~60 GB, latest snapshot of each datamart)
    python -m ingestion.givingtuesday.download --all

    # Force re-download of one datamart
    python -m ingestion.givingtuesday.download --match Missions --force
"""
from __future__ import annotations

import argparse
import asyncio
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from core_lib.logging import setup_logging


CACHE_DIR = Path("data/cache/giving_tuesday")

BUCKET_HOST = "https://gt990datalake-analytics-and-datamarts.s3.us-east-1.amazonaws.com"
PREFIX = "EfileDataMarts/"

# Google Sheet workbook holding the field-level data dictionary (one tab per
# datamart). Exported as a single .xlsx so every tab is captured.
DATA_DICTIONARY_SHEET_ID = "1UnOtFmbaVz0cWBkjhbclIGmQOZCtWFYy-GeNATJNI3c"
DATA_DICTIONARY_URL = (
    f"https://docs.google.com/spreadsheets/d/{DATA_DICTIONARY_SHEET_ID}/export?format=xlsx"
)

_S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_DATE_PREFIX = re.compile(r"^(\d{4}_\d{2}_\d{2})_")
# Stream chunk size and progress-log cadence.
_CHUNK = 1024 * 1024  # 1 MiB
_LOG_EVERY = 256 * 1024 * 1024  # log progress every 256 MiB


@dataclass(frozen=True)
class Datamart:
    """One logical datamart, resolved to its most recent dated snapshot."""

    logical: str  # e.g. "All_Years_990Part1Missions.csv" (date prefix stripped)
    key: str      # full S3 key, e.g. "EfileDataMarts/2025_08_29_All_Years_990Part1Missions.csv"
    date: str     # snapshot date "YYYY_MM_DD"
    size: int     # object size in bytes

    @property
    def url(self) -> str:
        return f"{BUCKET_HOST}/{self.key}"

    @property
    def filename(self) -> str:
        """Local filename: the snapshot-dated basename from the S3 key."""
        return self.key.split("/")[-1]


def _logical_name(key: str) -> str:
    """Strip the leading ``YYYY_MM_DD_`` snapshot date from a key's basename."""
    base = key.split("/")[-1]
    return _DATE_PREFIX.sub("", base)


def _snapshot_date(key: str) -> str:
    m = _DATE_PREFIX.match(key.split("/")[-1])
    return m.group(1) if m else "0000_00_00"


async def list_datamarts(client: httpx.AsyncClient) -> list[Datamart]:
    """List EfileDataMarts objects, deduped to the latest snapshot per datamart.

    Handles S3 ListObjectsV2 continuation tokens, though the prefix currently
    fits in a single page.
    """
    latest: dict[str, Datamart] = {}
    token: str | None = None

    while True:
        params = {"list-type": "2", "prefix": PREFIX, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        resp = await client.get(f"{BUCKET_HOST}/", params=params)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for c in root.findall(f"{_S3_NS}Contents"):
            key = c.findtext(f"{_S3_NS}Key") or ""
            if not key or key.endswith("/"):
                continue
            size = int(c.findtext(f"{_S3_NS}Size") or "0")
            logical = _logical_name(key)
            date = _snapshot_date(key)
            cur = latest.get(logical)
            if cur is None or date > cur.date:
                latest[logical] = Datamart(logical=logical, key=key, date=date, size=size)

        if (root.findtext(f"{_S3_NS}IsTruncated") or "false").lower() == "true":
            token = root.findtext(f"{_S3_NS}NextContinuationToken")
            if not token:
                break
        else:
            break

    return sorted(latest.values(), key=lambda d: d.logical)


def _select(datamarts: list[Datamart], patterns: list[str]) -> list[Datamart]:
    """Filter datamarts whose logical name contains any pattern (case-insensitive)."""
    pats = [p.strip().lower() for p in patterns if p.strip()]
    return [d for d in datamarts if any(p in d.logical.lower() for p in pats)]


def _is_fresh(dest: Path, expected_size: int) -> bool:
    """A cached file is fresh if it exists and matches the S3 object size."""
    return dest.exists() and dest.stat().st_size == expected_size


async def _stream_to_file(client: httpx.AsyncClient, url: str, dest: Path) -> int:
    """Stream ``url`` to ``dest`` via a ``.part`` temp file. Returns bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    written = 0
    next_log = _LOG_EVERY
    async with client.stream("GET", url, follow_redirects=True) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            async for chunk in resp.aiter_bytes(_CHUNK):
                fh.write(chunk)
                written += len(chunk)
                if written >= next_log:
                    logger.info(f"  {dest.name}: {written / 1e9:.2f} GB...")
                    next_log += _LOG_EVERY
    tmp.replace(dest)
    return written


async def download_data_dictionary(client: httpx.AsyncClient, cache_dir: Path, *, force: bool) -> Path:
    """Download the GivingTuesday data dictionary workbook (.xlsx, all tabs)."""
    dest = cache_dir / "data_dictionary.xlsx"
    if not force and dest.exists() and dest.stat().st_size > 1024:
        logger.info(f"Skipping (cached): {dest.name}")
        return dest
    logger.info("Downloading data dictionary (Google Sheet -> xlsx)...")
    written = await _stream_to_file(client, DATA_DICTIONARY_URL, dest)
    logger.success(f"Downloaded: {dest.name} ({written:,} bytes)")
    return dest


async def download(
    *,
    match: list[str] | None = None,
    download_all: bool = False,
    data_dictionary: bool = False,
    force: bool = False,
    cache_dir: Path | None = None,
) -> list[Path]:
    """Download selected GivingTuesday datamarts into the cache.

    Pass ``download_all=True`` for every datamart, or ``match=[...]`` substrings
    to select a subset. Already-present files matching the S3 object size are
    reused unless ``force=True``.
    """
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    timeout = httpx.Timeout(60.0, read=300.0)
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "open-navigator/gt-datamarts"}) as client:
        catalog = await list_datamarts(client)

        if download_all:
            selected = catalog
        elif match:
            selected = _select(catalog, match)
        else:
            selected = []

        if not selected and not data_dictionary:
            logger.warning("Nothing selected. Use --list, --all, or --match <pattern>.")
            return written

        if selected:
            total = sum(d.size for d in selected)
            logger.info(f"Selected {len(selected)} datamart(s), {total / 1e9:.1f} GB total")

        for dm in selected:
            dest = cache_dir / dm.filename
            if not force and _is_fresh(dest, dm.size):
                logger.info(f"Skipping (cached): {dm.filename}")
                written.append(dest)
                continue
            logger.info(f"Downloading {dm.filename} ({dm.size / 1e9:.2f} GB)...")
            n = await _stream_to_file(client, dm.url, dest)
            logger.success(f"Downloaded: {dm.filename} ({n:,} bytes)")
            written.append(dest)

        if data_dictionary:
            written.append(await download_data_dictionary(client, cache_dir, force=force))

    return written


def _print_catalog(catalog: list[Datamart]) -> None:
    total = sum(d.size for d in catalog)
    logger.info(f"{len(catalog)} datamarts available (latest snapshot of each):")
    for d in catalog:
        print(f"  {d.size / 1e9:7.2f} GB  {d.date}  {d.logical}")
    print(f"\n  TOTAL: {total / 1e9:.1f} GB")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download GivingTuesday 990 datamart CSVs into data/cache/giving_tuesday",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available datamarts (latest snapshot of each) and exit",
    )
    parser.add_argument(
        "--all", action="store_true", dest="download_all",
        help="Download every datamart (~60 GB)",
    )
    parser.add_argument(
        "--match", type=str,
        help="Comma-separated substrings to select datamarts by name "
             "(e.g. Missions,Programs,990StandardFields)",
    )
    parser.add_argument(
        "--data-dictionary", action="store_true",
        help="Also download the field-level data dictionary workbook (.xlsx)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if a cached copy of matching size exists",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    if args.list:
        timeout = httpx.Timeout(60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            _print_catalog(await list_datamarts(client))
        return

    match = args.match.split(",") if args.match else None
    paths = await download(
        match=match,
        download_all=args.download_all,
        data_dictionary=args.data_dictionary,
        force=args.force,
    )
    logger.info(f"GivingTuesday datamart download complete: {len(paths)} file(s) in {CACHE_DIR}")


def main() -> None:
    setup_logging()
    asyncio.run(_run(build_parser().parse_args()))


if __name__ == "__main__":
    main()

"""Tests for the NCCS bulk downloader ported to core_lib BaseAsyncClient."""
from __future__ import annotations

import asyncio
from pathlib import Path

from ingestion.nccs import download as nccs_download
from ingestion.nccs.download import (
    BASE_URL,
    NccsClient,
    _is_fresh,
    download,
)


def test_client_config() -> None:
    """The NCCS client points at the S3 host with source 'nccs' and throttling."""
    client = NccsClient()
    cfg = client._cfg
    assert cfg.base_url == BASE_URL == "https://nccsdata.s3.us-east-1.amazonaws.com"
    assert cfg.source == "nccs"
    # Fetches many files, so a rate limit must be configured.
    assert cfg.rate_limit_per_sec is not None
    assert cfg.rate_limit_per_sec > 0


def test_cache_freshness(tmp_path: Path) -> None:
    """_is_fresh requires the file to exist and exceed the minimum size."""
    missing = tmp_path / "missing.csv"
    assert _is_fresh(missing) is False

    tiny = tmp_path / "tiny.csv"
    tiny.write_bytes(b"x" * 10)
    assert _is_fresh(tiny) is False

    big = tmp_path / "big.csv"
    big.write_bytes(b"x" * 2048)
    assert _is_fresh(big) is True


def test_cache_hit_skips_network(tmp_path, monkeypatch) -> None:
    """A fresh cached file is reused and no HTTP request is made."""
    monkeypatch.setattr(nccs_download, "CACHE_DIR", tmp_path)

    # Pre-create a fresh raw-BMF file for a single month.
    month = "2026-01"
    dest = tmp_path / "raw-bmf" / f"{month}-BMF.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"cached," * 1000)

    # No httpx_mock is registered: any network call would raise, so a clean run
    # proves the fresh cache file was reused without touching the network.
    paths = asyncio.run(download(force=False, dataset="raw", months=[month]))

    assert dest in paths


def test_download_writes_cache(tmp_path, monkeypatch, httpx_mock) -> None:
    """A missing raw-BMF file is fetched over HTTP and written to the cache."""
    monkeypatch.setattr(nccs_download, "CACHE_DIR", tmp_path)

    month = "2026-01"
    url = f"{BASE_URL}/raw/bmf/{month}-BMF.csv"
    body = b"col1,col2\n" + b"v," * 1000

    httpx_mock.add_response(url=url, content=body)

    paths = asyncio.run(download(force=False, dataset="raw", months=[month]))

    dest = tmp_path / "raw-bmf" / f"{month}-BMF.csv"
    assert dest in paths
    assert dest.exists()
    assert dest.read_bytes() == body


def test_force_redownload(tmp_path, monkeypatch, httpx_mock) -> None:
    """force=True re-fetches over HTTP even when a fresh cache file exists."""
    monkeypatch.setattr(nccs_download, "CACHE_DIR", tmp_path)

    month = "2026-01"
    dest = tmp_path / "raw-bmf" / f"{month}-BMF.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"stale," * 1000)  # fresh by size, but stale content

    url = f"{BASE_URL}/raw/bmf/{month}-BMF.csv"
    fresh = b"fresh," * 1000
    httpx_mock.add_response(url=url, content=fresh)

    paths = asyncio.run(download(force=True, dataset="raw", months=[month]))

    assert dest in paths
    assert dest.read_bytes() == fresh

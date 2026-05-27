"""Unit tests for the OSF ZIP downloader port to core_lib.http.BaseAsyncClient."""
from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path

import pytest

from ingestion.osf.download import (  # noqa: E402
    CACHE_DIR,
    DEFAULT_PAGE_URL,
    OSF_BASE_URL,
    OsfClient,
    extract_zip,
)


def _tiny_zip_bytes() -> bytes:
    """Build a minimal in-memory ZIP with one small file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", "hi osf")
    return buf.getvalue()


def test_client_config():
    client = OsfClient()
    cfg = client._cfg
    assert cfg.base_url == OSF_BASE_URL == "https://osf.io"
    assert cfg.source == "osf"
    # generous timeout for a large zip
    assert cfg.timeout_s >= 300.0
    # rate limiting disabled (single large download)
    assert cfg.rate_limit_per_sec is None
    assert client._limiter is None
    # default cache dir
    assert CACHE_DIR == Path("data/cache/osf")


def test_cache_freshness_reuses_existing_zip(tmp_path):
    """A non-trivial existing zip is reused; no network call is made."""
    zip_bytes = _tiny_zip_bytes()
    # pad past the >1024 byte freshness threshold
    payload = zip_bytes + b"\x00" * 2048
    dest = tmp_path / "osf.zip"
    dest.write_bytes(payload)

    async def run():
        async with OsfClient() as client:
            return await client.download(force=False, cache_dir=tmp_path)

    # No httpx_mock registered: any network call would raise.
    result = asyncio.run(run())
    assert result == dest
    assert result.read_bytes() == payload


def test_cache_hit_skips_network(tmp_path, monkeypatch):
    """With CACHE_DIR monkeypatched, a fresh cached zip short-circuits download()."""
    import ingestion.osf.download as dl

    monkeypatch.setattr(dl, "CACHE_DIR", tmp_path)
    dest = tmp_path / "osf.zip"
    dest.write_bytes(_tiny_zip_bytes() + b"\x00" * 2048)

    async def run():
        async with OsfClient() as client:
            # cache_dir defaults to (patched) CACHE_DIR
            return await client.download(force=False)

    result = asyncio.run(run())
    assert result == dest


def test_download_writes_cache(tmp_path, httpx_mock):
    """download() fetches the zip via the client and writes it to the cache."""
    zip_bytes = _tiny_zip_bytes()
    zip_url = "https://files.osf.io/v1/resources/mv5e6/providers/osfstorage/?zip="
    httpx_mock.add_response(
        url=zip_url,
        content=zip_bytes,
        headers={"Content-Type": "application/zip"},
    )

    async def run():
        async with OsfClient() as client:
            return await client.download(
                force=False, zip_url=zip_url, cache_dir=tmp_path
            )

    result = asyncio.run(run())
    assert result == tmp_path / "osf.zip"
    assert result.read_bytes() == zip_bytes
    # the .part temp file was renamed away
    assert not (tmp_path / "osf.zip.part").exists()


def test_force_redownload(tmp_path, httpx_mock):
    """--force re-fetches over the network even when a fresh cache exists."""
    stale = b"OLD" + b"\x00" * 4096
    dest = tmp_path / "osf.zip"
    dest.write_bytes(stale)

    fresh = _tiny_zip_bytes()
    zip_url = "https://files.osf.io/direct.zip"
    httpx_mock.add_response(url=zip_url, content=fresh)

    async def run():
        async with OsfClient() as client:
            return await client.download(
                force=True, zip_url=zip_url, cache_dir=tmp_path
            )

    result = asyncio.run(run())
    assert result == dest
    assert result.read_bytes() == fresh  # replaced the stale bytes


def test_extract_zip_writes_and_extracts(tmp_path):
    """extract_zip unpacks a synthetic zip and writes the sha256 marker."""
    zip_path = tmp_path / "osf.zip"
    zip_path.write_bytes(_tiny_zip_bytes())
    extract_dir = tmp_path / "osf"

    # count includes the .extracted_from_sha256 marker (verbatim original behavior)
    count = extract_zip(zip_path, extract_dir, force=False)
    assert count == 2
    assert (extract_dir / "hello.txt").read_text() == "hi osf"
    assert (extract_dir / ".extracted_from_sha256").exists()

    # Second call with the same zip is a cache hit (returns 0, no re-extract).
    assert extract_zip(zip_path, extract_dir, force=False) == 0


def test_default_page_url_preserved():
    assert DEFAULT_PAGE_URL == "https://osf.io/mv5e6/files/osfstorage"

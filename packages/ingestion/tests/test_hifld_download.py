"""Unit tests for the HIFLD downloader refactor (core_lib BaseAsyncClient)."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from ingestion.hifld import download as dl
from ingestion.hifld.download import (
    ARCGIS_BASE_URL,
    DATASETS,
    HifldClient,
    _is_cache_fresh,
    download,
)


# -- client config ---------------------------------------------------------

def test_client_config():
    client = HifldClient()
    cfg = client._cfg
    assert cfg.base_url == ARCGIS_BASE_URL
    assert cfg.source == "hifld"
    assert cfg.timeout_s == 60.0
    assert cfg.rate_limit_per_sec == 2.0


# -- cache-freshness helper ------------------------------------------------

def test_is_cache_fresh(tmp_path: Path):
    missing = tmp_path / "nope.csv"
    assert _is_cache_fresh(missing) is False

    fresh = tmp_path / "fresh.csv"
    fresh.write_text("data")
    assert _is_cache_fresh(fresh) is True

    stale = tmp_path / "stale.csv"
    stale.write_text("data")
    old = time.time() - 10 * 86400  # 10 days old > 7-day window
    import os

    os.utime(stale, (old, old))
    assert _is_cache_fresh(stale) is False


# -- cache hit skips network -----------------------------------------------

def test_cache_hit_skips_network(httpx_mock, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(dl, "CACHE_DIR", tmp_path)
    item_id = DATASETS["hospitals"]
    cached = tmp_path / f"{item_id}.csv"
    cached.write_text("OBJECTID\n1\n")  # pre-existing fresh cache

    result = asyncio.run(download(item_id=item_id, force=False))

    assert result == cached
    assert httpx_mock.get_requests() == []  # no network calls


# -- download writes cache -------------------------------------------------

def test_download_writes_cache(httpx_mock, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(dl, "CACHE_DIR", tmp_path)
    item_id = "abc123"
    service_url = "https://services.arcgis.com/test/arcgis/rest/services/Foo/FeatureServer"

    # 1) item metadata -> service URL
    httpx_mock.add_response(
        url=f"{ARCGIS_BASE_URL}{dl.ARCGIS_ITEMS_PATH}/{item_id}?f=json",
        json={"url": service_url, "title": "Foo"},
    )
    # 2) layer query -> one page of features, no transfer-limit exceeded
    httpx_mock.add_response(
        method="GET",
        json={
            "features": [
                {"attributes": {"OBJECTID": 1, "NAME": "A"}},
                {"attributes": {"OBJECTID": 2, "NAME": "B"}},
            ],
            "exceededTransferLimit": False,
        },
    )

    result = asyncio.run(download(item_id=item_id, force=False))

    out = tmp_path / f"{item_id}.csv"
    assert result == out
    assert out.exists()
    text = out.read_text()
    assert "OBJECTID" in text and "NAME" in text
    assert "A" in text and "B" in text


# -- force re-download ignores fresh cache ---------------------------------

def test_force_redownload(httpx_mock, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(dl, "CACHE_DIR", tmp_path)
    item_id = "force123"
    out = tmp_path / f"{item_id}.csv"
    out.write_text("OLD\nx\n")  # fresh but stale-content cache

    service_url = "https://services.arcgis.com/test/arcgis/rest/services/Bar/FeatureServer"
    httpx_mock.add_response(
        url=f"{ARCGIS_BASE_URL}{dl.ARCGIS_ITEMS_PATH}/{item_id}?f=json",
        json={"url": service_url, "title": "Bar"},
    )
    httpx_mock.add_response(
        method="GET",
        json={
            "features": [{"attributes": {"OBJECTID": 9, "NAME": "NEW"}}],
            "exceededTransferLimit": False,
        },
    )

    result = asyncio.run(download(item_id=item_id, force=True))

    assert result == out
    assert len(httpx_mock.get_requests()) == 2  # network was hit despite cache
    assert "NEW" in out.read_text()

"""Unit tests for the OpenStates bulk downloader (BaseAsyncClient port)."""
from __future__ import annotations

import asyncio
import os
import time

import ingestion.openstates.download as mod
from ingestion.openstates.download import OpenstatesBulkClient, download


def test_client_config():
    c = OpenstatesBulkClient()
    assert c._cfg.source == "openstates_bulk"
    assert c._cfg.base_url == "https://data.openstates.org"
    assert c._cfg.rate_limit_per_sec == 2.0


def test_is_fresh(tmp_path):
    f = tmp_path / "ca-2024.csv"
    f.write_text("a")
    assert mod._is_fresh(f) is True
    # backdate beyond the 24h window
    old = time.time() - (mod._MAX_CACHE_AGE_S + 10)
    os.utime(f, (old, old))
    assert mod._is_fresh(f) is False
    assert mod._is_fresh(tmp_path / "missing.csv") is False


def test_cache_hit_skips_network(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    existing = tmp_path / "csv" / "ca-2024.csv"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"cached,data\n")
    # No httpx_mock response registered: a network call would error.
    out = asyncio.run(download(force=False, states=["CA"], years=[2024], fmt="csv"))
    assert out == [existing]
    assert existing.read_bytes() == b"cached,data\n"
    assert len(httpx_mock.get_requests()) == 0


def test_download_writes_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    httpx_mock.add_response(
        url="https://data.openstates.org/session/csv/ca/ca-2024.csv",
        content=b"bill_id,title\nca-1,Test Bill\n",
    )
    out = asyncio.run(download(force=True, states=["CA"], years=[2024], fmt="csv"))
    assert len(out) == 1
    assert out[0].exists()
    assert out[0].read_bytes().startswith(b"bill_id")
    assert len(httpx_mock.get_requests()) == 1


def test_force_redownloads_over_fresh_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    existing = tmp_path / "csv" / "ca-2024.csv"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"stale\n")
    httpx_mock.add_response(
        url="https://data.openstates.org/session/csv/ca/ca-2024.csv",
        content=b"fresh\n",
    )
    out = asyncio.run(download(force=True, states=["CA"], years=[2024], fmt="csv"))
    assert out[0].read_bytes() == b"fresh\n"
    assert len(httpx_mock.get_requests()) == 1

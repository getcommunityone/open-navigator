"""Unit tests for the GSA downloader (BaseAsyncClient reference port)."""
from __future__ import annotations

import asyncio
import time

import pytest

import ingestion.gsa.download as mod
from ingestion.gsa.download import GsaDomainsClient, download


def test_client_config():
    c = GsaDomainsClient()
    assert c._cfg.source == "gsa_domains"
    assert c._cfg.base_url == "https://raw.githubusercontent.com"


def test_is_fresh(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a")
    assert mod._is_fresh(f) is True
    # backdate beyond the 24h window
    old = time.time() - (mod._MAX_CACHE_AGE_S + 10)
    import os
    os.utime(f, (old, old))
    assert mod._is_fresh(f) is False
    assert mod._is_fresh(tmp_path / "missing.csv") is False


def test_cache_hit_skips_network(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    existing = mod._cache_path()
    existing.write_bytes(b"cached,data\n")
    # No httpx_mock response registered: a network call would error.
    out = asyncio.run(download(force=False))
    assert out == existing
    assert out.read_bytes() == b"cached,data\n"
    assert len(httpx_mock.get_requests()) == 0


def test_download_writes_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    httpx_mock.add_response(
        url="https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv",
        content=b"Domain name,Domain type\nexample.gov,Federal\n",
    )
    out = asyncio.run(download(force=True))
    assert out.exists()
    assert out.read_bytes().startswith(b"Domain name")
    assert len(httpx_mock.get_requests()) == 1


def test_force_redownloads_over_fresh_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    mod._cache_path().write_bytes(b"stale\n")
    httpx_mock.add_response(
        url="https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv",
        content=b"fresh\n",
    )
    out = asyncio.run(download(force=True))
    assert out.read_bytes() == b"fresh\n"
    assert len(httpx_mock.get_requests()) == 1

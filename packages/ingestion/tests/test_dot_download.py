"""Unit tests for the DOT public-pages downloader port to BaseAsyncClient."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from ingestion.dot import download as dl
from ingestion.dot.download import (  # noqa: E402
    _is_fresh,
    _primary_path,
    _select_states,
    download,
    load_registry,
    parse_dot_markdown_table,
)


def test_registry_parses_and_builds_client_config():
    # The shipped dot.txt parses into a USPS-indexed registry of absolute URLs.
    registry = load_registry()
    assert "AL" in registry
    assert registry["AL"]["public_involvement_url"].startswith("https://")
    # Selecting AL/TX yields exactly those, sorted-or-explicit.
    selected = _select_states(registry, ["al", "tx"])
    assert selected == ["AL", "TX"]
    # Unknown codes are rejected.
    with pytest.raises(ValueError):
        _select_states(registry, ["ZZ"])


def test_cache_freshness_helper(tmp_path):
    f = tmp_path / "public_involvement.html"
    assert _is_fresh(f) is False  # missing
    f.write_bytes(b"")
    assert _is_fresh(f) is False  # empty
    f.write_bytes(b"<html>x</html>")
    assert _is_fresh(f) is True  # fresh, non-empty
    # Backdate beyond the freshness window.
    old = time.time() - (dl.CACHE_MAX_AGE_S + 10)
    import os
    os.utime(f, (old, old))
    assert _is_fresh(f) is False


def test_cache_hit_skips_network(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(dl, "CACHE_DIR", tmp_path)
    registry = load_registry()
    url = registry["AL"]["public_involvement_url"]
    # Pre-create a fresh cached snapshot at the expected path.
    primary = _primary_path("AL", url)
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_bytes(b"<html>cached</html>")

    paths = asyncio.run(download(force=False, states=["AL"]))

    assert paths == [primary]
    # No HTTP request should have been issued (httpx_mock raises on unmatched).
    assert httpx_mock.get_requests() == []


def test_download_writes_cache_for_states(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(dl, "CACHE_DIR", tmp_path)
    registry = load_registry()
    al_url = registry["AL"]["public_involvement_url"]
    tx_url = registry["TX"]["public_involvement_url"]
    httpx_mock.add_response(url=al_url, html="<html>AL page</html>")
    httpx_mock.add_response(url=tx_url, html="<html>TX page</html>")

    paths = asyncio.run(download(force=False, states=["AL", "TX"]))

    assert len(paths) == 2
    for usps in ("AL", "TX"):
        primary = _primary_path(usps, registry[usps]["public_involvement_url"])
        assert primary.is_file()
        assert primary.read_bytes()
        # Each state also gets a source.json metadata sidecar.
        assert (primary.parent / "source.json").is_file()
    assert len(httpx_mock.get_requests()) == 2


def test_force_redownloads_over_fresh_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(dl, "CACHE_DIR", tmp_path)
    registry = load_registry()
    url = registry["AL"]["public_involvement_url"]
    primary = _primary_path("AL", url)
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_bytes(b"<html>stale-but-fresh</html>")

    httpx_mock.add_response(url=url, html="<html>fresh fetch</html>")
    paths = asyncio.run(download(force=True, states=["AL"]))

    assert paths == [primary]
    # force=True must hit the network despite a fresh cache file.
    assert len(httpx_mock.get_requests()) == 1
    assert b"fresh fetch" in primary.read_bytes()

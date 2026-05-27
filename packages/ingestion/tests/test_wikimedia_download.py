"""Unit tests for the Wikimedia state-silhouette downloader (BaseAsyncClient port)."""
from __future__ import annotations

import asyncio
import os
import re
import time

import ingestion.wikimedia.download as mod
from ingestion.wikimedia.download import WikimediaSilhouettesClient, download


def test_client_config():
    c = WikimediaSilhouettesClient()
    assert c._cfg.source == "wikimedia"
    assert c._cfg.base_url == "https://commons.wikimedia.org"
    # Many per-asset fetches → a throttle is configured.
    assert c._cfg.rate_limit_per_sec is not None


def test_is_fresh(tmp_path):
    f = tmp_path / "x.svg"
    f.write_text("<svg/>")
    assert mod._is_fresh(f) is True
    old = time.time() - (mod._MAX_CACHE_AGE_S + 10)
    os.utime(f, (old, old))
    assert mod._is_fresh(f) is False
    assert mod._is_fresh(tmp_path / "missing.svg") is False


def test_cache_hit_skips_network(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    # Pre-create a fresh national silhouette → us_only download should reuse it
    # without any network request.
    (tmp_path / mod.US_SILHOUETTE_LOCAL).write_bytes(b"<svg>cached</svg>")
    out = asyncio.run(download(force=False, us_only=True))
    assert out == [tmp_path / mod.US_SILHOUETTE_LOCAL]
    assert (tmp_path / mod.US_SILHOUETTE_LOCAL).read_bytes() == b"<svg>cached</svg>"
    assert len(httpx_mock.get_requests()) == 0


def test_download_writes_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    upload_url = "https://upload.wikimedia.org/wikipedia/commons/usa.svg"
    # imageinfo API JSON response (resolves the national silhouette title).
    httpx_mock.add_response(
        url=re.compile(r"https://commons\.wikimedia\.org/w/api\.php.*"),
        json={
            "query": {
                "pages": {
                    "1": {
                        "title": mod.US_SILHOUETTE_COMMONS,
                        "imageinfo": [
                            {"url": upload_url, "mime": "image/svg+xml", "timestamp": "2024-01-01T00:00:00Z"}
                        ],
                    }
                }
            }
        },
    )
    # Binary fetch from upload.wikimedia.org (absolute URL passed to client.get()).
    httpx_mock.add_response(url=upload_url, content=b"<svg>downloaded</svg>")

    out = asyncio.run(download(force=True, us_only=True))
    dest = tmp_path / mod.US_SILHOUETTE_LOCAL
    assert out == [dest]
    assert dest.read_bytes() == b"<svg>downloaded</svg>"
    # One API call + one binary fetch.
    assert len(httpx_mock.get_requests()) == 2


def test_force_redownloads_over_fresh_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    dest = tmp_path / mod.US_SILHOUETTE_LOCAL
    dest.write_bytes(b"<svg>stale</svg>")
    upload_url = "https://upload.wikimedia.org/wikipedia/commons/usa.svg"
    httpx_mock.add_response(
        url=re.compile(r"https://commons\.wikimedia\.org/w/api\.php.*"),
        json={
            "query": {
                "pages": {
                    "1": {
                        "title": mod.US_SILHOUETTE_COMMONS,
                        "imageinfo": [
                            {"url": upload_url, "mime": "image/svg+xml", "timestamp": "2024-01-01T00:00:00Z"}
                        ],
                    }
                }
            }
        },
    )
    httpx_mock.add_response(url=upload_url, content=b"<svg>fresh</svg>")

    out = asyncio.run(download(force=True, us_only=True))
    assert out == [dest]
    assert dest.read_bytes() == b"<svg>fresh</svg>"
    assert len(httpx_mock.get_requests()) == 2

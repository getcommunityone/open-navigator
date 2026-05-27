"""Unit tests for the Wikimedia Commons assets downloader (BaseAsyncClient port)."""
from __future__ import annotations

import asyncio
import os
import re
import time

import ingestion.wikicommons.download as mod
from ingestion.wikicommons.download import WikiCommonsAssetsClient, download


_API_RE = re.compile(r"https://commons\.wikimedia\.org/w/api\.php.*")


def test_client_config():
    c = WikiCommonsAssetsClient()
    assert c._cfg.source == "wikicommons"
    assert c._cfg.base_url == "https://commons.wikimedia.org"
    # Recursive plate walk fetches many assets → a throttle is configured.
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
    # Pre-create a fresh AK hero flag. The flags path resolves the category
    # picks BEFORE the cache check, so the categorymembers API is still queried,
    # but the per-file freshness reuse must skip the imageinfo + binary fetches.
    (tmp_path / "AK_colors_hero.svg").write_bytes(b"<svg>cached</svg>")
    # categorymembers for Category:SVG flags of Alaska → one canonical Flag of … .svg
    httpx_mock.add_response(
        url=_API_RE,
        json={
            "query": {
                "categorymembers": [{"title": "File:Flag of Alaska.svg"}]
            }
        },
    )
    out = asyncio.run(download(force=False, only={"AK"}, skip_plates=True))
    hero = tmp_path / "AK_colors_hero.svg"
    assert hero in out
    assert hero.read_bytes() == b"<svg>cached</svg>"
    # Only the categorymembers listing hit the network; no imageinfo/binary fetch.
    assert len(httpx_mock.get_requests()) == 1


def test_download_writes_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    upload_url = "https://upload.wikimedia.org/wikipedia/commons/flag_of_alaska.svg"
    # 1) categorymembers (list) → 2) imageinfo (prop) → 3) binary fetch.
    httpx_mock.add_response(
        url=_API_RE,
        json={"query": {"categorymembers": [{"title": "File:Flag of Alaska.svg"}]}},
    )
    httpx_mock.add_response(
        url=_API_RE,
        json={
            "query": {
                "pages": {
                    "1": {
                        "title": "File:Flag of Alaska.svg",
                        "imageinfo": [
                            {"url": upload_url, "mime": "image/svg+xml", "timestamp": "2024-01-01T00:00:00Z"}
                        ],
                    }
                }
            }
        },
    )
    httpx_mock.add_response(url=upload_url, content=b"<svg>downloaded</svg>")

    out = asyncio.run(download(force=True, only={"AK"}, skip_plates=True))
    hero = tmp_path / "AK_colors_hero.svg"
    assert hero in out
    assert hero.read_bytes() == b"<svg>downloaded</svg>"
    # Manifest is always written.
    assert (tmp_path / "_manifest.json").exists()
    # categorymembers + imageinfo + binary fetch.
    assert len(httpx_mock.get_requests()) == 3


def test_force_redownloads_over_fresh_cache(tmp_path, monkeypatch, httpx_mock):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    hero = tmp_path / "AK_colors_hero.svg"
    hero.write_bytes(b"<svg>stale</svg>")
    upload_url = "https://upload.wikimedia.org/wikipedia/commons/flag_of_alaska.svg"
    httpx_mock.add_response(
        url=_API_RE,
        json={"query": {"categorymembers": [{"title": "File:Flag of Alaska.svg"}]}},
    )
    httpx_mock.add_response(
        url=_API_RE,
        json={
            "query": {
                "pages": {
                    "1": {
                        "title": "File:Flag of Alaska.svg",
                        "imageinfo": [
                            {"url": upload_url, "mime": "image/svg+xml", "timestamp": "2024-01-01T00:00:00Z"}
                        ],
                    }
                }
            }
        },
    )
    httpx_mock.add_response(url=upload_url, content=b"<svg>fresh</svg>")

    out = asyncio.run(download(force=True, only={"AK"}, skip_plates=True))
    assert hero in out
    assert hero.read_bytes() == b"<svg>fresh</svg>"
    assert len(httpx_mock.get_requests()) == 3

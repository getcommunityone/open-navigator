"""Retry-failed-shallow GEOID collection (#401): legacy and jurisdiction_id folders."""
from __future__ import annotations

import json
from pathlib import Path

from scrapers.discovery.retry_failed_shallow import (
    collect_retry_geoids_from_scraped_manifests,
    discover_scraped_jurisdiction_types,
)


def _write_manifest(path: Path, *, jurisdiction_id: str, pages: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "jurisdiction_id": jurisdiction_id,
                "pages_fetched": [f"https://example.test/p{i}" for i in range(pages)],
            }
        ),
        encoding="utf-8",
    )


def test_collects_legacy_and_jurisdiction_id_folders(tmp_path: Path) -> None:
    root = tmp_path / "scraped"
    # Legacy type_geoid folder.
    _write_manifest(
        root / "AL" / "county" / "county_01001" / "_manifest.json",
        jurisdiction_id="county_01001",
        pages=0,
    )
    # Current slug_geoid folder (issue example).
    _write_manifest(
        root / "AL" / "municipality" / "tuscaloosa_0177256" / "_manifest.json",
        jurisdiction_id="tuscaloosa_0177256",
        pages=0,
    )

    county = collect_retry_geoids_from_scraped_manifests(
        state="AL",
        jtype="county",
        scraped_root=root,
        shallow_max_pages=5,
        retry_modes={"failed", "shallow"},
    )
    muni = collect_retry_geoids_from_scraped_manifests(
        state="AL",
        jtype="municipality",
        scraped_root=root,
        shallow_max_pages=5,
        retry_modes={"failed", "shallow"},
    )
    assert county == ["01001"]
    assert muni == ["0177256"]


def test_shallow_threshold_and_folder_fallback_without_jid(tmp_path: Path) -> None:
    root = tmp_path / "scraped"
    folder = root / "IN" / "county" / "adams_18001"
    folder.mkdir(parents=True)
    # Manifest missing jurisdiction_id — folder name still yields the GEOID.
    # Three pages: shallow when cap > 3, not when cap <= 3 (cap = max(2, N)).
    (folder / "_manifest.json").write_text(
        json.dumps(
            {"pages_fetched": [f"https://example.test/p{i}" for i in range(3)]}
        ),
        encoding="utf-8",
    )
    shallow = collect_retry_geoids_from_scraped_manifests(
        state="IN",
        jtype="county",
        scraped_root=root,
        shallow_max_pages=5,
        retry_modes={"shallow"},
    )
    assert shallow == ["18001"]
    deep_enough = collect_retry_geoids_from_scraped_manifests(
        state="IN",
        jtype="county",
        scraped_root=root,
        shallow_max_pages=3,
        retry_modes={"shallow"},
    )
    assert deep_enough == []


def test_discover_types_lists_concrete_folders(tmp_path: Path) -> None:
    root = tmp_path / "scraped"
    (root / "MT" / "county").mkdir(parents=True)
    (root / "MT" / "municipality").mkdir(parents=True)
    (root / "MT" / "notes.txt").write_text("x", encoding="utf-8")
    assert discover_scraped_jurisdiction_types(root, "MT") == ["county", "municipality"]

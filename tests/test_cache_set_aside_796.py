"""#796: the cache layout repair sets older duplicates aside instead of deleting them."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

tcp = pytest.importorskip("llm.gemini.transcript_cache_paths")


def _write(path: Path, text: str, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.utime(path, (mtime, mtime))
    return path


def test_older_source_is_set_aside_not_deleted(tmp_path):
    dest = _write(tmp_path / "02_analysis" / "a.json", "newer", 2_000)
    src = _write(tmp_path / "02_analysis" / "old" / "a.json", "older", 1_000)
    action = tcp._safe_move(src, dest, dry_run=False)
    assert action == "set_aside_older_duplicate"
    assert dest.read_text() == "newer"
    assert not src.exists()
    kept = list((src.parent / "_superseded").iterdir())
    assert [p.read_text() for p in kept] == ["older"]  # still on disk


def test_newer_source_replaces_dest_and_the_old_dest_is_kept(tmp_path):
    dest = _write(tmp_path / "02_analysis" / "a.json", "older", 1_000)
    src = _write(tmp_path / "02_analysis" / "old" / "a.json", "newer", 2_000)
    action = tcp._safe_move(src, dest, dry_run=False)
    assert action == "moved"
    assert dest.read_text() == "newer"
    kept = list((dest.parent / "_superseded").iterdir())
    assert [p.read_text() for p in kept] == ["older"]


def test_dry_run_changes_nothing(tmp_path):
    dest = _write(tmp_path / "02_analysis" / "a.json", "newer", 2_000)
    src = _write(tmp_path / "02_analysis" / "old" / "a.json", "older", 1_000)
    assert tcp._safe_move(src, dest, dry_run=True) == "would_set_aside_older_duplicate"
    assert src.read_text() == "older" and dest.read_text() == "newer"
    assert not (src.parent / "_superseded").exists()


def test_two_set_aside_files_with_one_name_both_survive(tmp_path):
    dest = _write(tmp_path / "02_analysis" / "a.json", "newest", 3_000)
    first = _write(tmp_path / "02_analysis" / "x" / "a.json", "one", 1_000)
    tcp._safe_move(first, dest, dry_run=False)
    _write(first, "two", 2_000)  # a second duplicate later arrives under the same name
    tcp._safe_move(first, dest, dry_run=False)
    kept = sorted(p.read_text() for p in (first.parent / "_superseded").iterdir())
    assert kept == ["one", "two"]  # neither was lost, although both were called a.json


def test_moving_to_a_free_destination_is_unchanged(tmp_path):
    src = _write(tmp_path / "a" / "f.json", "x", 1_000)
    dest = tmp_path / "b" / "f.json"
    assert tcp._safe_move(src, dest, dry_run=False) == "moved"
    assert dest.read_text() == "x" and not src.exists()

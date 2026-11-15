"""The policy-cache date cleanup never deletes a file whose bytes differ (#48, #215 review).

Covers the collision paths the #215 review found: a healed name landing on a
different file, two meetings mapping to one name, a caption-sidecar target
collision, and the dry run predicting collisions.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from llm.gemini.transcript_cache_paths import (
    DIR_RUNS,
    DIR_TRANSCRIPTS,
    ensure_jurisdiction_layout,
    fix_policy_cache_dates_from_title,
)

BASE = "2025-03-04_Council_Meeting"


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "UCchannel"
    ensure_jurisdiction_layout(root)
    return root


def _touch(path: Path, text: str, age_s: float = 0) -> Path:
    path.write_text(text, encoding="utf-8")
    t = time.time() - age_s
    os.utime(path, (t, t))
    return path


def _files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "README.md"
    }


def test_healing_a_name_keeps_a_different_file(tmp_path: Path) -> None:
    root = _root(tmp_path)
    runs = root / DIR_RUNS
    _touch(runs / f"{BASE}.diagrams.md", "CLEAN-OLD", age_s=600)
    _touch(runs / f"{BASE}.diagrams.diagrams.md", "DOUBLED-NEWER")
    stats = fix_policy_cache_dates_from_title(root)
    contents = sorted(_files(root).values())
    assert "CLEAN-OLD" in contents and "DOUBLED-NEWER" in contents, stats
    assert stats.get("skipped_collision", 0) == 1, stats


def test_healing_a_name_removes_an_identical_copy(tmp_path: Path) -> None:
    root = _root(tmp_path)
    runs = root / DIR_RUNS
    _touch(runs / f"{BASE}.diagrams.md", "SAME", age_s=600)
    _touch(runs / f"{BASE}.diagrams.diagrams.md", "SAME")
    stats = fix_policy_cache_dates_from_title(root)
    assert [p.name for p in runs.glob("*.md")] == [f"{BASE}.diagrams.md"], stats
    assert stats.get("removed_identical_duplicate", 0) == 1, stats


def test_two_meetings_with_one_name_both_survive(tmp_path: Path) -> None:
    root = _root(tmp_path)
    tr = root / DIR_TRANSCRIPTS
    title = "Council Meeting 04.28.26"
    _touch(tr / "2026-05-01_Council_Meeting_04.28.26.json", json.dumps({"title": title, "video_id": "aaaaaaaaaaa"}), 600)
    _touch(tr / "2026-05-02_Council_Meeting_04.28.26.json", json.dumps({"title": title, "video_id": "bbbbbbbbbbb"}))
    fix_policy_cache_dates_from_title(root)
    video_ids = sorted(json.loads(t)["video_id"] for t in _files(root).values())
    assert video_ids == ["aaaaaaaaaaa", "bbbbbbbbbbb"]


def test_sidecar_never_overwrites_a_different_target(tmp_path: Path) -> None:
    root = _root(tmp_path)
    tr = root / DIR_TRANSCRIPTS
    title = "Council Meeting 03.04.25"
    src_stem = "2025-03-10_Council_Meeting_03.04.25"
    dest_stem = "2025-03-04_Council_Meeting"
    _touch(tr / f"{src_stem}.json", json.dumps({"title": title, "video_id": "ddddddddddd"}), 600)
    _touch(tr / f"{src_stem}.caption_raw_data.json", json.dumps([{"text": "SRC-SIDECAR"}]), 600)
    _touch(tr / f"{dest_stem}.caption_raw_data.json", json.dumps([{"text": "OTHER-SIDECAR"}]))
    stats = fix_policy_cache_dates_from_title(root)
    text = "".join(_files(root).values())
    assert "SRC-SIDECAR" in text and "OTHER-SIDECAR" in text, stats


def test_dry_run_predicts_a_collision_between_two_sources(tmp_path: Path) -> None:
    root = _root(tmp_path)
    runs = root / DIR_RUNS
    _touch(runs / f"{BASE}.diagrams.diagrams.md", "ONE", age_s=600)
    _touch(runs / f"{BASE}.diagrams.diagrams.diagrams.md", "TWO")
    dry = fix_policy_cache_dates_from_title(root, dry_run=True)
    real = fix_policy_cache_dates_from_title(root)
    assert dry.get("would_move", 0) == real.get("moved", 0) == 1, (dry, real)
    assert dry.get("would_skip_collision", 0) == real.get("skipped_collision", 0) == 1, (dry, real)
    assert sorted(_files(root).values()) == ["ONE", "TWO"]

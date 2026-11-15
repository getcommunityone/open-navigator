"""The policy-cache date cleanup must converge: a second run moves nothing (#48)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from llm.gemini.transcript_cache_paths import (
    DIR_ANALYSIS,
    DIR_REPORTS,
    DIR_RUNS,
    DIR_TRANSCRIPTS,
    ensure_jurisdiction_layout,
    fix_policy_cache_dates_from_title,
    meeting_media_basename,
)

TITLES = [
    "City Council Meeting 10.14.25 (rescheduled from 10.7.25)",
    "Budget Hearing June 3, 2025 and June 10, 2025",
    "Regular Meeting 2025-04-01 Agenda 20250325",
    "Council Meeting - March 4, 2025",
]


def _seed(root: Path) -> None:
    ensure_jurisdiction_layout(root)
    for i, title in enumerate(TITLES):
        payload = {"title": title, "video_id": f"vid{i:08d}"}
        base = meeting_media_basename(title, None)
        for sub, suffix, body in (
            (DIR_TRANSCRIPTS, ".json", payload),
            (DIR_ANALYSIS, ".json", payload),
            (DIR_REPORTS, ".md", None),
            (DIR_RUNS, ".meta.json", payload),
            (DIR_RUNS, ".diagrams.md", None),
        ):
            text = json.dumps(body) if body else "# report\n"
            (root / sub / f"{base}{suffix}").write_text(text, encoding="utf-8")


def _moves(stats: dict) -> int:
    return sum(v for k, v in stats.items() if k.endswith("moved") or k.startswith("would_move"))


@pytest.mark.parametrize("dry_run_second", [False, True])
def test_second_run_moves_nothing(tmp_path: Path, dry_run_second: bool) -> None:
    root = tmp_path / "UCchannel"
    _seed(root)
    fix_policy_cache_dates_from_title(root)
    second = fix_policy_cache_dates_from_title(root, dry_run=dry_run_second)
    assert _moves(second) == 0, second


def test_diagrams_suffix_is_not_repeated(tmp_path: Path) -> None:
    root = tmp_path / "UCchannel"
    _seed(root)
    for _ in range(3):
        fix_policy_cache_dates_from_title(root)
    names = [p.name for p in (root / DIR_RUNS).glob("*.diagrams.md")]
    assert names and all(n.count(".diagrams") == 1 for n in names), names


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("sidecar_newer", [True, False])
def test_caption_sidecars_are_never_merged_into_the_transcript(tmp_path: Path, sidecar_newer: bool) -> None:
    """A caption sidecar must not overwrite, or be deleted as a duplicate of, its transcript."""
    root = tmp_path / "UCchannel"
    _seed(root)
    transcripts = root / DIR_TRANSCRIPTS
    for main in list(transcripts.glob("*.json")):
        for suffix in (".caption_raw_data.json", ".caption_formatted.json"):
            side = transcripts / f"{main.stem}{suffix}"
            side.write_text(json.dumps([{"text": "raw"}]), encoding="utf-8")
            offset = 60 if sidecar_newer else -60
            os.utime(side, (time.time() + offset, time.time() + offset))
    fix_policy_cache_dates_from_title(root)
    before = _snapshot(root)
    assert len([n for n in before if ".caption_" in n]) == 2 * len(TITLES)
    for name, text in before.items():
        if name.startswith(DIR_TRANSCRIPTS) and ".caption_" not in name:
            assert json.loads(text)["title"] in TITLES, name
    fix_policy_cache_dates_from_title(root)
    assert _snapshot(root) == before

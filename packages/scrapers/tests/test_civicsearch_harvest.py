"""Unit tests for the CivicSearch harvester merge/keyword logic.

These cover the pure in-memory logic (no network): per-place keyword extraction
and the by-vid_id meeting merge that accumulates matched keywords, dedups
snippets, and collects non-negative topic ids.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scrapers.civicsearch.harvest import CivicSearchHarvester, _place_keywords


def _harvester() -> CivicSearchHarvester:
    # Only client.portal is read by __init__; the network is never touched here.
    client = SimpleNamespace(portal="schools")
    return CivicSearchHarvester(
        client=client,  # type: ignore[arg-type]
        cache_dir=Path("/tmp/civicsearch-test"),
        max_places=10,
    )


def _place() -> dict:
    return {"query_id": "p", "display_name": "P", "lat": 1.0, "lon": 2.0}


def test_place_keywords_dedups_case_insensitively_preserving_order():
    payload = {
        "issue_keywords": ["Budget", "School Safety", "budget"],
        "keywords": ["School Safety", "Attendance"],
    }
    assert _place_keywords(payload) == ["Budget", "School Safety", "Attendance"]


def test_place_keywords_handles_missing_keys():
    assert _place_keywords({}) == []
    assert _place_keywords({"keywords": [" ", "x", None]}) == ["x"]


def test_merge_meeting_accumulates_keywords_and_topics():
    h = _harvester()
    store: dict[str, dict] = {}
    place = _place()
    result = {
        "vid_id": "abc123def45",
        "title": "Board Meeting",
        "date": "2026-01-15",
        "location": "P",
        "location_query_id": "p",
        "distance": 0,
        "has_approximate_timings": False,
        "snippets": [
            {"text": "alpha", "timestamp": 10.0, "topic_id": 5},
            {"text": "no topic", "timestamp": 20.0, "topic_id": -1},
        ],
    }
    h._merge_meeting(store, result, place, "budget")
    # Second keyword surfaces the same meeting with a new + a duplicate snippet.
    result2 = dict(result)
    result2["snippets"] = [
        {"text": "alpha", "timestamp": 10.0, "topic_id": 5},   # duplicate
        {"text": "beta", "timestamp": 30.0, "topic_id": 7},     # new
    ]
    h._merge_meeting(store, result2, place, "safety")

    rec = store["abc123def45"]
    assert rec["matched_keywords"] == ["budget", "safety"]
    # 3 distinct snippets after dedup on (timestamp, text)
    assert len(rec["snippets"]) == 3
    # only non-negative topic ids, de-duplicated, in first-seen order
    assert rec["topic_ids"] == [5, 7]
    assert rec["youtube_url"] == "https://www.youtube.com/watch?v=abc123def45"


def test_merge_meeting_skips_missing_vid():
    h = _harvester()
    store: dict[str, dict] = {}
    h._merge_meeting(store, {"snippets": []}, _place(), "budget")
    assert store == {}


def _harvester_at(cache_dir: Path, *, incremental: bool) -> CivicSearchHarvester:
    client = SimpleNamespace(portal="schools")
    return CivicSearchHarvester(
        client=client,  # type: ignore[arg-type]
        cache_dir=cache_dir,
        max_places=10,
        incremental=incremental,
    )


def _meetings_on_disk(cache_dir: Path) -> list[str]:
    path = cache_dir / "schools" / "meetings.jsonl"
    return [json.loads(line)["vid_id"] for line in path.read_text().splitlines() if line.strip()]


def test_streaming_append_and_incremental_dedupe(tmp_path: Path):
    # First run: stream two places' meetings to disk as they finish.
    h = _harvester_at(tmp_path, incremental=False)
    h.open()
    h._flush_place_meetings({"vid_aaaaaaa": {"vid_id": "vid_aaaaaaa"}})
    h._flush_place_meetings({"vid_bbbbbbb": {"vid_id": "vid_bbbbbbb"}})
    # Files are written live, not buffered to the end.
    assert _meetings_on_disk(tmp_path) == ["vid_aaaaaaa", "vid_bbbbbbb"]
    h.close()

    # Second run, incremental: known vids are loaded and skipped; only new appended.
    h2 = _harvester_at(tmp_path, incremental=True)
    h2.open()
    assert h2._seen_vids == {"vid_aaaaaaa", "vid_bbbbbbb"}
    h2._flush_place_meetings({
        "vid_aaaaaaa": {"vid_id": "vid_aaaaaaa"},  # already seen -> skipped
        "vid_ccccccc": {"vid_id": "vid_ccccccc"},  # new -> appended
    })
    h2.close()

    assert h2._new_meetings == 1
    assert _meetings_on_disk(tmp_path) == ["vid_aaaaaaa", "vid_bbbbbbb", "vid_ccccccc"]


def test_non_incremental_truncates(tmp_path: Path):
    h = _harvester_at(tmp_path, incremental=False)
    h.open()
    h._flush_place_meetings({"vid_aaaaaaa": {"vid_id": "vid_aaaaaaa"}})
    h.close()

    # A fresh (non-incremental) run starts the file over.
    h2 = _harvester_at(tmp_path, incremental=False)
    h2.open()
    assert h2._seen_vids == set()
    h2._flush_place_meetings({"vid_zzzzzzz": {"vid_id": "vid_zzzzzzz"}})
    h2.close()
    assert _meetings_on_disk(tmp_path) == ["vid_zzzzzzz"]

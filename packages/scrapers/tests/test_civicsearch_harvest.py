"""Unit tests for the CivicSearch harvester merge/keyword logic.

These cover the pure in-memory logic (no network): per-place keyword extraction
and the by-vid_id meeting merge that accumulates matched keywords, dedups
snippets, and collects non-negative topic ids.
"""
from __future__ import annotations

from scrapers.civicsearch.harvest import CivicSearchHarvester, _place_keywords


def _harvester() -> CivicSearchHarvester:
    # client is unused by the pure-logic methods under test.
    return CivicSearchHarvester(client=None, max_places=10)  # type: ignore[arg-type]


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
    h._merge_meeting(result, place, "budget")
    # Second keyword surfaces the same meeting with a new + a duplicate snippet.
    result2 = dict(result)
    result2["snippets"] = [
        {"text": "alpha", "timestamp": 10.0, "topic_id": 5},   # duplicate
        {"text": "beta", "timestamp": 30.0, "topic_id": 7},     # new
    ]
    h._merge_meeting(result2, place, "safety")

    rec = h.meetings["abc123def45"]
    assert rec["matched_keywords"] == ["budget", "safety"]
    # 3 distinct snippets after dedup on (timestamp, text)
    assert len(rec["snippets"]) == 3
    # only non-negative topic ids, de-duplicated, in first-seen order
    assert rec["topic_ids"] == [5, 7]
    assert rec["youtube_url"] == "https://www.youtube.com/watch?v=abc123def45"


def test_merge_meeting_skips_missing_vid():
    h = _harvester()
    h._merge_meeting({"snippets": []}, _place(), "budget")
    assert h.meetings == {}

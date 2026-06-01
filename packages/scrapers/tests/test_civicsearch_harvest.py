"""Unit tests for the CivicSearch harvester merge/keyword logic.

These cover the pure in-memory logic (no network): per-place keyword extraction,
the by-vid_id meeting merge that accumulates matched keywords / dedups snippets /
collects non-negative topic ids, and the ``get_place_list``-driven place listing
(the discovery path that replaced the old BFS crawl) — exercised with a mocked
client so no network is touched.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from scrapers.civicsearch.harvest import (
    CivicSearchHarvester,
    _place_from_list_item,
    _place_keywords,
)


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


# --------------------------------------------------------------- place listing
# The discovery path is now a single get_place_list call (no BFS). These tests
# mock that endpoint so no network is touched.

_ANDALUSIA = {
    "query_id": "andalusia-alabama",
    "name": "Andalusia, AL",
    "state_name": "Alabama",
    "latitude": 31.309125,
    "longitude": -86.482844,
    "num_meetings": 27,
    "last_meeting_link": "https://example/x",
    "last_meeting_title": "Council",
}


def test_place_from_list_item_maps_fields():
    place = _place_from_list_item(_ANDALUSIA, "cities")
    assert place == {
        "portal": "cities",
        "query_id": "andalusia-alabama",
        "display_name": "Andalusia, AL",
        "lat": 31.309125,
        "lon": -86.482844,
        "num_meetings": 27,
        "state_name": "Alabama",
        "scraped_at": place["scraped_at"],  # timestamp filled in
    }


def test_place_from_list_item_rejects_incomplete():
    assert _place_from_list_item({"name": "no id"}, "cities") is None
    assert _place_from_list_item(
        {"query_id": "x", "latitude": 1.0}, "cities"  # missing longitude
    ) is None


class _ListClient:
    """Mock client exposing only get_place_list (the discovery path)."""

    def __init__(self, items: list[dict], portal: str = "cities") -> None:
        self.portal = portal
        self._items = items
        self.calls = 0

    async def get_place_list(self) -> list[dict]:
        self.calls += 1
        return self._items


def _list_harvester(tmp_path: Path, items: list[dict], *, max_places=None, incremental=False):
    return CivicSearchHarvester(
        client=_ListClient(items),  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_places=max_places,
        incremental=incremental,
    )


def _places_on_disk(cache_dir: Path) -> list[str]:
    path = cache_dir / "cities" / "places.jsonl"
    return [json.loads(line)["query_id"] for line in path.read_text().splitlines() if line.strip()]


def test_list_places_populates_from_get_place_list(tmp_path: Path):
    items = [
        _ANDALUSIA,
        {"query_id": "b-town", "name": "B, AL", "latitude": 1.0, "longitude": 2.0,
         "num_meetings": 3, "state_name": "Alabama"},
        {"name": "bad-no-id", "latitude": 9.0, "longitude": 9.0},  # dropped
    ]
    h = _list_harvester(tmp_path, items)
    h.open()
    asyncio.run(h.list_places())
    h.close()

    assert h.client.calls == 1
    assert set(h.places) == {"andalusia-alabama", "b-town"}
    assert h.places["andalusia-alabama"]["display_name"] == "Andalusia, AL"
    assert _places_on_disk(tmp_path) == ["andalusia-alabama", "b-town"]


def test_list_places_respects_max_places_cap(tmp_path: Path):
    items = [
        _ANDALUSIA,
        {"query_id": "b-town", "name": "B, AL", "latitude": 1.0, "longitude": 2.0},
        {"query_id": "c-town", "name": "C, AL", "latitude": 3.0, "longitude": 4.0},
    ]
    h = _list_harvester(tmp_path, items, max_places=1)
    h.open()
    asyncio.run(h.list_places())
    h.close()
    assert list(h.places) == ["andalusia-alabama"]


def test_harvest_skips_fully_done_place(tmp_path: Path, monkeypatch):
    # A place whose on-disk captured count already meets num_meetings is skipped.
    h = _list_harvester(tmp_path, [_ANDALUSIA], incremental=True)
    h.open()
    asyncio.run(h.list_places())
    # Simulate 27 already-captured meetings on disk for this place.
    h._disk_counts["andalusia-alabama"] = 27

    swept: list[str] = []

    async def _fake_sweep(place):
        swept.append(place["query_id"])
        return {}

    monkeypatch.setattr(h, "_harvest_place_meetings", _fake_sweep)
    asyncio.run(h.harvest_meetings())
    h.close()
    assert swept == []  # fully-done place skipped, never swept


def test_harvest_sweeps_incomplete_place(tmp_path: Path, monkeypatch):
    h = _list_harvester(tmp_path, [_ANDALUSIA], incremental=True)
    h.open()
    asyncio.run(h.list_places())
    h._disk_counts["andalusia-alabama"] = 5  # below num_meetings (27) -> sweep

    swept: list[str] = []

    async def _fake_sweep(place):
        swept.append(place["query_id"])
        return {}

    monkeypatch.setattr(h, "_harvest_place_meetings", _fake_sweep)
    asyncio.run(h.harvest_meetings())
    h.close()
    assert swept == ["andalusia-alabama"]

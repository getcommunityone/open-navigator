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


def test_harvest_skips_best_effort_swept_place(tmp_path: Path, monkeypatch):
    # A place that was fully swept once but stayed short of num_meetings must
    # NOT be re-swept on a later incremental run (it would re-grind every axis).
    h = _list_harvester(tmp_path, [_ANDALUSIA], incremental=True)
    h.open()
    asyncio.run(h.list_places())
    h._disk_counts["andalusia-alabama"] = 25  # short of 27, but already swept
    h._swept["andalusia-alabama"] = 27        # swept at this target before

    swept: list[str] = []

    async def _fake_sweep(place):
        swept.append(place["query_id"])
        return {}

    monkeypatch.setattr(h, "_harvest_place_meetings", _fake_sweep)
    asyncio.run(h.harvest_meetings())
    h.close()
    assert swept == []  # best-effort-swept place skipped, not re-ground


def test_harvest_reweeps_when_num_meetings_grows(tmp_path: Path, monkeypatch):
    # If num_meetings grew beyond the swept target, re-sweep (new meetings exist).
    h = _list_harvester(tmp_path, [_ANDALUSIA], incremental=True)
    h.open()
    asyncio.run(h.list_places())
    h._disk_counts["andalusia-alabama"] = 25
    h._swept["andalusia-alabama"] = 20  # last swept at 20; now advertises 27

    swept: list[str] = []

    async def _fake_sweep(place):
        swept.append(place["query_id"])
        return {}

    monkeypatch.setattr(h, "_harvest_place_meetings", _fake_sweep)
    asyncio.run(h.harvest_meetings())
    h.close()
    assert swept == ["andalusia-alabama"]  # target grew -> re-swept


"""Case 7 -- Offline integration tests for scrapers.civicsearch.harvest.

Validates the full list_places -> harvest_meetings -> flush flow without any
live HTTP requests.  All async client methods are replaced with _StubClient;
tmp_path and pytest.fixture are used throughout per the engineering directives.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from scrapers.civicsearch.harvest import (
    CivicSearchHarvester,
    _extract_topic_ids,
    _safe_json,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def portal() -> str:
    """Target portal name used across all Case-7 tests."""
    return "cities"


@pytest.fixture()
def andalusia_item() -> dict[str, Any]:
    """Minimal get_place_list item that _place_from_list_item will accept."""
    return {
        "query_id": "andalusia-alabama",
        "name": "Andalusia, AL",
        "state_name": "Alabama",
        "latitude": 31.309125,
        "longitude": -86.482844,
        "num_meetings": 3,
    }


@pytest.fixture()
def place_list(andalusia_item: dict[str, Any]) -> list[dict[str, Any]]:
    """Two valid items + one bad item (missing query_id) for the stub."""
    return [
        andalusia_item,
        {
            "query_id": "b-town",
            "name": "B, AL",
            "latitude": 1.0,
            "longitude": 2.0,
            "num_meetings": 1,
            "state_name": "Alabama",
        },
        {"name": "no-id-bad", "latitude": 9.0, "longitude": 9.0},  # dropped
    ]


class _StubClient:
    """Fully offline CivicSearchClient stand-in.

    Only the three methods called by CivicSearchHarvester are implemented;
    all return pre-canned dicts or empty dicts.
    """

    def __init__(
        self,
        portal: str,
        place_list: list[dict[str, Any]],
        search_responses: dict[str, dict[str, Any]] | None = None,
        topics_responses: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.portal = portal
        self._place_list = place_list
        # Keyed by keyword string; default response is empty {}.
        self._search_responses: dict[str, dict[str, Any]] = search_responses or {}
        self._topics_responses: dict[str, dict[str, Any]] = topics_responses or {}

        # Introspection counters
        self.get_place_list_calls: int = 0
        self.search_calls: list[dict[str, Any]] = []
        self.topics_calls: list[str] = []

    async def get_place_list(self) -> list[dict[str, Any]]:
        self.get_place_list_calls += 1
        return self._place_list

    async def get_topics_by_city(self, query_id: str) -> dict[str, Any]:
        self.topics_calls.append(query_id)
        return self._topics_responses.get(query_id, {})

    async def search(
        self,
        *,
        keywords: str | None = None,
        topics: list[int] | None = None,
        lonlat: tuple[float, float] | None = None,
        search_radius: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        self.search_calls.append(
            {"keywords": keywords, "topics": topics, "lonlat": lonlat}
        )
        key = keywords or ""
        return self._search_responses.get(key, {})


@pytest.fixture()
def stub_client(portal: str, place_list: list[dict[str, Any]]) -> _StubClient:
    """Stub client pre-loaded with the canonical two-place fixture."""
    return _StubClient(portal=portal, place_list=place_list)


@pytest.fixture()
def harvester(stub_client: _StubClient, tmp_path: Path) -> CivicSearchHarvester:
    """Non-incremental harvester wired to the stub client and a tmp_path cache dir."""
    return CivicSearchHarvester(
        client=stub_client,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        max_places=None,
        incremental=False,
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse all non-blank lines from a JSONL file."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Case 7a -- list_places populates dict and streams to places.jsonl
# ---------------------------------------------------------------------------


def test_list_places_populates_and_streams(
    harvester: CivicSearchHarvester,
    stub_client: _StubClient,
    tmp_path: Path,
    portal: str,
) -> None:
    """list_places must call get_place_list exactly once, ingest the two valid
    items, silently drop the bad item, and flush both to places.jsonl."""
    harvester.open()
    asyncio.run(harvester.list_places())
    harvester.close()

    assert stub_client.get_place_list_calls == 1

    assert set(harvester.places) == {"andalusia-alabama", "b-town"}
    assert harvester.places["andalusia-alabama"]["display_name"] == "Andalusia, AL"
    assert harvester.places["andalusia-alabama"]["portal"] == portal

    places_path = tmp_path / portal / "places.jsonl"
    records = _read_jsonl(places_path)
    assert [r["query_id"] for r in records] == ["andalusia-alabama", "b-town"]
    assert all(r["portal"] == portal for r in records)


# ---------------------------------------------------------------------------
# Case 7b -- harvest_meetings writes to disk and deduplicates across keywords
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_meetings(
    portal: str, place_list: list[dict[str, Any]]
) -> _StubClient:
    """Stub whose 'city council' keyword returns one Andalusia meeting."""
    andalusia_meeting: dict[str, Any] = {
        "vid_id": "ANDALUSIA0001",
        "title": "Regular Council Meeting",
        "date": "2026-01-15",
        "location": "Andalusia, AL",
        "location_query_id": "andalusia-alabama",
        "distance": 0,
        "has_approximate_timings": False,
        "snippets": [
            {"text": "budget discussion", "timestamp": 90.0, "topic_id": 12}
        ],
    }
    search_resp: dict[str, dict[str, Any]] = {
        "city council": {
            "results": [andalusia_meeting],
            "topic_counts": [{"topic_id": 12}],
        },
        # All other broad keywords return empty -- ensures dedup is exercised.
    }
    return _StubClient(
        portal=portal, place_list=place_list, search_responses=search_resp
    )


def test_harvest_meetings_writes_and_deduplicates(
    client_with_meetings: _StubClient,
    tmp_path: Path,
    portal: str,
) -> None:
    """harvest_meetings must flush meetings to disk and never write the same
    vid_id twice within a single run (cross-keyword dedup via _seen_vids)."""
    h = CivicSearchHarvester(
        client=client_with_meetings,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        incremental=False,
    )
    h.open()
    asyncio.run(h.list_places())
    asyncio.run(h.harvest_meetings())
    h.close()

    meetings_path = tmp_path / portal / "meetings.jsonl"
    records = _read_jsonl(meetings_path)
    vids = [r["vid_id"] for r in records]

    assert "ANDALUSIA0001" in vids
    # Cross-keyword dedup must hold: no duplicate vid_ids.
    assert len(vids) == len(set(vids))
    # Every record must carry portal + schema_version (set by _merge_meeting).
    assert all(r["portal"] == portal for r in records)
    assert all("schema_version" in r for r in records)


# ---------------------------------------------------------------------------
# Case 7c -- incremental resume skips fully-done places
# ---------------------------------------------------------------------------


def test_incremental_resume_skips_fully_done_place(
    tmp_path: Path,
    portal: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once a place's on-disk captured count meets num_meetings, a subsequent
    incremental run must not call _harvest_place_meetings for it at all."""
    item: dict[str, Any] = {
        "query_id": "andalusia-alabama",
        "name": "Andalusia, AL",
        "state_name": "Alabama",
        "latitude": 31.309125,
        "longitude": -86.482844,
        "num_meetings": 2,
    }

    # --- Run 1: capture two meetings, filling num_meetings. ---
    client1 = _StubClient(portal=portal, place_list=[item])
    h1 = CivicSearchHarvester(
        client=client1,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        incremental=False,
    )
    h1.open()
    asyncio.run(h1.list_places())
    h1._flush_place_meetings(
        {
            "VID000000001": {
                "vid_id": "VID000000001",
                "place_query_id": "andalusia-alabama",
            },
            "VID000000002": {
                "vid_id": "VID000000002",
                "place_query_id": "andalusia-alabama",
            },
        }
    )
    h1.close()

    # --- Run 2: incremental -- place is fully done, must not be swept. ---
    client2 = _StubClient(portal=portal, place_list=[item])
    h2 = CivicSearchHarvester(
        client=client2,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        incremental=True,
    )

    swept: list[str] = []

    async def _fake_sweep(place: dict[str, Any]) -> dict[str, Any]:
        swept.append(place["query_id"])
        return {}

    monkeypatch.setattr(h2, "_harvest_place_meetings", _fake_sweep)
    h2.open()
    asyncio.run(h2.list_places())
    asyncio.run(h2.harvest_meetings())
    h2.close()

    assert swept == [], "Fully-done place must not trigger a new sweep"

    # Original meetings must still be on disk.
    vids = {r["vid_id"] for r in _read_jsonl(tmp_path / portal / "meetings.jsonl")}
    assert vids == {"VID000000001", "VID000000002"}


# ---------------------------------------------------------------------------
# Case 7d -- _extract_topic_ids handles all payload shapes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload, expected",
    [
        # topic_counts as a list of dicts
        (
            {
                "topic_counts": [
                    {"topic_id": 5},
                    {"topic_id": 12},
                    {"topic_id": -1},  # negative -- rejected
                ],
                "results": [],
            },
            {5, 12},
        ),
        # topic_counts as a string-keyed dict
        (
            {"topic_counts": {"5": 3, "bad": 0, "12": 1}},
            {5, 12},
        ),
        # topic_ids carried in snippet dicts
        (
            {
                "results": [
                    {
                        "vid_id": "x",
                        "snippets": [
                            {"topic_id": 7},
                            {"topic_id": -2},  # rejected
                            {"topic_id": 9},
                        ],
                    }
                ]
            },
            {7, 9},
        ),
        # completely empty payload
        ({}, set()),
    ],
)
def test_extract_topic_ids_variants(
    payload: dict[str, Any], expected: set[int]
) -> None:
    assert _extract_topic_ids(payload) == expected


# ---------------------------------------------------------------------------
# Case 7e -- _safe_json tolerates blank and malformed input
# ---------------------------------------------------------------------------


def test_safe_json_parses_valid_line() -> None:
    assert _safe_json('{"a": 1}') == {"a": 1}


def test_safe_json_returns_none_for_blank() -> None:
    assert _safe_json("   ") is None
    assert _safe_json("") is None


def test_safe_json_returns_none_for_truncated_record() -> None:
    assert _safe_json("{truncated bad json") is None


# ---------------------------------------------------------------------------
# Case 7f -- non-incremental open truncates stale JSONL files
# ---------------------------------------------------------------------------


def test_open_non_incremental_truncates_stale_files(
    tmp_path: Path, portal: str
) -> None:
    """When incremental=False, open() must truncate both JSONL files so a fresh
    run never appends to a previous run's output."""
    portal_dir = tmp_path / portal
    portal_dir.mkdir(parents=True)
    stale = '{"vid_id": "stale"}\n'
    (portal_dir / "meetings.jsonl").write_text(stale, encoding="utf-8")
    (portal_dir / "places.jsonl").write_text(stale, encoding="utf-8")

    client = _StubClient(portal=portal, place_list=[])
    h = CivicSearchHarvester(
        client=client,  # type: ignore[arg-type]
        cache_dir=tmp_path,
        incremental=False,
    )
    h.open()
    h.close()

    assert (portal_dir / "meetings.jsonl").read_text(encoding="utf-8") == ""
    assert (portal_dir / "places.jsonl").read_text(encoding="utf-8") == ""

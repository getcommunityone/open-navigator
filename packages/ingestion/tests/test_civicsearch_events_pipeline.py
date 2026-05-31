"""Unit tests for the CivicSearch events LAND pipeline."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from core_lib.pipeline.schemas import PipelineContext
from ingestion.civicsearch.events import (
    CivicSearchEventsPipeline,
    CivicSearchMeetingRow,
    _parse_date_iso,
    _parse_scraped_at,
)


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _meeting(**over) -> dict:
    base = {
        "schema_version": 1,
        "vid_id": "RFacSvSuLjU",
        "title": "Issaquah School District Board Meeting 01/15/2026",
        "meeting_date": "2026-01-15",
        "location": "Issaquah School District, Washington",
        "location_query_id": "issaquah-school-district-washington",
        "distance": 0,
        "has_approximate_timings": False,
        "youtube_url": "https://www.youtube.com/watch?v=RFacSvSuLjU",
        "place_query_id": "issaquah-school-district-washington",
        "place_lat": 47.5,
        "place_lon": -122.0,
        "matched_keywords": ["middle school", "attendance"],
        "snippets": [
            {"text": "Maywood <mark>Middle School</mark>", "timestamp": 140.0, "topic_id": 38},
            {"text": "no topic here", "timestamp": 200.0, "topic_id": -1},
        ],
        "topic_ids": [38, 41],
        "scraped_at": "2026-05-31T20:46:58.233717+00:00",
    }
    base.update(over)
    return base


def test_parse_date_iso():
    assert _parse_date_iso("2026-01-15") == date(2026, 1, 15)
    assert _parse_date_iso("2026-01-15T00:00:00") == date(2026, 1, 15)
    assert _parse_date_iso(None) is None
    assert _parse_date_iso("not-a-date") is None


def test_parse_scraped_at_tz_normalization():
    dt = _parse_scraped_at("2026-05-31T20:46:58+00:00")
    assert dt is not None and dt.tzinfo is not None
    # naive input is coerced to UTC
    naive = _parse_scraped_at("2026-05-31T20:46:58")
    assert naive is not None and naive.tzinfo == timezone.utc
    assert _parse_scraped_at("") is None


def test_row_schema_validates_and_drops_negative_topics_upstream():
    row = CivicSearchMeetingRow.model_validate({
        "source": "civicsearch",
        "source_version": "meetings.jsonl.v1",
        "natural_key": "RFacSvSuLjU",
        "vid_id": "RFacSvSuLjU",
        "meeting_date": date(2026, 1, 15),
        "matched_keywords": ["budget"],
        "snippets": [{"text": "x", "timestamp": 1.0, "topic_id": 3}],
        "topic_ids": [3],
        "scraped_at": datetime.now(timezone.utc),
    })
    assert row.vid_id == "RFacSvSuLjU"
    assert row.topic_ids == [3]


def test_row_schema_rejects_overlong_vid_id():
    with pytest.raises(Exception):
        CivicSearchMeetingRow.model_validate({
            "source": "civicsearch",
            "source_version": "v1",
            "natural_key": "x",
            "vid_id": "x" * 25,  # > max_length=20
        })


@pytest.mark.asyncio
async def test_extract_maps_fields_and_skips_missing_vid(tmp_path):
    jsonl = tmp_path / "meetings.jsonl"
    rows = [
        _meeting(),
        _meeting(vid_id="", title="no id"),  # should be skipped
        _meeting(vid_id="OTHER123abc", topic_ids=[1, "bad", 2]),
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl)
    out = [r async for r in pipeline.extract(_ctx())]

    assert len(out) == 2  # the empty-vid row was skipped
    first = out[0]
    assert first["source"] == "civicsearch"
    assert first["natural_key"] == "RFacSvSuLjU"
    assert first["meeting_date"] == date(2026, 1, 15)
    assert first["raw_record"]["vid_id"] == "RFacSvSuLjU"
    # non-int topic ids are filtered out in extract
    assert out[1]["topic_ids"] == [1, 2]
    # every extracted dict validates against the row schema
    for raw in out:
        assert pipeline.validate(raw) is not None


@pytest.mark.asyncio
async def test_extract_respects_limit(tmp_path):
    jsonl = tmp_path / "meetings.jsonl"
    rows = [_meeting(vid_id=f"vid{i:08d}") for i in range(5)]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl, limit=2)
    out = [r async for r in pipeline.extract(_ctx())]
    assert len(out) == 2

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


"""Case 9 -- Extended offline tests for ingestion.civicsearch.events.

Supplements the existing test_civicsearch_events_pipeline.py with focused
tests for the extract() generator's field-mapping contract, JSONL error
handling, blank-line tolerance, date/timestamp parsing edge-cases, and the
limit enforcement semantics.

No database sessions are opened -- extract() is exercised directly.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from core_lib.pipeline.schemas import PipelineContext
from ingestion.civicsearch.events import (
    BASE_TABLE,
    SCHOOLS_TABLE,
    CivicSearchEventsPipeline,
    CivicSearchMeetingRow,
    _default_jsonl,
    _parse_date_iso,
    _parse_scraped_at,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="case9", started_at=datetime.now(timezone.utc))


def _meeting(**overrides) -> dict:
    """Construct a minimal valid meeting record, applying any overrides."""
    base: dict = {
        "schema_version": 2,
        "portal": "cities",
        "vid_id": "RFacSvSuLjU",
        "title": "Issaquah SD Board Meeting 01/15/2026",
        "meeting_date": "2026-01-15",
        "location": "Issaquah School District, Washington",
        "location_query_id": "issaquah-school-district-washington",
        "distance": 0,
        "has_approximate_timings": False,
        "youtube_url": "https://www.youtube.com/watch?v=RFacSvSuLjU",
        "place_query_id": "issaquah-school-district-washington",
        "place_lat": 47.529812,
        "place_lon": -122.017456,
        "matched_keywords": ["middle school", "attendance"],
        "snippets": [
            {"text": "Maywood Middle School", "timestamp": 140.0, "topic_id": 38},
            {"text": "no topic", "timestamp": 200.0, "topic_id": -1},
        ],
        "topic_ids": [38, 41],
        "scraped_at": "2026-05-31T20:46:58.233717+00:00",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def jsonl_one(tmp_path: Path) -> Path:
    """JSONL with one valid meeting."""
    p = tmp_path / "meetings.jsonl"
    p.write_text(json.dumps(_meeting()) + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _default_jsonl path derivation
# ---------------------------------------------------------------------------


def test_default_jsonl_cities_points_to_cities_dir() -> None:
    path = _default_jsonl(schools=False)
    assert "cities" in str(path)
    assert path.name == "meetings.jsonl"


def test_default_jsonl_schools_points_to_schools_dir() -> None:
    path = _default_jsonl(schools=True)
    assert "schools" in str(path)


# ---------------------------------------------------------------------------
# FileNotFoundError when JSONL path is missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_raises_on_missing_jsonl(tmp_path: Path) -> None:
    p = CivicSearchEventsPipeline(jsonl_path=tmp_path / "nonexistent.jsonl")
    with pytest.raises(FileNotFoundError):
        async for _ in p.extract(_ctx()):
            pass


# ---------------------------------------------------------------------------
# Field mapping -- every extract field is correctly populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_field_mapping(tmp_path: Path) -> None:
    """Every field produced by extract() must be correctly mapped from the
    raw JSONL record and pass schema validation."""
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text(json.dumps(_meeting()) + "\n", encoding="utf-8")

    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl)
    rows = [r async for r in pipeline.extract(_ctx())]

    assert len(rows) == 1
    row = rows[0]

    assert row["source"] == "civicsearch"
    assert row["source_version"] == "meetings.jsonl.v2"
    assert row["natural_key"] == "RFacSvSuLjU"
    assert row["vid_id"] == "RFacSvSuLjU"
    assert row["meeting_date"] == date(2026, 1, 15)
    assert row["place_lat"] == pytest.approx(47.529812)
    assert row["place_lon"] == pytest.approx(-122.017456)
    assert row["matched_keywords"] == ["middle school", "attendance"]
    # Negative topic_id in snippets must survive; only topic_ids list is filtered.
    assert row["snippets"][1]["topic_id"] == -1
    # topic_ids: both ints present in raw (filtering of non-ints only)
    assert row["topic_ids"] == [38, 41]
    assert row["raw_record"]["vid_id"] == "RFacSvSuLjU"
    # scraped_at must be timezone-aware datetime
    assert isinstance(row["scraped_at"], datetime)
    assert row["scraped_at"].tzinfo is not None
    # Schema round-trip
    validated = pipeline.validate(row)
    assert validated is not None
    assert validated.vid_id == "RFacSvSuLjU"


# ---------------------------------------------------------------------------
# Non-integer topic_ids are filtered out during extract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_filters_non_int_topic_ids(tmp_path: Path) -> None:
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text(
        json.dumps(_meeting(vid_id="OTHER123abc", topic_ids=[1, "bad", None, 2])) + "\n",
        encoding="utf-8",
    )
    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl)
    rows = [r async for r in pipeline.extract(_ctx())]
    assert rows[0]["topic_ids"] == [1, 2]


# ---------------------------------------------------------------------------
# Rows with blank vid_id are skipped silently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_skips_blank_vid_id(tmp_path: Path) -> None:
    lines = [
        json.dumps(_meeting(vid_id="")),           # blank -- skipped
        json.dumps(_meeting(vid_id="  ")),         # whitespace-only -- skipped
        json.dumps(_meeting(vid_id="VALID123abc")),  # kept
    ]
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl)
    rows = [r async for r in pipeline.extract(_ctx())]
    assert len(rows) == 1
    assert rows[0]["vid_id"] == "VALID123abc"


# ---------------------------------------------------------------------------
# Blank lines in the JSONL file are silently skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_skips_blank_lines(tmp_path: Path) -> None:
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text(
        "\n"
        + json.dumps(_meeting()) + "\n"
        + "   \n"
        + json.dumps(_meeting(vid_id="SECOND12345")) + "\n",
        encoding="utf-8",
    )
    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl)
    rows = [r async for r in pipeline.extract(_ctx())]
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Malformed JSON raises ValueError with the line number
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_raises_on_malformed_json(tmp_path: Path) -> None:
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text("{bad json on line 1\n", encoding="utf-8")
    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl)
    with pytest.raises(ValueError, match=r"Line 1"):
        async for _ in pipeline.extract(_ctx()):
            pass


# ---------------------------------------------------------------------------
# limit=N stops after N records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_limit_stops_early(tmp_path: Path) -> None:
    rows_data = [_meeting(vid_id=f"vid{i:09d}") for i in range(10)]
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in rows_data) + "\n", encoding="utf-8")

    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl, limit=3)
    out = [r async for r in pipeline.extract(_ctx())]
    assert len(out) == 3


@pytest.mark.asyncio
async def test_extract_limit_none_returns_all(tmp_path: Path) -> None:
    rows_data = [_meeting(vid_id=f"vid{i:09d}") for i in range(5)]
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in rows_data) + "\n", encoding="utf-8")

    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl, limit=None)
    out = [r async for r in pipeline.extract(_ctx())]
    assert len(out) == 5


# ---------------------------------------------------------------------------
# missing/null meeting_date is gracefully handled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_null_meeting_date(tmp_path: Path) -> None:
    jsonl = tmp_path / "m.jsonl"
    jsonl.write_text(
        json.dumps(_meeting(meeting_date=None)) + "\n", encoding="utf-8"
    )
    pipeline = CivicSearchEventsPipeline(jsonl_path=jsonl)
    rows = [r async for r in pipeline.extract(_ctx())]
    assert rows[0]["meeting_date"] is None


# ---------------------------------------------------------------------------
# _parse_date_iso edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026-01-15", date(2026, 1, 15)),
        ("2026-01-15T00:00:00", date(2026, 1, 15)),
        ("2026-01-15 12:30:00", date(2026, 1, 15)),  # space-separated datetime
        (None, None),
        ("", None),
        ("  ", None),
        ("not-a-date", None),
        (20260115, date(2026, 1, 15)),  # int -> str '20260115' parsed as YYYYMMDD by 3.11+
    ],
)
def test_parse_date_iso_parametrized(raw, expected) -> None:
    assert _parse_date_iso(raw) == expected


# ---------------------------------------------------------------------------
# _parse_scraped_at edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, tzinfo_is_none",
    [
        ("2026-05-31T20:46:58+00:00", False),    # already UTC-aware
        ("2026-05-31T20:46:58Z", False),          # Z suffix
        ("2026-05-31T20:46:58", True),             # naive -- must get UTC attached
        (None, None),
        ("", None),
        ("garbage", None),
    ],
)
def test_parse_scraped_at_parametrized(raw, tzinfo_is_none) -> None:
    result = _parse_scraped_at(raw)
    if tzinfo_is_none is None:
        assert result is None
    else:
        assert result is not None
        if tzinfo_is_none:
            # Naive inputs must be coerced to UTC, so tzinfo is NOT None.
            assert result.tzinfo is not None
        else:
            assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# CivicSearchMeetingRow schema -- boundary validation
# ---------------------------------------------------------------------------


def test_row_schema_rejects_empty_vid_id() -> None:
    with pytest.raises(Exception):
        CivicSearchMeetingRow.model_validate(
            {
                "source": "civicsearch",
                "source_version": "v1",
                "natural_key": "x",
                "vid_id": "",  # min_length=1 violated
            }
        )


def test_row_schema_rejects_vid_id_over_20_chars() -> None:
    with pytest.raises(Exception):
        CivicSearchMeetingRow.model_validate(
            {
                "source": "civicsearch",
                "source_version": "v1",
                "natural_key": "x",
                "vid_id": "x" * 21,  # max_length=20 violated
            }
        )


def test_row_schema_accepts_minimal_record() -> None:
    row = CivicSearchMeetingRow.model_validate(
        {
            "source": "civicsearch",
            "source_version": "meetings.jsonl.v2",
            "natural_key": "RFacSvSuLjU",
            "vid_id": "RFacSvSuLjU",
        }
    )
    assert row.vid_id == "RFacSvSuLjU"
    assert row.topic_ids == []
    assert row.snippets == []
    assert row.matched_keywords == []


# ---------------------------------------------------------------------------
# Pipeline constructor: table selection drives default JSONL path
# ---------------------------------------------------------------------------


def test_pipeline_schools_table_uses_schools_subdir() -> None:
    p = CivicSearchEventsPipeline(table=SCHOOLS_TABLE)
    assert "schools" in str(p._jsonl_path)


def test_pipeline_base_table_uses_cities_subdir() -> None:
    p = CivicSearchEventsPipeline(table=BASE_TABLE)
    assert "cities" in str(p._jsonl_path)


def test_pipeline_explicit_jsonl_overrides_default(tmp_path: Path) -> None:
    custom = tmp_path / "custom.jsonl"
    p = CivicSearchEventsPipeline(jsonl_path=custom)
    assert p._jsonl_path == custom

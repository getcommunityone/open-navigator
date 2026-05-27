"""Unit tests for the YouTube events pipeline (LAND layer).

Offline only: no DB, no network. Exercises the pure helpers, the row schema,
the JSON/JSONL reader, and the extract envelope.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from ingestion.youtube.events import (  # noqa: E402
    YoutubeEventRow,
    YoutubeEventsPipeline,
    _clean_dt,
    _clean_int,
    _clean_str,
    _read_objects,
    find_record_files,
    stable_event_id,
    video_to_record,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _video(**overrides) -> dict:
    base = {
        "video_id": "dQw4w9WgXcQ",
        "title": "City Council Meeting 9/23/2024",
        "description": "Regular session",
        "published_at": "2024-09-24T01:30:00Z",
        "jurisdiction_id": "northport_0155200",
        "jurisdiction_name": "Northport",
        "jurisdiction_type": "municipality",
        "state_code": "AL",
        "state": "AL",
        "channel_id": "UC74dczS0B3MhDhUHp2ZGRPA",
        "channel_url": "https://www.youtube.com/channel/UC74dczS0B3MhDhUHp2ZGRPA",
        "duration_minutes": 95,
        "view_count": 1200,
        "like_count": 14,
        "language": "en",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
    base.update(overrides)
    return base


# --- pure helpers ----------------------------------------------------------

def test_clean_str_trims_and_caps():
    assert _clean_str("  hi  ") == "hi"
    assert _clean_str("") is None
    assert _clean_str(None) is None
    assert _clean_str("abcdef", 3) == "abc"


def test_clean_int_coerces():
    assert _clean_int("42") == 42
    assert _clean_int("42.0") == 42
    assert _clean_int(7) == 7
    assert _clean_int("") is None
    assert _clean_int(None) is None
    assert _clean_int("nope") is None


def test_clean_dt_handles_z_and_date_only():
    assert _clean_dt("2024-09-24T01:30:00Z").year == 2024
    assert _clean_dt("2024-09-24").month == 9
    assert _clean_dt(None) is None
    assert _clean_dt("garbage") is None


def test_stable_event_id_is_deterministic_and_in_range():
    a = stable_event_id("abc123")
    b = stable_event_id("abc123")
    assert a == b  # deterministic, unlike Python hash()
    assert a != stable_event_id("xyz789")
    assert 1 <= a <= 2_147_483_647


# --- mapping (no derivation) ------------------------------------------------

def test_video_to_record_lands_raw_no_date_derivation():
    rec = video_to_record(_video(), source_version="northport")
    assert rec["video_id"] == "dQw4w9WgXcQ"
    assert rec["natural_key"] == "dQw4w9WgXcQ"
    assert rec["source"] == "youtube_events"
    assert rec["source_version"] == "northport"
    # Title lands verbatim; event_date is NOT derived here (dbt does that).
    assert rec["title"] == "City Council Meeting 9/23/2024"
    assert "event_date" not in rec
    assert rec["published_at"].year == 2024
    assert rec["datasource"] == "youtube"
    assert rec["event_id"] == stable_event_id("dQw4w9WgXcQ")


def test_video_to_record_defaults_video_url_and_language():
    rec = video_to_record(
        {"video_id": "vid12345678"}, source_version="x"
    )
    assert rec["video_url"] == "https://www.youtube.com/watch?v=vid12345678"
    assert rec["language"] == "en"


def test_video_to_record_extracts_transcript_block():
    rec = video_to_record(
        _video(
            transcript={
                "raw_text": "good evening everyone",
                "segments": [{"text": "good evening", "start": 0.0}],
                "language": "en",
                "is_auto_generated": True,
                "transcript_source": "yt-dlp",
            }
        ),
        source_version="x",
    )
    assert rec["raw_text"] == "good evening everyone"
    assert rec["is_auto_generated"] is True
    assert rec["transcript_source"] == "yt-dlp"


def test_video_to_record_skips_missing_video_id():
    assert video_to_record({"title": "no id"}, source_version="x") is None


# --- row schema -------------------------------------------------------------

def test_row_schema_accepts_minimal_valid_row():
    r = YoutubeEventRow.model_validate(
        video_to_record(_video(), source_version="v")
    )
    assert r.video_id == "dQw4w9WgXcQ"
    assert r.state_code == "AL"
    assert r.has_transcript is False


def test_row_schema_rejects_bad_rows():
    base = video_to_record(_video(), source_version="v")
    # Empty video_id rejected (it's the upsert key).
    with pytest.raises(Exception):
        YoutubeEventRow.model_validate({**base, "video_id": ""})
    # state_code capped at 2 chars.
    with pytest.raises(Exception):
        YoutubeEventRow.model_validate({**base, "state_code": "ALA"})


def test_has_transcript_flag():
    base = video_to_record(_video(transcript={"raw_text": "hello"}), source_version="v")
    assert YoutubeEventRow.model_validate(base).has_transcript is True


# --- file reader ------------------------------------------------------------

def test_read_objects_jsonl(tmp_path):
    p = tmp_path / "dump.jsonl"
    p.write_text(
        json.dumps(_video(video_id="a1")) + "\n"
        + "\n"  # blank line ignored
        + json.dumps(_video(video_id="b2")) + "\n"
    )
    objs = _read_objects(p)
    assert [o["video_id"] for o in objs] == ["a1", "b2"]


def test_read_objects_json_list_and_wrapped(tmp_path):
    p1 = tmp_path / "list.json"
    p1.write_text(json.dumps([_video(video_id="a1"), _video(video_id="b2")]))
    assert len(_read_objects(p1)) == 2

    p2 = tmp_path / "wrapped.json"
    p2.write_text(json.dumps({"videos": [_video(video_id="c3")]}))
    assert _read_objects(p2)[0]["video_id"] == "c3"

    p3 = tmp_path / "single.json"
    p3.write_text(json.dumps(_video(video_id="d4")))
    assert _read_objects(p3)[0]["video_id"] == "d4"


def test_find_record_files_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.youtube.events as ev
    monkeypatch.setattr(ev, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_record_files()


# --- pipeline metadata + extract -------------------------------------------

def test_pipeline_metadata():
    p = YoutubeEventsPipeline()
    assert p.source == "youtube_events"
    assert p.batch_size == 500
    assert p.row_schema is YoutubeEventRow


def test_extract_roundtrip_and_validation(tmp_path):
    p = tmp_path / "northport.jsonl"
    p.write_text(
        json.dumps(_video(video_id="v1")) + "\n"
        + json.dumps({"title": "no video_id"}) + "\n"  # skipped (no video_id)
        + json.dumps(_video(video_id="v3")) + "\n"
    )
    pipe = YoutubeEventsPipeline(path=p)

    async def collect():
        return [r async for r in pipe.extract(_ctx())]

    raws = asyncio.run(collect())
    assert [r["video_id"] for r in raws] == ["v1", "v3"]
    assert raws[0]["source_version"] == "northport"
    # Each extracted row validates cleanly.
    for raw in raws:
        assert pipe.validate(raw) is not None


def test_extract_respects_limit(tmp_path):
    p = tmp_path / "many.jsonl"
    p.write_text("\n".join(json.dumps(_video(video_id=f"v{i}")) for i in range(10)) + "\n")
    pipe = YoutubeEventsPipeline(path=p, limit=3)

    async def collect():
        return [r async for r in pipe.extract(_ctx())]

    assert len(asyncio.run(collect())) == 3

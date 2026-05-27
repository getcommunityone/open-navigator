"""Unit tests for the LocalView events pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import pytest

from ingestion.localview.events import (  # noqa: E402
    LocalviewEventRow,
    LocalviewEventsPipeline,
    find_parquet_files,
    get_state_abbrev,
    infer_jurisdiction_type,
    row_to_event,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_parquet(path, records: list[dict]):
    pd.DataFrame(records).to_parquet(path)
    return path


def test_infer_jurisdiction_type_maps_and_defaults():
    assert infer_jurisdiction_type("County Commission") == "county"
    assert infer_jurisdiction_type("school board") == "school_district"
    # Unknown but present govt strings default to "city".
    assert infer_jurisdiction_type("Some Random Board") == "city"
    # Missing / NaN govt -> "unknown".
    assert infer_jurisdiction_type(None) == "unknown"
    assert infer_jurisdiction_type(float("nan")) == "unknown"


def test_get_state_abbrev_known_and_fallback():
    assert get_state_abbrev("California") == "CA"
    assert get_state_abbrev("Texas") == "TX"
    # Unknown name -> first two chars uppercased.
    assert get_state_abbrev("Freedonia") == "FR"
    assert get_state_abbrev(float("nan")) is None


def test_row_to_event_builds_expected_fields():
    row = pd.Series({
        "meeting_date": "2023-05-10",
        "vid_id": "abc123",
        "state_name": "California",
        "place_name": "Springfield",
        "place_govt": "City Commission",
        "vid_title": "Council Meeting",
        "channel_id": "chan1",
    })
    event = row_to_event(row)
    assert event["datasource_id"] == "abc123"
    assert event["video_url"] == "https://www.youtube.com/watch?v=abc123"
    assert event["state_code"] == "CA"
    assert event["jurisdiction_type"] == "city"
    assert event["datasource"] == "localview"
    assert event["title"] == "Council Meeting"


def test_row_to_event_synthesizes_title_when_missing():
    row = pd.Series({
        "meeting_date": "2023-05-10",
        "vid_id": "xyz",
        "state_name": "Texas",
        "place_name": "Austin",
        "place_govt": "City Council",
        "vid_title": None,
    })
    event = row_to_event(row)
    assert event["title"].startswith("Austin Meeting - ")


def test_row_schema_accepts_minimal_valid_row():
    r = LocalviewEventRow(
        source="localview_events",
        source_version="meetings.2023",
        natural_key="abc123",
        datasource_id="abc123",
        datasource="localview",
        state_code="CA",
    )
    assert r.datasource_id == "abc123"
    assert r.state_code == "CA"
    assert r.vid_views is None


def test_row_schema_rejects_missing_datasource_id():
    # datasource_id is the upsert key and required (min_length=1).
    with pytest.raises(Exception):
        LocalviewEventRow(
            source="localview_events",
            source_version="v",
            natural_key="x",
            datasource_id="",
        )
    # state_code is capped at 2 chars.
    with pytest.raises(Exception):
        LocalviewEventRow(
            source="localview_events",
            source_version="v",
            natural_key="x",
            datasource_id="abc",
            state_code="CAL",
        )


def test_pipeline_metadata():
    p = LocalviewEventsPipeline()
    assert p.source == "localview_events"
    assert p.batch_size == 1000
    assert p.row_schema is LocalviewEventRow


def test_find_parquet_files_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.localview.events as ev
    monkeypatch.setattr(ev, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_parquet_files()


def test_find_parquet_files_filters_by_year(tmp_path, monkeypatch):
    import ingestion.localview.events as ev
    monkeypatch.setattr(ev, "CACHE_DIR", tmp_path)
    (tmp_path / "meetings.2022.parquet").write_text("")
    (tmp_path / "meetings.2023.parquet").write_text("")
    files = find_parquet_files(year=2023)
    assert [f.name for f in files] == ["meetings.2023.parquet"]


def test_extract_roundtrip_and_validation(tmp_path):
    path = tmp_path / "meetings.2023.parquet"
    _write_parquet(path, [
        {  # valid
            "meeting_date": "2023-01-15", "vid_id": "vid1", "state_name": "California",
            "place_name": "Oakland", "place_govt": "County Commission",
            "vid_title": "Board Meeting", "channel_id": "chanA", "channel_title": "Oakland TV",
        },
        {  # missing vid_id -> dropped
            "meeting_date": "2023-02-15", "vid_id": None, "state_name": "Texas",
            "place_name": "Dallas", "place_govt": "City Council",
            "vid_title": "X", "channel_id": "chanB", "channel_title": "Dallas TV",
        },
        {  # missing meeting_date -> dropped
            "meeting_date": None, "vid_id": "vid3", "state_name": "Ohio",
            "place_name": "Columbus", "place_govt": "School Board",
            "vid_title": "Y", "channel_id": "chanC", "channel_title": "Columbus TV",
        },
    ])
    p = LocalviewEventsPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    raw = extracted[0]
    assert raw["source"] == "localview_events"
    assert raw["source_version"] == "meetings.2023"
    assert raw["natural_key"] == "vid1"
    assert raw["datasource_id"] == "vid1"
    assert raw["state_code"] == "CA"
    assert raw["jurisdiction_type"] == "county"
    assert raw["channel_id"] == "chanA"

    # Extracted rows validate cleanly against the schema.
    row = p.validate(raw)
    assert row is not None
    assert row.datasource_id == "vid1"


def test_extract_respects_limit(tmp_path):
    path = tmp_path / "meetings.2024.parquet"
    _write_parquet(path, [
        {
            "meeting_date": "2024-03-01", "vid_id": f"vid{i}", "state_name": "Texas",
            "place_name": f"City{i}", "place_govt": "City Council",
            "vid_title": f"Meeting {i}", "channel_id": f"chan{i}", "channel_title": "TV",
        }
        for i in range(10)
    ])
    p = LocalviewEventsPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

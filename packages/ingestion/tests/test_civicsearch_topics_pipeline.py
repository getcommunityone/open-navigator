"""Unit tests for the CivicSearch topic-decoder LAND pipeline."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from core_lib.pipeline.schemas import PipelineContext
from ingestion.civicsearch.topics import (
    BASE_TABLE,
    SCHOOLS_TABLE,
    CivicSearchTopicRow,
    CivicSearchTopicsPipeline,
    _default_json,
)


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


_TOPICS = [
    {"id": -1, "name": "Local governance", "query_id": "local-governance",
     "keyword_stats": ["seats", "podium"]},
    {"id": 66, "name": "Police matters", "query_id": "police-matters",
     "keyword_stats": ["Police", "officers"]},
]


def test_default_json_picks_portal_subdir():
    assert _default_json(schools=False).as_posix().endswith("cities/topics.json")
    assert _default_json(schools=True).as_posix().endswith("schools/topics.json")


def test_row_schema_keeps_catch_all_negative_id():
    row = CivicSearchTopicRow.model_validate({
        "source": "civicsearch",
        "source_version": "topics.json.v1",
        "natural_key": "-1",
        "topic_id": -1,
        "name": "Local governance",
        "query_id": "local-governance",
        "keyword_stats": ["seats"],
    })
    assert row.topic_id == -1
    assert row.name == "Local governance"


def test_row_schema_rejects_blank_name():
    with pytest.raises(Exception):
        CivicSearchTopicRow.model_validate({
            "source": "civicsearch",
            "source_version": "topics.json.v1",
            "natural_key": "1",
            "topic_id": 1,
            "name": "",
        })


@pytest.mark.asyncio
async def test_extract_maps_fields(tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(_TOPICS), encoding="utf-8")

    pipeline = CivicSearchTopicsPipeline(json_path=path)
    out = [r async for r in pipeline.extract(_ctx())]

    assert len(out) == 2
    first = out[0]
    assert first["source"] == "civicsearch"
    assert first["natural_key"] == "-1"
    assert first["topic_id"] == -1
    assert first["raw_record"]["query_id"] == "local-governance"
    # every extracted dict validates against the row schema
    for raw in out:
        assert pipeline.validate(raw) is not None


@pytest.mark.asyncio
async def test_extract_skips_entry_without_id(tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps([{"name": "no id here"}, *_TOPICS]), encoding="utf-8")

    pipeline = CivicSearchTopicsPipeline(json_path=path)
    out = [r async for r in pipeline.extract(_ctx())]
    assert len(out) == 2  # the id-less entry was skipped


def test_table_selection_targets_schools():
    schools = CivicSearchTopicsPipeline(table=SCHOOLS_TABLE)
    assert schools._table == SCHOOLS_TABLE
    assert schools._json_path.as_posix().endswith("schools/topics.json")
    base = CivicSearchTopicsPipeline()
    assert base._table == BASE_TABLE
    assert base._json_path.as_posix().endswith("cities/topics.json")

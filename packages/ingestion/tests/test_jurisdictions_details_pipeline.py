"""Unit tests for the jurisdictions details pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ingestion.jurisdictions.details import (  # noqa: E402
    JurisdictionsDetailsPipeline,
    JurisdictionsDetailsRow,
    _coerce_json,
    _notna,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_parquet(path: Path, rows: list[dict]) -> Path:
    pd.DataFrame(rows).to_parquet(path)
    return path


def _base_record(**overrides) -> dict:
    rec = {
        "jurisdiction_id": "boston_2507000",
        "jurisdiction_name": "Boston",
        "state_code": "MA",
        "state": "MA",
        "jurisdiction_type": "city",
        "population": 675647,
        "discovery_timestamp": "2026-05-01T00:00:00",
        "website_url": "https://boston.gov",
        "youtube_channel_count": 2,
        "youtube_channels": "['a', 'b']",
        "meeting_platform_count": 1,
        "meeting_platforms": "['zoom']",
        "social_media": "{'twitter': 'cityofboston'}",
        "agenda_portal_count": 1,
        "status": "discovered",
        "in_localview": True,
    }
    rec.update(overrides)
    return rec


def test_coerce_json_handles_string_list_dict_and_missing():
    # Python-literal string round-trips to JSON
    assert _coerce_json("['a', 'b']", "[]") == '["a", "b"]'
    assert _coerce_json("{'k': 'v'}", "{}") == '{"k": "v"}'
    # list / dict are json.dumps'd
    assert _coerce_json(["a", "b"], "[]") == '["a", "b"]'
    assert _coerce_json({"k": "v"}, "{}") == '{"k": "v"}'
    # invalid literal falls back to default
    assert _coerce_json("not-a-literal", "[]") == "[]"
    # missing -> default
    assert _coerce_json(None, "{}") == "{}"
    assert _coerce_json(float("nan"), "[]") == "[]"


def test_notna_scalar_and_collections():
    assert _notna("x") is True
    assert _notna(0) is True
    assert _notna(None) is False
    assert _notna(float("nan")) is False
    # collections are always present (avoids ambiguous truth-value error)
    assert _notna(["a"]) is True
    assert _notna({}) is True


def test_row_schema_accepts_full_record():
    r = JurisdictionsDetailsRow(
        source="jurisdictions_details",
        source_version="jurisdictions_details",
        natural_key="boston_2507000",
        jurisdiction_id="boston_2507000",
        jurisdiction_name="Boston",
        state_code="MA",
        state="MA",
        jurisdiction_type="city",
        population=675647,
        discovery_timestamp=pd.Timestamp("2026-05-01"),
        website_url="https://boston.gov",
        youtube_channel_count=2,
        youtube_channels='["a", "b"]',
        meeting_platform_count=1,
        meeting_platforms='["zoom"]',
        social_media='{"twitter": "cityofboston"}',
        agenda_portal_count=1,
        discovery_status="discovered",
        in_localview=True,
    )
    assert r.jurisdiction_id == "boston_2507000"
    assert r.in_localview is True


def test_row_schema_rejects_empty_jurisdiction_id():
    with pytest.raises(Exception):
        JurisdictionsDetailsRow(
            source="jurisdictions_details",
            source_version="v",
            natural_key="x",
            jurisdiction_id="",
            jurisdiction_name="X",
            discovery_timestamp=pd.Timestamp("2026-05-01"),
        )


def test_row_schema_rejects_oversized_state():
    with pytest.raises(Exception):
        JurisdictionsDetailsRow(
            source="jurisdictions_details",
            source_version="v",
            natural_key="x",
            jurisdiction_id="x_1",
            jurisdiction_name="X",
            state="MAS",
            discovery_timestamp=pd.Timestamp("2026-05-01"),
        )


def test_pipeline_metadata():
    p = JurisdictionsDetailsPipeline()
    assert p.source == "jurisdictions_details"
    assert p.batch_size == 1000
    assert p.row_schema is JurisdictionsDetailsRow


def test_extract_raises_when_default_file_missing(tmp_path, monkeypatch):
    import ingestion.jurisdictions.details as dp

    monkeypatch.setattr(dp, "DETAILS_FILE", tmp_path / "does_not_exist.parquet")
    p = JurisdictionsDetailsPipeline()

    async def collect():
        return [r async for r in p.extract(_ctx())]

    with pytest.raises(FileNotFoundError):
        asyncio.run(collect())


def test_extract_roundtrip_validates_and_coerces_json(tmp_path):
    path = _write_parquet(
        tmp_path / "jurisdictions_details.parquet",
        [
            _base_record(),
            _base_record(
                jurisdiction_id="austin_4805000",
                jurisdiction_name="Austin",
                state_code="TX",
                state="TX",
                website_url=None,
                youtube_channels="not-a-literal",  # -> default "[]"
                status=None,  # -> "unknown"
                in_localview=False,
            ),
        ],
    )
    p = JurisdictionsDetailsPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2

    first = extracted[0]
    assert first["jurisdiction_id"] == "boston_2507000"
    assert first["natural_key"] == "boston_2507000"
    assert first["youtube_channels"] == '["a", "b"]'
    assert first["social_media"] == '{"twitter": "cityofboston"}'

    second = extracted[1]
    assert second["website_url"] is None
    assert second["youtube_channels"] == "[]"  # invalid literal -> default
    assert second["discovery_status"] == "unknown"

    # every extracted row validates cleanly through the pydantic schema
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_limit_caps_extracted_rows(tmp_path):
    records = [
        _base_record(jurisdiction_id=f"x_{i}", jurisdiction_name=f"City{i}")
        for i in range(10)
    ]
    path = _write_parquet(tmp_path / "jurisdictions_details.parquet", records)
    p = JurisdictionsDetailsPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

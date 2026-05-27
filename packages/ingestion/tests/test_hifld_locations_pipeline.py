"""Unit tests for the HIFLD locations pipeline refactor (slimmed: RAW landing).

The org_type classification and FIELD_MAP column normalization moved to dbt
(stg_hifld__location); this loader now only lands the raw HIFLD record into
bronze.bronze_locations, so the tests assert the raw shape.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import pytest


from ingestion.hifld.locations import (  # noqa: E402
    HifldLocationsPipeline,
    LocationRow,
    _jsonable,
    _raw_source_id,
    _truncate,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


# -- pure helpers ----------------------------------------------------------

def test_truncate_handles_none_nan_and_not_available():
    assert _truncate(None, 10) is None
    assert _truncate(float("nan"), 10) is None
    assert _truncate("NOT AVAILABLE", 50) is None
    assert _truncate("hello", 3) == "hel"
    assert _truncate("hello", 100) == "hello"
    assert _truncate("", 10) is None


def test_jsonable_coerces_cells():
    assert _jsonable(None) is None
    assert _jsonable(float("nan")) is None
    assert _jsonable("x") == "x"
    assert _jsonable(3) == 3
    assert _jsonable(pd.Timestamp("2020-01-01")) == "2020-01-01 00:00:00"


def test_raw_source_id_picks_first_candidate_case_insensitive():
    assert _raw_source_id({"OBJECTID": 101}) == "101"
    assert _raw_source_id({"fid": 7}) == "7"  # case-insensitive
    assert _raw_source_id({"FACILITY_ID": "abc"}) == "abc"
    # FID wins over OBJECTID (candidate order)
    assert _raw_source_id({"OBJECTID": 2, "FID": 9}) == "9"
    assert _raw_source_id({"NAME": "x"}) is None


# -- pipeline shape --------------------------------------------------------

def test_location_row_requires_source_dataset_and_raw_record():
    r = LocationRow(
        source="hifld", source_version="Hospitals", natural_key="Hospitals:42",
        source_id="42", source_dataset="Hospitals",
        raw_record={"FACNAME": "General Hospital"},
    )
    assert r.source_dataset == "Hospitals"
    assert r.raw_record == {"FACNAME": "General Hospital"}

    # empty raw_record is rejected
    with pytest.raises(Exception):
        LocationRow(
            source="hifld", source_version="x", natural_key="x:1",
            source_dataset="x", raw_record={},
        )

    # missing source_dataset is rejected
    with pytest.raises(Exception):
        LocationRow(
            source="hifld", source_version="x", natural_key="x:1",
            raw_record={"NAME": "y"},
        )


def test_pipeline_metadata():
    p = HifldLocationsPipeline()
    assert p.source == "hifld"
    assert p.batch_size == 1000
    assert p.row_schema is LocationRow


def test_extract_lands_raw_records(tmp_path):
    df = pd.DataFrame({
        "FACNAME": ["St. Mary Hospital", "City Clinic"],
        "ADDRESS": ["1 Main St", "2 Elm St"],
        "CITY": ["Boston", "Cambridge"],
        "STATE": ["MA", "MA"],
        "ZIP": ["02101", "02139"],
        "LAT": [42.36, 42.37],
        "LON": [-71.06, -71.10],
        "OBJECTID": [101, 102],
        "STATUS": ["OPEN", "OPEN"],
    })
    parquet = tmp_path / "Hospitals.parquet"
    df.to_parquet(parquet)

    p = HifldLocationsPipeline(parquet_file=parquet)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    first = extracted[0]
    # Raw, un-normalized: original column names preserved verbatim in raw_record.
    assert first["source_dataset"] == "Hospitals"
    assert first["source_id"] == "101"
    assert first["natural_key"] == "Hospitals:101"
    assert first["raw_record"]["FACNAME"] == "St. Mary Hospital"
    assert first["raw_record"]["STATE"] == "MA"
    assert first["raw_record"]["STATUS"] == "OPEN"
    # No derived columns leaked into the raw landing.
    assert "organization_type" not in first
    assert "name" not in first
    # All extracted rows must validate.
    for raw in extracted:
        row_obj = p.validate(raw)
        assert row_obj is not None


def test_discover_files_raises_when_missing(tmp_path):
    p = HifldLocationsPipeline(parquet_file=tmp_path / "missing.parquet")
    with pytest.raises(FileNotFoundError):
        p._discover_files()

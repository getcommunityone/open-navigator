"""Unit tests for the HIFLD locations pipeline refactor."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest


from ingestion.hifld.locations import (  # noqa: E402
    FIELD_MAP,
    HifldLocationsPipeline,
    LocationRow,
    _opt_float,
    _truncate,
    map_organization_type,
    normalize_field_names,
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


def test_opt_float_handles_invalid_inputs():
    assert _opt_float("3.14") == 3.14
    assert _opt_float(2) == 2.0
    assert _opt_float(None) is None
    assert _opt_float(float("nan")) is None
    assert _opt_float("garbage") is None


def test_map_organization_type_dispatches_on_dataset_name():
    assert map_organization_type("Hospitals.parquet", {}) == "hospital"
    assert map_organization_type("Schools", {}) == "school"
    assert map_organization_type("Worship", {}) == "place_of_worship"
    assert map_organization_type("Fire_Stations", {}) == "fire_station"
    assert map_organization_type("Government", {}) == "government_building"
    assert map_organization_type("Unknown", {}) == "other"


def test_map_organization_type_uses_row_TYPE_for_law_enforcement():
    assert map_organization_type("Law_Enforcement", {"TYPE": "State Police"}) == "state_police"
    assert map_organization_type("Law_Enforcement", {}) == "law_enforcement"


def test_normalize_field_names_renames_known_columns():
    df = pd.DataFrame({"FACNAME": ["x"], "ZIP_CODE": ["12345"], "LAT": [34.0], "LON": [-118.0], "OTHER": [1]})
    n = normalize_field_names(df)
    assert "name" in n.columns
    assert "zip" in n.columns
    assert "latitude" in n.columns
    assert "longitude" in n.columns
    assert "OTHER" in n.columns  # unknown column unchanged


def test_field_map_covers_common_variants():
    for canonical in ("name", "address", "city", "state", "zip", "county",
                      "latitude", "longitude", "telephone", "website", "source_id"):
        assert canonical in FIELD_MAP.values()


# -- pipeline shape --------------------------------------------------------

def test_location_row_requires_organization_type_and_source_dataset():
    r = LocationRow(
        source="hifld", source_version="Hospitals", natural_key="Hospitals:42",
        source_id="42", name="General Hospital", organization_type="hospital",
        source_dataset="Hospitals",
    )
    assert r.organization_type == "hospital"

    with pytest.raises(Exception):
        LocationRow(
            source="hifld", source_version="x", natural_key="x:1",
            organization_type="", source_dataset="x",
        )


def test_pipeline_metadata():
    p = HifldLocationsPipeline()
    assert p.source == "hifld"
    assert p.batch_size == 1000
    assert p.row_schema is LocationRow


def test_extract_reads_parquet_and_yields_validated_rows(tmp_path):
    df = pd.DataFrame({
        "FACNAME": ["St. Mary Hospital", "City Clinic"],
        "ADDRESS": ["1 Main St", "2 Elm St"],
        "CITY": ["Boston", "Cambridge"],
        "STATE": ["MA", "MA"],
        "ZIP": ["02101", "02139"],
        "LAT": [42.36, 42.37],
        "LON": [-71.06, -71.10],
        "OBJECTID": [101, 102],
        # extra fields not in STANDARD_FIELDS — should land in additional_info
        "STATUS": ["OPEN", "OPEN"],
    })
    parquet = tmp_path / "Hospitals.parquet"
    df.to_parquet(parquet)

    p = HifldLocationsPipeline(parquet_file=parquet, org_type_override="hospital")

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    first = extracted[0]
    assert first["name"] == "St. Mary Hospital"
    assert first["organization_type"] == "hospital"
    assert first["state"] == "MA"
    assert first["source_id"] == "101"
    assert first["additional_info"] == {"STATUS": "OPEN"}
    # All extracted rows must validate
    for raw in extracted:
        row_obj = p.validate(raw)
        assert row_obj is not None


def test_discover_files_raises_when_missing(tmp_path):
    p = HifldLocationsPipeline(parquet_file=tmp_path / "missing.parquet")
    with pytest.raises(FileNotFoundError):
        p._discover_files()

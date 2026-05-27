"""Unit tests for the Census county-mappings pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import pytest


from ingestion.census.county_mappings import (  # noqa: E402
    CensusCountyMappingsPipeline,
    CountyMappingRow,
    find_input_file,
    process_zcta_to_county,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_input(path, with_population=True):
    """Write a synthetic pipe-delimited ZCTA-to-county relationship file."""
    header = ["GEOID_ZCTA5_20", "GEOID_COUNTY_20", "NAMELSAD_COUNTY_20"]
    rows = [
        # ZCTA 02101 overlaps two counties; Suffolk has the higher population.
        ["02101", "25025", "Suffolk County", "900"],
        ["02101", "25021", "Norfolk County", "100"],
        # ZCTA 10001 single county.
        ["10001", "36061", "New York County", "500"],
    ]
    if with_population:
        header.append("POPPT")
    else:
        rows = [r[:3] for r in rows]
    lines = ["|".join(header)]
    for r in rows:
        lines.append("|".join(r))
    path.write_text("\n".join(lines) + "\n")


def test_process_zcta_to_county_picks_primary_county():
    df = pd.DataFrame(
        {
            "GEOID_ZCTA5_20": ["02101", "02101", "10001"],
            "GEOID_COUNTY_20": ["25025", "25021", "36061"],
            "NAMELSAD_COUNTY_20": ["Suffolk County", "Norfolk County", "New York County"],
            "POPPT": ["900", "100", "500"],
        }
    )
    result = process_zcta_to_county(df)
    assert result is not None
    by_zcta = {r["zcta"]: r for r in result.to_dict("records")}
    # Suffolk (900/1000) wins over Norfolk for 02101.
    assert by_zcta["02101"]["county_geoid"] == "25025"
    assert by_zcta["02101"]["population_pct"] == 90.0
    assert by_zcta["02101"]["state_fips"] == "25"
    assert by_zcta["10001"]["county_geoid"] == "36061"
    assert by_zcta["10001"]["population_pct"] == 100.0


def test_process_zcta_to_county_without_population():
    df = pd.DataFrame(
        {
            "GEOID_ZCTA5_20": ["02101", "10001"],
            "GEOID_COUNTY_20": ["25025", "36061"],
            "NAMELSAD_COUNTY_20": ["Suffolk County", "New York County"],
        }
    )
    result = process_zcta_to_county(df)
    assert result is not None
    assert "population" not in result.columns
    assert set(result["population_pct"]) == {100.0}


def test_process_zcta_to_county_missing_required_returns_none():
    df = pd.DataFrame({"GEOID_ZCTA5_20": ["02101"], "POPPT": ["1"]})
    assert process_zcta_to_county(df) is None


def test_county_mapping_row_schema_accepts_valid():
    r = CountyMappingRow(
        source="census_county_mappings",
        source_version="2020",
        natural_key="zcta:02101",
        zcta="02101",
        county_geoid="25025",
        county_name="Suffolk County",
        state_fips="25",
        population=900.0,
        population_pct=90.0,
    )
    assert r.zcta == "02101"
    assert r.county_geoid == "25025"
    assert r.population_pct == 90.0


def test_county_mapping_row_schema_rejects_bad_lengths():
    # state_fips must be max 2 chars
    with pytest.raises(Exception):
        CountyMappingRow(
            source="census_county_mappings",
            source_version="2020",
            natural_key="zcta:02101",
            zcta="02101",
            county_geoid="25025",
            state_fips="250",
        )
    # zcta is required (min_length=1)
    with pytest.raises(Exception):
        CountyMappingRow(
            source="census_county_mappings",
            source_version="2020",
            natural_key="zcta:",
            zcta="",
            county_geoid="25025",
        )
    # extra field forbidden by RawRow config
    with pytest.raises(Exception):
        CountyMappingRow(
            source="census_county_mappings",
            source_version="2020",
            natural_key="zcta:02101",
            zcta="02101",
            county_geoid="25025",
            bogus="x",
        )


def test_pipeline_metadata():
    p = CensusCountyMappingsPipeline()
    assert p.source == "census_county_mappings"
    assert p.batch_size == 1000
    assert p.row_schema is CountyMappingRow


def test_find_input_file_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.census.county_mappings as cm
    monkeypatch.setattr(cm, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_input_file()


def test_extract_yields_validated_rows(tmp_path):
    input_path = tmp_path / "zcta_to_county.txt"
    _write_input(input_path, with_population=True)
    p = CensusCountyMappingsPipeline(path=input_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    by_zcta = {r["zcta"]: r for r in extracted}
    assert set(by_zcta) == {"02101", "10001"}
    assert by_zcta["02101"]["county_geoid"] == "25025"
    assert by_zcta["02101"]["state_fips"] == "25"
    assert by_zcta["02101"]["natural_key"] == "zcta:02101"

    # All extracted rows validate cleanly.
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_limit_caps_rows(tmp_path):
    input_path = tmp_path / "zcta_to_county.txt"
    _write_input(input_path, with_population=True)
    p = CensusCountyMappingsPipeline(path=input_path, limit=1)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1

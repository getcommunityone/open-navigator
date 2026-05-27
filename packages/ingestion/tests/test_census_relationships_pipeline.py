"""Unit tests for the Census relationships pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from ingestion.census.relationships import (  # noqa: E402
    CensusRelationshipsPipeline,
    RelationshipRow,
    safe_int,
    safe_str,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_safe_str_trims_and_handles_nan():
    assert safe_str("  02101  ") == "02101"
    assert safe_str("") == ""
    assert safe_str("   ") == ""
    assert safe_str(None) == ""
    assert safe_str("nan") == ""
    assert safe_str("NaN") == ""


def test_safe_int_parses_and_tolerates_garbage():
    assert safe_int("123") == 123
    assert safe_int("123.0") == 123
    assert safe_int("") is None
    assert safe_int(None) is None
    assert safe_int("abc") is None


def test_relationship_row_schema_accepts_valid():
    r = RelationshipRow(
        source="census_relationships",
        source_version="2020",
        natural_key="zcta_county:02101:25025",
        relationship_type="zcta_county",
        zcta="02101",
        geoid="25025",
        name="Suffolk County",
        state_fips="25",
        arealand_part=1000,
        areawater_part=50,
        source_file="Census 2020 ZCTA-County Relationship File",
    )
    assert r.zcta == "02101"
    assert r.geoid == "25025"
    assert r.state_fips == "25"
    assert r.arealand_part == 1000


def test_relationship_row_schema_rejects_missing_zcta():
    with pytest.raises(Exception):
        RelationshipRow(
            source="census_relationships",
            source_version="2020",
            natural_key="x",
            relationship_type="zcta_county",
            zcta="",
            geoid="25025",
        )


def test_relationship_row_schema_rejects_state_fips_too_long():
    with pytest.raises(Exception):
        RelationshipRow(
            source="census_relationships",
            source_version="2020",
            natural_key="x",
            relationship_type="zcta_county",
            zcta="02101",
            geoid="25025",
            state_fips="250",  # > 2 chars
        )


def test_relationship_row_schema_forbids_extra_fields():
    with pytest.raises(Exception):
        RelationshipRow(
            source="census_relationships",
            source_version="2020",
            natural_key="x",
            relationship_type="zcta_county",
            zcta="02101",
            geoid="25025",
            unexpected="boom",
        )


def test_pipeline_metadata():
    p = CensusRelationshipsPipeline()
    assert p.source == "census_relationships"
    assert p.batch_size == 5000
    assert p.row_schema is RelationshipRow


def test_extract_raises_when_cache_file_missing(tmp_path, monkeypatch):
    import ingestion.census.relationships as rp
    monkeypatch.setattr(rp, "CACHE_DIR", tmp_path)
    p = CensusRelationshipsPipeline(types=["zcta_county"])

    async def collect():
        return [r async for r in p.extract(_ctx())]

    with pytest.raises(FileNotFoundError):
        asyncio.run(collect())


def test_extract_yields_validated_county_rows(tmp_path):
    input_file = tmp_path / "zcta_county.txt"
    input_file.write_text(
        "GEOID_ZCTA5_20|GEOID_COUNTY_20|NAMELSAD_COUNTY_20|AREALAND_PART|AREAWATER_PART\n"
        "02101|25025|Suffolk County|123456|789\n"
        "||X County|1|2\n"  # missing zcta -> dropped
        "10001|36061|New York County|999.0|\n"  # float area, empty water
    )
    p = CensusRelationshipsPipeline(path=input_file, types=["zcta_county"])

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2

    first = extracted[0]
    assert first["relationship_type"] == "zcta_county"
    assert first["zcta"] == "02101"
    assert first["geoid"] == "25025"
    assert first["name"] == "Suffolk County"
    assert first["state_fips"] == "25"
    assert first["arealand_part"] == 123456
    assert first["areawater_part"] == 789
    assert first["natural_key"] == "zcta_county:02101:25025"

    second = extracted[1]
    assert second["zcta"] == "10001"
    assert second["arealand_part"] == 999
    assert second["areawater_part"] is None
    assert second["state_fips"] == "36"

    # All extracted rows validate cleanly and route to the county upsert.
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None
        assert row.relationship_type == "zcta_county"


def test_extract_limit_caps_rows(tmp_path):
    input_file = tmp_path / "zcta_place.txt"
    lines = ["GEOID_ZCTA5_20|GEOID_PLACE_20|NAMELSAD_PLACE_20|AREALAND_PART|AREAWATER_PART"]
    for i in range(10):
        lines.append(f"100{i:02d}|36{i:05d}|Place {i}|{i}|{i}")
    input_file.write_text("\n".join(lines) + "\n")

    p = CensusRelationshipsPipeline(path=input_file, types=["zcta_place"], limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3
    assert all(r["relationship_type"] == "zcta_place" for r in extracted)

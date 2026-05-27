"""Unit tests for the census place crosswalks pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


from ingestion.census.place_crosswalks import (  # noqa: E402
    CensusPlaceCrosswalksPipeline,
    PlaceZctaRow,
    _safe_int,
    build_place_zcta,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


_HEADER = (
    "GEOID_ZCTA5_20|NAMELSAD_ZCTA5_20|GEOID_PLACE_20|NAMELSAD_PLACE_20|"
    "AREALAND_PART|AREAWATER_PART"
)


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_rel_file(tmp_path, rows: list[str]):
    p = tmp_path / "zcta_place.txt"
    p.write_text("\n".join([_HEADER, *rows]) + "\n")
    return p


def test_safe_int_parses_and_handles_bad_input():
    assert _safe_int("123") == 123
    assert _safe_int("123.7") == 123
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("abc") is None


def test_place_zcta_row_schema_accepts_valid():
    r = PlaceZctaRow(
        source="census_place_crosswalks",
        source_version="zcta_place",
        natural_key="2507000:02101",
        place_geoid="2507000",
        place_name="Boston city",
        zcta="02101",
        state_fips="25",
        arealand_part=1000,
        areawater_part=0,
        is_primary=True,
        place_source="Census 2020 ZCTA-Place Relationship File",
    )
    assert r.place_geoid == "2507000"
    assert r.zcta == "02101"
    assert r.is_primary is True


def test_place_zcta_row_schema_rejects_overlong_zcta():
    # zcta is VARCHAR(10) -> max_length=10
    with pytest.raises(Exception):
        PlaceZctaRow(
            source="census_place_crosswalks",
            source_version="v",
            natural_key="x",
            place_geoid="2507000",
            zcta="0123456789X",  # 11 chars
            is_primary=False,
        )


def test_place_zcta_row_requires_place_geoid():
    with pytest.raises(Exception):
        PlaceZctaRow(
            source="census_place_crosswalks",
            source_version="v",
            natural_key="x",
            place_geoid="",
            zcta="02101",
            is_primary=False,
        )


def test_pipeline_metadata():
    p = CensusPlaceCrosswalksPipeline()
    assert p.source == "census_place_crosswalks"
    assert p.batch_size == 1000
    assert p.row_schema is PlaceZctaRow


def test_build_place_zcta_raises_when_cache_missing(tmp_path, monkeypatch):
    import ingestion.census.place_crosswalks as pc
    monkeypatch.setattr(pc, "RELATIONSHIPS_CACHE", tmp_path)
    # No zcta_place.txt present -> returns an empty DataFrame (logged error).
    df = build_place_zcta()
    assert df.empty


def test_extract_roundtrip_and_primary_marking(tmp_path):
    # Two places. Place 2507000 spans two ZCTAs (the larger arealand wins
    # primary); place 0644000 has a single ZCTA (always primary).
    src = _write_rel_file(
        tmp_path,
        [
            "02101|ZCTA5 02101|2507000|Boston city|500|0",
            "02199|ZCTA5 02199|2507000|Boston city|1500|10",
            "90001|ZCTA5 90001|0644000|Los Angeles city|9000|0",
        ],
    )
    p = CensusPlaceCrosswalksPipeline(path=src)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

    # All envelopes validate cleanly against the row schema.
    rows = [p.validate(raw) for raw in extracted]
    assert all(r is not None for r in rows)

    by_key = {raw["natural_key"]: raw for raw in extracted}
    assert by_key["2507000:02101"]["is_primary"] is False
    assert by_key["2507000:02199"]["is_primary"] is True  # largest arealand
    assert by_key["0644000:90001"]["is_primary"] is True
    # state_fips derived from zero-padded place_geoid prefix
    assert by_key["2507000:02101"]["state_fips"] == "25"
    assert by_key["0644000:90001"]["state_fips"] == "06"
    # envelope carries source/source_version metadata
    assert by_key["2507000:02101"]["source"] == "census_place_crosswalks"
    assert by_key["2507000:02101"]["source_version"] == "zcta_place"


def test_extract_limit_caps_distinct_places(tmp_path):
    src = _write_rel_file(
        tmp_path,
        [
            "02101|ZCTA5 02101|2507000|Boston city|500|0",
            "02199|ZCTA5 02199|2507000|Boston city|1500|0",
            "90001|ZCTA5 90001|0644000|Los Angeles city|9000|0",
            "60601|ZCTA5 60601|1714000|Chicago city|7000|0",
        ],
    )
    # limit=1 keeps only the first distinct place (2507000), both its rows.
    p = CensusPlaceCrosswalksPipeline(path=src, limit=1)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert {raw["place_geoid"] for raw in extracted} == {"2507000"}
    assert len(extracted) == 2

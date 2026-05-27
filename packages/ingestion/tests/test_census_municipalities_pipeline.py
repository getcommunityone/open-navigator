"""Unit tests for the Census municipalities pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


from ingestion.census.municipalities import (  # noqa: E402
    LSAD_TYPE_MAP,
    CensusMunicipalitiesPipeline,
    MunicipalityRow,
    _parse_float,
    find_latest_cache_file,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


_GAZ_HEADER = (
    "USPS,GEOID,ANSICODE,NAME,LSAD,FUNCSTAT,ALAND,AWATER,"
    "ALAND_SQMI,AWATER_SQMI,INTPTLAT,INTPTLONG"
)


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_parse_float_handles_bad_values():
    assert _parse_float("12.5") == 12.5
    assert _parse_float(0) == 0.0
    assert _parse_float("") is None
    assert _parse_float("abc") is None
    assert _parse_float(None) is None


def test_lsad_type_map_known_codes():
    assert LSAD_TYPE_MAP["25"] == "city"
    assert LSAD_TYPE_MAP["43"] == "town"
    assert LSAD_TYPE_MAP["57"] == "cdp"


def test_municipality_row_schema_accepts_valid():
    r = MunicipalityRow(
        source="census_municipalities",
        source_version="municipalities_20240101",
        natural_key="MA:city:Boston",
        name="Boston",
        jurisdiction_type="city",
        state_code="MA",
        geoid="2507000",
        ansicode="00619463",
        area_sq_miles=48.34,
        latitude=42.3,
        longitude=-71.0,
    )
    assert r.name == "Boston"
    assert r.jurisdiction_type == "city"
    assert r.ansicode == "00619463"
    assert r.latitude == 42.3


def test_municipality_row_allows_nullable_fields():
    r = MunicipalityRow(
        source="census_municipalities",
        source_version="v",
        natural_key="XX:place:Nowhere",
        name="Nowhere",
        jurisdiction_type="place",
        state_code="XX",
        geoid="9999999",
    )
    assert r.ansicode is None
    assert r.area_sq_miles is None
    assert r.latitude is None
    assert r.longitude is None


def test_municipality_row_rejects_empty_name():
    with pytest.raises(Exception):
        MunicipalityRow(
            source="census_municipalities",
            source_version="v",
            natural_key="MA:city:",
            name="",
            jurisdiction_type="city",
            state_code="MA",
            geoid="2507000",
        )


def test_municipality_row_forbids_extra_fields():
    with pytest.raises(Exception):
        MunicipalityRow(
            source="census_municipalities",
            source_version="v",
            natural_key="MA:city:Boston",
            name="Boston",
            jurisdiction_type="city",
            state_code="MA",
            geoid="2507000",
            population=600000,  # not a field on the row schema
        )


def test_pipeline_metadata():
    p = CensusMunicipalitiesPipeline()
    assert p.source == "census_municipalities"
    assert p.batch_size == 1000
    assert p.row_schema is MunicipalityRow


def test_find_latest_cache_file_raises_when_no_files(tmp_path, monkeypatch):
    import ingestion.census.municipalities as mp
    monkeypatch.setattr(mp, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_latest_cache_file()


def test_find_latest_cache_file_returns_most_recent(tmp_path, monkeypatch):
    import ingestion.census.municipalities as mp
    monkeypatch.setattr(mp, "CACHE_DIR", tmp_path)
    (tmp_path / "municipalities_20240101.csv").write_text("")
    (tmp_path / "municipalities_20260101.csv").write_text("")
    (tmp_path / "municipalities_20250101.csv").write_text("")
    latest = find_latest_cache_file()
    assert latest.name == "municipalities_20260101.csv"


def test_extract_yields_validated_rows(tmp_path):
    csv_path = tmp_path / "municipalities_20240101.csv"
    csv_path.write_text(
        _GAZ_HEADER + "\n"
        # active city with full data
        "MA,2507000,00619463,Boston,25,A,232471675,56862167,48.34,21.95,42.3,-71.0\n"
        # inactive place -> dropped (FUNCSTAT != A)
        "MA,2599999,00000000,Ghosttown,25,I,0,0,0,0,0,0\n"
        # active place with unknown LSAD -> type 'place', blank ansicode -> None,
        # bad coords -> lat/long both dropped
        "TX,4805000,,Weirdville,99,A,100,0,1.0,0,abc,xyz\n"
    )
    p = CensusMunicipalitiesPipeline(path=csv_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2

    boston = extracted[0]
    assert boston["name"] == "Boston"
    assert boston["jurisdiction_type"] == "city"
    assert boston["state_code"] == "MA"
    assert boston["geoid"] == "2507000"
    assert boston["ansicode"] == "00619463"
    assert boston["area_sq_miles"] == 48.34
    assert boston["latitude"] == 42.3
    assert boston["natural_key"] == "MA:city:Boston"

    weird = extracted[1]
    assert weird["jurisdiction_type"] == "place"  # unknown LSAD fallback
    assert weird["ansicode"] is None  # blank -> None
    assert weird["latitude"] is None and weird["longitude"] is None  # bad coords

    # All extracted rows validate cleanly through the schema
    for raw in extracted:
        assert p.validate(raw) is not None


def test_limit_caps_iterated_rows(tmp_path):
    csv_path = tmp_path / "municipalities_test.csv"
    rows = [_GAZ_HEADER]
    for i in range(10):
        rows.append(
            f"MA,250{i:04d},0061946{i},Place{i},25,A,1,0,1.0,0,42.{i},-71.{i}"
        )
    csv_path.write_text("\n".join(rows) + "\n")

    # limit applies to the raw enumerate index (matches legacy behavior),
    # so only the first 3 input rows are considered.
    p = CensusMunicipalitiesPipeline(path=csv_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

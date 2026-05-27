"""Unit tests for the Census counties pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


from ingestion.census.counties import (  # noqa: E402
    CensusCountiesPipeline,
    CountyRow,
    _parse_float,
    download_gazetteer_file,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_parse_float_handles_numbers_and_bad_input():
    assert _parse_float("123.45") == 123.45
    assert _parse_float("0") == 0.0
    # Empty / None default to 0.0 (mirrors float(row.get(..., 0)))
    assert _parse_float("") == 0.0
    assert _parse_float(None) == 0.0
    # Non-numeric input is swallowed
    assert _parse_float("abc") is None


def test_county_row_schema_accepts_valid():
    r = CountyRow(
        source="census_counties",
        source_version="2024",
        natural_key="county:06037",
        name="Los Angeles County",
        type="county",
        state_code="CA",
        geoid="06037",
        fips_code="06037",
        area_sq_miles=4057.88,
        latitude=34.3,
        longitude=-118.2,
    )
    assert r.name == "Los Angeles County"
    assert r.geoid == "06037"
    assert r.fips_code == "06037"
    assert r.area_sq_miles == 4057.88


def test_county_row_allows_null_optional_fields():
    r = CountyRow(
        source="census_counties",
        source_version="2024",
        natural_key="county:99999",
        name="Nowhere County",
        type="county",
        state_code="ZZ",
        geoid="99999",
        fips_code="99999",
    )
    assert r.area_sq_miles is None
    assert r.latitude is None
    assert r.longitude is None


def test_county_row_requires_name():
    with pytest.raises(Exception):
        CountyRow(
            source="census_counties",
            source_version="2024",
            natural_key="county:06037",
            name="",
            type="county",
            state_code="CA",
            geoid="06037",
            fips_code="06037",
        )


def test_county_row_rejects_extra_fields():
    # RawRow uses extra="forbid"
    with pytest.raises(Exception):
        CountyRow(
            source="census_counties",
            source_version="2024",
            natural_key="county:06037",
            name="Los Angeles County",
            type="county",
            state_code="CA",
            geoid="06037",
            fips_code="06037",
            bogus_field="nope",
        )


def test_pipeline_metadata():
    p = CensusCountiesPipeline()
    assert p.source == "census_counties"
    assert p.batch_size == 1000
    assert p.row_schema is CountyRow


def test_download_returns_cached_file_when_present(tmp_path, monkeypatch):
    import ingestion.census.counties as cc
    monkeypatch.setattr(cc, "CACHE_DIR", tmp_path)
    cache_file = tmp_path / f"counties_{datetime.now().strftime('%Y%m%d')}.csv"
    cache_file.write_text("USPS,GEOID,NAME\n")
    assert download_gazetteer_file() == cache_file


def test_download_raises_when_no_cache_and_network_fails(tmp_path, monkeypatch):
    import ingestion.census.counties as cc
    monkeypatch.setattr(cc, "CACHE_DIR", tmp_path)

    class _Boom(cc.requests.exceptions.RequestException):
        pass

    def _fail(*args, **kwargs):
        raise _Boom("offline")

    monkeypatch.setattr(cc.requests, "get", _fail)
    with pytest.raises(cc.requests.exceptions.RequestException):
        download_gazetteer_file(force_download=True)


def test_extract_yields_validated_rows(tmp_path):
    csv_path = tmp_path / "counties_20240101.csv"
    csv_path.write_text(
        "USPS,GEOID,NAME,ALAND_SQMI,INTPTLAT,INTPTLONG\n"
        "CA,06037,Los Angeles County,4057.88,34.3,-118.2\n"
        "TX,48201,Harris County,1703.48,29.8,-95.4\n"
    )
    p = CensusCountiesPipeline(path=csv_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["name"] == "Los Angeles County"
    assert extracted[0]["geoid"] == "06037"
    assert extracted[0]["fips_code"] == "06037"
    assert extracted[0]["type"] == "county"
    assert extracted[0]["state_code"] == "CA"
    assert extracted[0]["area_sq_miles"] == 4057.88
    assert extracted[0]["latitude"] == 34.3
    assert extracted[0]["natural_key"] == "county:06037"

    # All extracted rows validate cleanly
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_limit_caps_rows(tmp_path):
    csv_path = tmp_path / "counties_20240101.csv"
    rows = ["USPS,GEOID,NAME,ALAND_SQMI,INTPTLAT,INTPTLONG"]
    for i in range(10):
        rows.append(f"CA,060{i:02d},County{i},100.0,34.0,-118.0")
    csv_path.write_text("\n".join(rows) + "\n")

    p = CensusCountiesPipeline(path=csv_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

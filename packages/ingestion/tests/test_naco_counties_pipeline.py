"""Unit tests for the NACo counties pipeline refactor."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


from ingestion.naco.counties import (  # noqa: E402
    CountyRow,
    NacoCountiesPipeline,
    _int,
    _float,
    _str,
    find_cache_files,
    natural_key_for,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_pure_helpers_str_int_float():
    assert _str("  hi  ") == "hi"
    assert _str("") is None
    assert _str(None) is None
    assert _str("abcdef", 3) == "abc"
    assert _int("42") == 42
    assert _int("nope") is None
    assert _float("3.5") == 3.5
    assert _float(None) is None


def test_natural_key_for_basic_and_null():
    # state_code + county_name alias-coalescing for the bronze key only.
    assert natural_key_for({"name": "Madison", "state": "al"}) == ("AL", "Madison")
    assert natural_key_for(
        {"county_name": "Jefferson", "state_code": "ga"}
    ) == ("GA", "Jefferson")
    assert natural_key_for(
        {"countyName": "Cobb", "stateCode": "ga"}
    ) == ("GA", "Cobb")
    # Missing county or state -> None (row is dropped, as parse_county did).
    assert natural_key_for({"name": "X"}) is None
    assert natural_key_for({"state": "AL"}) is None


def test_county_row_schema_accepts_valid():
    # Slimmed raw shape: natural key components + the full raw JSON object.
    r = CountyRow(
        source="naco_counties",
        source_version="naco_counties_AL_20260510",
        natural_key="AL:Madison",
        county_name="Madison",
        state_code="AL",
        raw_json={
            "name": "Madison",
            "state": "AL",
            "fips": "01089",
            "population": 400000,
        },
    )
    assert r.county_name == "Madison"
    assert r.state_code == "AL"
    # Derived columns are no longer on the row; the full object lands verbatim.
    assert r.raw_json["population"] == 400000
    assert r.raw_json["fips"] == "01089"


def test_county_row_schema_rejects_bad_state_and_empty_name():
    # state_code max 2 chars
    with pytest.raises(Exception):
        CountyRow(
            source="naco_counties",
            source_version="v",
            natural_key="x",
            county_name="Madison",
            state_code="ALA",
        )
    # county_name required (min_length 1)
    with pytest.raises(Exception):
        CountyRow(
            source="naco_counties",
            source_version="v",
            natural_key="x",
            county_name="",
            state_code="AL",
        )


def test_county_row_rejects_extra_field():
    with pytest.raises(Exception):
        CountyRow(
            source="naco_counties",
            source_version="v",
            natural_key="x",
            county_name="Madison",
            state_code="AL",
            bogus="nope",
        )


def test_pipeline_metadata():
    p = NacoCountiesPipeline()
    assert p.source == "naco_counties"
    assert p.batch_size == 2000
    assert p.row_schema is CountyRow


def test_find_cache_files_filters_by_date_and_state(tmp_path, monkeypatch):
    import ingestion.naco.counties as cp
    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    (tmp_path / "naco_counties_AL_20260510.json").write_text("[]")
    (tmp_path / "naco_counties_GA_20260510.json").write_text("[]")
    (tmp_path / "naco_counties_AL_20260101.json").write_text("[]")

    # no filter -> all 3
    assert len(find_cache_files(None, None)) == 3
    # date filter
    files = find_cache_files("20260510", None)
    assert len(files) == 2
    # state + date filter
    files = find_cache_files("20260510", ["AL"])
    assert len(files) == 1
    assert files[0].name == "naco_counties_AL_20260510.json"


def test_discover_raises_when_no_files(tmp_path, monkeypatch):
    import ingestion.naco.counties as cp
    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    p = NacoCountiesPipeline(date_str="20990101")
    with pytest.raises(FileNotFoundError):
        p._discover()


def test_extract_roundtrip_and_validates(tmp_path):
    cache_file = tmp_path / "naco_counties_AL_20260510.json"
    cache_file.write_text(
        json.dumps([
            {"name": "Madison", "state": "AL", "fips": "01089", "population": 400000},
            {"name": "X", "_fallback": True},  # fallback -> skipped
            {"state": "AL"},  # missing name -> dropped (no usable natural key)
            {"name": "Jefferson", "state": "al", "fips": "01073"},
        ])
    )
    p = NacoCountiesPipeline(path=cache_file)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["county_name"] == "Madison"
    assert extracted[0]["state_code"] == "AL"
    assert extracted[0]["natural_key"] == "AL:Madison"
    assert extracted[0]["source"] == "naco_counties"
    assert extracted[0]["source_version"] == "naco_counties_AL_20260510"
    # RAW JSON lands verbatim — derived fields (population/fips) are NOT parsed
    # in Python anymore, they ride along inside raw_json for dbt to extract.
    assert extracted[0]["raw_json"]["name"] == "Madison"
    assert extracted[0]["raw_json"]["population"] == 400000
    assert extracted[0]["raw_json"]["fips"] == "01089"
    # Only the natural-key columns + raw_json are emitted (slimmed shape).
    assert set(extracted[0]) == {
        "source", "source_version", "natural_key",
        "county_name", "state_code", "raw_json",
    }
    assert extracted[1]["county_name"] == "Jefferson"
    assert extracted[1]["state_code"] == "AL"  # uppercased
    assert extracted[1]["raw_json"]["state"] == "al"  # raw value preserved

    # All extracted rows validate cleanly through the schema
    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_limit_caps_rows(tmp_path):
    cache_file = tmp_path / "naco_counties_AL_20260510.json"
    records = [
        {"name": f"County{i}", "state": "AL", "fips": f"010{i:02d}"}
        for i in range(10)
    ]
    cache_file.write_text(json.dumps(records))
    p = NacoCountiesPipeline(path=cache_file, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

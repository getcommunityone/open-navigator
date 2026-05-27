"""Unit tests for the Census ACS pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest


from ingestion.census.acs import (  # noqa: E402
    AcsCellRow,
    CensusAcsPipeline,
    _geo_id_for_row,
    _safe_str,
    find_acs_parquets,
    parse_parquet_name,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_safe_str_trims_and_drops_empty():
    assert _safe_str("  hello  ") == "hello"
    assert _safe_str("") is None
    assert _safe_str("   ") is None
    assert _safe_str(None) is None
    assert _safe_str(float("nan")) is None
    assert _safe_str(42) == "42"


def test_parse_parquet_name_extracts_parts():
    parts = parse_parquet_name(Path("B19013_county_06_2022.parquet"))
    assert parts == {
        "table": "B19013",
        "geography": "county",
        "state": "06",
        "year": "2022",
    }
    # subject tables and the wildcard-state token also parse
    assert parse_parquet_name(Path("S0801_state_*_2021.parquet"))["table"] == "S0801"


def test_parse_parquet_name_rejects_bad_name():
    with pytest.raises(ValueError):
        parse_parquet_name(Path("not_an_acs_file.csv"))


def test_geo_id_prefers_geo_id_then_composite_then_name():
    assert _geo_id_for_row({"GEO_ID": "0500000US06037", "NAME": "LA"}) == "0500000US06037"
    assert _geo_id_for_row({"state": "06", "county": "037", "NAME": "LA"}) == "06:037"
    assert _geo_id_for_row({"NAME": "California"}) == "California"
    assert _geo_id_for_row({}) == ""


def test_acs_cell_row_schema_accepts_valid():
    r = AcsCellRow(
        source="census_acs",
        source_version="B19013_county_06_2022",
        natural_key="B19013:county:06:2022:0500000US06037:B19013_001E",
        table="B19013",
        geography="county",
        state="06",
        year=2022,
        geo_id="0500000US06037",
        geo_name="Los Angeles County, California",
        variable="B19013_001E",
        value="83411",
    )
    assert r.table == "B19013"
    assert r.year == 2022
    assert r.value == "83411"


def test_acs_cell_row_schema_rejects_invalid():
    # empty required field (variable) rejected
    with pytest.raises(Exception):
        AcsCellRow(
            source="census_acs",
            source_version="v",
            natural_key="k",
            table="B19013",
            geography="county",
            state="06",
            year=2022,
            geo_id="g",
            variable="",
        )
    # non-int year rejected
    with pytest.raises(Exception):
        AcsCellRow(
            source="census_acs",
            source_version="v",
            natural_key="k",
            table="B19013",
            geography="county",
            state="06",
            year="not-a-year",
            geo_id="g",
            variable="B19013_001E",
        )


def test_pipeline_metadata():
    p = CensusAcsPipeline()
    assert p.source == "census_acs"
    assert p.batch_size == 5000
    assert p.row_schema is AcsCellRow


def test_find_acs_parquets_raises_when_no_files(tmp_path, monkeypatch):
    import ingestion.census.acs as acs
    monkeypatch.setattr(acs, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_acs_parquets()


def test_extract_melts_wide_parquet_and_validates(tmp_path):
    parquet_path = tmp_path / "B19013_county_06_2022.parquet"
    pd.DataFrame(
        [
            {"GEO_ID": "0500000US06037", "NAME": "Los Angeles County", "B19013_001E": "83411", "B19013_001M": "512"},
            {"GEO_ID": "0500000US06075", "NAME": "San Francisco County", "B19013_001E": "141446", "B19013_001M": "3200"},
        ]
    ).to_parquet(parquet_path, index=False)

    p = CensusAcsPipeline(path=parquet_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    # 2 geographies x 2 value columns (GEO_ID/NAME are identity cols, not melted)
    assert len(extracted) == 4
    first = extracted[0]
    assert first["table"] == "B19013"
    assert first["geography"] == "county"
    assert first["state"] == "06"
    assert first["year"] == 2022
    assert first["geo_id"] == "0500000US06037"
    assert first["geo_name"] == "Los Angeles County"
    assert first["variable"] == "B19013_001E"
    assert first["value"] == "83411"
    assert first["natural_key"] == "B19013:county:06:2022:0500000US06037:B19013_001E"

    # All extracted rows validate cleanly
    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_limit_caps_cells(tmp_path):
    parquet_path = tmp_path / "B19013_county_06_2022.parquet"
    rows = [
        {"GEO_ID": f"0500000US060{i:02d}", "NAME": f"County {i}", "B19013_001E": str(i), "B19013_001M": "1"}
        for i in range(10)
    ]
    pd.DataFrame(rows).to_parquet(parquet_path, index=False)

    p = CensusAcsPipeline(path=parquet_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

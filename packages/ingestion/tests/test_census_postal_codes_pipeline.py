"""Unit tests for the Census postal codes (ZCTA) pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest


from ingestion.census.postal_codes import (  # noqa: E402
    CensusPostalCodesPipeline,
    PostalCodeRow,
    find_cached_csv,
    safe_float,
    safe_int,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_csv(path: Path) -> None:
    """Synthetic Gazetteer-style CSV (header + 3 ZCTAs, one invalid GEOID)."""
    path.write_text(
        "GEOID,ALAND,AWATER,ALAND_SQMI,AWATER_SQMI,INTPTLAT,INTPTLONG\n"
        "00601,166659789,799292,64.348,0.309,18.180555,-66.749961\n"
        "12,100,0,1.0,0.0,40.0,-70.0\n"  # GEOID not 5 digits -> dropped
        "10001,1827919,90865,0.706,0.035,40.750742,-73.997039\n"
    )


def test_safe_int_parses_and_handles_bad_input():
    assert safe_int("100") == 100
    assert safe_int("100.0") == 100
    assert safe_int(166659789) == 166659789
    assert safe_int("") is None
    assert safe_int(None) is None
    assert safe_int("not-a-number") is None


def test_safe_float_parses_and_handles_bad_input():
    assert safe_float("64.348") == 64.348
    assert safe_float("0") == 0.0
    assert safe_float("") is None
    assert safe_float(None) is None
    assert safe_float("not-a-number") is None


def test_postal_code_row_schema_accepts_valid():
    r = PostalCodeRow(
        source="census_postal_codes",
        source_version="2024",
        natural_key="zcta:00601",
        zcta="00601",
        geoid="00601",
        aland=166659789,
        awater=799292,
        aland_sqmi=64.348,
        awater_sqmi=0.309,
        intptlat=18.180555,
        intptlong=-66.749961,
        source_file="Census Gazetteer 2024",
    )
    assert r.zcta == "00601"
    assert r.geoid == "00601"
    assert r.aland == 166659789


def test_postal_code_row_schema_allows_null_numerics():
    r = PostalCodeRow(
        source="census_postal_codes",
        source_version="2024",
        natural_key="zcta:10001",
        zcta="10001",
        geoid="10001",
    )
    assert r.aland is None
    assert r.intptlat is None
    assert r.source_file is None


def test_postal_code_row_schema_rejects_empty_zcta():
    with pytest.raises(Exception):
        PostalCodeRow(
            source="census_postal_codes",
            source_version="2024",
            natural_key="zcta:",
            zcta="",
            geoid="00601",
        )


def test_postal_code_row_schema_forbids_extra_fields():
    with pytest.raises(Exception):
        PostalCodeRow(
            source="census_postal_codes",
            source_version="2024",
            natural_key="zcta:00601",
            zcta="00601",
            geoid="00601",
            unexpected="boom",
        )


def test_pipeline_metadata():
    p = CensusPostalCodesPipeline()
    assert p.source == "census_postal_codes"
    assert p.batch_size == 5000
    assert p.row_schema is PostalCodeRow


def test_find_cached_csv_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.census.postal_codes as pc
    monkeypatch.setattr(pc, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_cached_csv(2024)


def test_find_cached_csv_returns_path_when_present(tmp_path, monkeypatch):
    import ingestion.census.postal_codes as pc
    monkeypatch.setattr(pc, "CACHE_DIR", tmp_path)
    (tmp_path / "zcta_2024.csv").write_text("GEOID\n00601\n")
    found = find_cached_csv(2024)
    assert found.name == "zcta_2024.csv"


def test_extract_yields_validated_rows(tmp_path):
    csv_path = tmp_path / "zcta_2024.csv"
    _write_csv(csv_path)
    p = CensusPostalCodesPipeline(path=csv_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    # Invalid (non-5-digit) GEOID is dropped.
    assert len(extracted) == 2
    assert extracted[0]["zcta"] == "00601"
    assert extracted[0]["geoid"] == "00601"
    assert extracted[0]["natural_key"] == "zcta:00601"
    assert extracted[0]["aland"] == 166659789
    assert extracted[0]["aland_sqmi"] == 64.348
    assert extracted[0]["source_file"] == "Census Gazetteer 2024"
    assert extracted[1]["zcta"] == "10001"

    # All extracted rows validate cleanly.
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_limit_caps_extracted_rows(tmp_path):
    csv_path = tmp_path / "zcta_2024.csv"
    rows = ["GEOID,ALAND,AWATER,ALAND_SQMI,AWATER_SQMI,INTPTLAT,INTPTLONG"]
    for i in range(10):
        rows.append(f"{10000 + i},100,0,1.0,0.0,40.0,-70.0")
    csv_path.write_text("\n".join(rows) + "\n")

    p = CensusPostalCodesPipeline(path=csv_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

"""Unit tests for the Census Gazetteer pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest


from ingestion.census.gazetteer import (  # noqa: E402
    CensusGazetteerPipeline,
    GazetteerRow,
    TYPES,
    build_records,
    safe_float,
    safe_int,
    safe_str,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_safe_helpers_handle_blanks_and_truncation():
    assert safe_str("  hello  ") == "hello"
    assert safe_str("") is None
    assert safe_str("nan") is None
    assert safe_str(None) is None
    assert safe_str("abcdef", 3) == "abc"

    assert safe_int("42") == 42
    assert safe_int("42.9") == 42
    assert safe_int("") is None
    assert safe_int(None) is None

    assert safe_float("1.5") == 1.5
    assert safe_float("") is None
    assert safe_float("oops") is None


def test_build_records_zfills_geoid_and_drops_blank():
    import pandas as pd

    df = pd.DataFrame(
        {
            "GEOID": ["1", "", "13"],
            "USPS": ["AL", "GA", "GA"],
            "ANSICODE": ["x", "y", "z"],
            "NAME": ["Alabama", "Skip", "Georgia"],
            "ALAND": ["100", "0", "200"],
            "AWATER": ["1", "0", "2"],
            "ALAND_SQMI": ["1.5", "0", "2.5"],
            "AWATER_SQMI": ["0.1", "0", "0.2"],
            "INTPTLAT": ["32.1", "0", "33.2"],
            "INTPTLONG": ["-86.1", "0", "-84.2"],
        }
    )
    records = build_records(df, "states")
    # Blank GEOID row dropped -> 2 records
    assert len(records) == 2
    assert records[0]["geoid"] == "01"  # zfilled to geoid_len=2
    assert records[1]["geoid"] == "13"
    assert records[0]["aland"] == 100
    assert records[0]["aland_sqmi"] == 1.5


def test_schema_accepts_full_row():
    r = GazetteerRow(
        source="census_gazetteer",
        source_version="states",
        natural_key="states:01",
        jtype="states",
        geoid="01",
        usps="AL",
        ansicode="01779775",
        name="Alabama",
        aland=131173688951,
        awater=4593686489,
        aland_sqmi=Decimal("50645.326"),
        awater_sqmi=Decimal("1773.636"),
        intptlat=Decimal("32.7570970"),
        intptlong=Decimal("-86.8434790"),
    )
    assert r.geoid == "01"
    assert r.usps == "AL"
    assert r.aland_sqmi == Decimal("50645.326")


def test_schema_rejects_oversized_usps():
    with pytest.raises(Exception):
        GazetteerRow(
            source="census_gazetteer",
            source_version="states",
            natural_key="states:01",
            jtype="states",
            geoid="01",
            usps="ABC",  # max_length=2
        )


def test_schema_rejects_missing_geoid():
    with pytest.raises(Exception):
        GazetteerRow(
            source="census_gazetteer",
            source_version="states",
            natural_key="states:",
            jtype="states",
            geoid="",  # min_length=1
        )


def test_pipeline_metadata():
    p = CensusGazetteerPipeline()
    assert p.source == "census_gazetteer"
    assert p.batch_size == 5000
    assert p.row_schema is GazetteerRow
    assert set(p._types) == set(TYPES.keys())


def test_extract_skips_missing_cache_file(tmp_path, monkeypatch):
    import ingestion.census.gazetteer as gz

    monkeypatch.setattr(gz, "CACHE_DIR", tmp_path)
    # No CSVs in tmp_path -> every type's cache file is missing -> empty extract.
    p = CensusGazetteerPipeline(types=["states"])

    async def collect():
        return [r async for r in p.extract(_ctx())]

    assert asyncio.run(collect()) == []


def test_extract_roundtrip_and_validates(tmp_path):
    csv_path = tmp_path / "states.csv"
    csv_path.write_text(
        "GEOID,USPS,ANSICODE,NAME,ALAND,AWATER,ALAND_SQMI,AWATER_SQMI,INTPTLAT,INTPTLONG\n"
        "1,AL,01779775,Alabama,131173688951,4593686489,50645.326,1773.636,32.7570970,-86.8434790\n"
        ",GA,01705317,SkipMe,1,1,1,1,1,1\n"  # blank GEOID -> dropped
        "13,GA,01705317,Georgia,149482048342,4422232563,57713.241,1707.430,32.6304790,-83.4239580\n"
    )
    p = CensusGazetteerPipeline(path=csv_path, types=["states"])

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["geoid"] == "01"
    assert extracted[0]["jtype"] == "states"
    assert extracted[0]["natural_key"] == "states:01"
    assert extracted[1]["geoid"] == "13"

    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_limit_caps_rows(tmp_path):
    rows = ["GEOID,USPS,ANSICODE,NAME,ALAND,AWATER,ALAND_SQMI,AWATER_SQMI,INTPTLAT,INTPTLONG"]
    for i in range(10):
        rows.append(f"{i + 1:02d},AL,x{i},Name{i},1,1,1,1,1,1")
    csv_path = tmp_path / "states.csv"
    csv_path.write_text("\n".join(rows) + "\n")

    p = CensusGazetteerPipeline(path=csv_path, types=["states"], limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    assert len(asyncio.run(collect())) == 3

"""Unit tests for the jurisdictions counties pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import pytest

from ingestion.census.counties_jurisdictions import (  # noqa: E402
    CountyRow,
    JurisdictionsCountiesPipeline,
    jurisdiction_id_from_name_geoid,
    place_slug_for_jurisdiction_id,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_parquet(path, rows: list[dict]):
    pd.DataFrame(rows).to_parquet(path)
    return path


def test_place_slug_strips_lsad_and_snake_cases():
    assert place_slug_for_jurisdiction_id("Mobile County") == "mobile"
    assert place_slug_for_jurisdiction_id("St. Clair County") == "st_clair"
    assert place_slug_for_jurisdiction_id("County of Marin") == "marin"


def test_jurisdiction_id_from_name_geoid():
    assert jurisdiction_id_from_name_geoid("Mobile County", "01097", jurisdiction_type="county") == "mobile_01097"
    # non-numeric geoid -> empty
    assert jurisdiction_id_from_name_geoid("Mobile County", "abc") == ""
    # hyphens stripped from geoid
    assert jurisdiction_id_from_name_geoid("Marin County", "06-041", jurisdiction_type="county") == "marin_06041"


def test_county_row_schema_accepts_valid():
    r = CountyRow(
        source="jurisdictions_counties",
        source_version="jurisdictions_counties",
        natural_key="mobile_01097",
        jurisdiction_id="mobile_01097",
        jurisdiction_name="Mobile",
        state_code="AL",
        state="AL",
        discovery_timestamp=pd.Timestamp("2026-01-01"),
    )
    assert r.jurisdiction_id == "mobile_01097"
    assert r.jurisdiction_type == "county"
    assert r.youtube_channels == "[]"
    assert r.status == "pending_discovery"


def test_county_row_schema_rejects_empty_id():
    with pytest.raises(Exception):
        CountyRow(
            source="jurisdictions_counties",
            source_version="v",
            natural_key="x",
            jurisdiction_id="",
            jurisdiction_name="Mobile",
            discovery_timestamp=pd.Timestamp("2026-01-01"),
        )


def test_county_row_schema_rejects_overlong_state():
    with pytest.raises(Exception):
        CountyRow(
            source="jurisdictions_counties",
            source_version="v",
            natural_key="x",
            jurisdiction_id="mobile_01097",
            jurisdiction_name="Mobile",
            state="ALA",
            discovery_timestamp=pd.Timestamp("2026-01-01"),
        )


def test_pipeline_metadata():
    p = JurisdictionsCountiesPipeline()
    assert p.source == "jurisdictions_counties"
    assert p.batch_size == 1000
    assert p.row_schema is CountyRow


def test_extract_yields_validated_rows(tmp_path):
    path = _write_parquet(
        tmp_path / "jurisdictions_counties.parquet",
        [
            {"NAME": "Mobile County", "USPS": "AL", "GEOID": "01097", "download_date": "2026-01-01"},
            {"NAME": "Marin County", "USPS": "CA", "GEOID": "06041", "download_date": "2026-01-01"},
        ],
    )
    p = JurisdictionsCountiesPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["jurisdiction_id"] == "mobile_01097"
    assert extracted[0]["jurisdiction_name"] == "Mobile"
    assert extracted[0]["state"] == "AL"
    assert extracted[0]["jurisdiction_type"] == "county"
    assert extracted[1]["jurisdiction_id"] == "marin_06041"

    # All extracted rows validate cleanly
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_states_filter(tmp_path):
    path = _write_parquet(
        tmp_path / "jurisdictions_counties.parquet",
        [
            {"NAME": "Mobile County", "USPS": "AL", "GEOID": "01097", "download_date": "2026-01-01"},
            {"NAME": "Marin County", "USPS": "CA", "GEOID": "06041", "download_date": "2026-01-01"},
        ],
    )
    p = JurisdictionsCountiesPipeline(path=path, states=["AL"])

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    assert extracted[0]["state"] == "AL"


def test_limit_caps_extracted_rows(tmp_path):
    rows = [
        {"NAME": f"County{i} County", "USPS": "AL", "GEOID": f"010{i:02d}", "download_date": "2026-01-01"}
        for i in range(10)
    ]
    path = _write_parquet(tmp_path / "jurisdictions_counties.parquet", rows)
    p = JurisdictionsCountiesPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

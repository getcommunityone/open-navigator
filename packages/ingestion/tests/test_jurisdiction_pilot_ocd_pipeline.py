"""Unit tests for the jurisdiction_pilot OCD pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


from ingestion.jurisdiction_pilot.ocd import (  # noqa: E402
    JurisdictionOcdRow,
    JurisdictionPilotOcdPipeline,
    find_cache_dir,
    parse_country_row,
    parse_local_gov_row,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_parse_country_row_county_and_place():
    county = parse_country_row(
        "ocd-division/country:us/state:ca/county:los_angeles", "Los Angeles"
    )
    assert county == {
        "ocd_id": "ocd-division/country:us/state:ca/county:los_angeles",
        "state_code": "CA",
        "jurisdiction_type": "county",
        "name": "Los Angeles",
        "parent_ocd_id": None,
    }

    place = parse_country_row(
        "ocd-division/country:us/state:ny/place:new_york", "New York"
    )
    assert place["jurisdiction_type"] == "place"
    assert place["state_code"] == "NY"


def test_parse_country_row_school_district_parent():
    rec = parse_country_row(
        "ocd-division/country:us/state:tx/county:harris/school_district:houston_isd",
        "Houston ISD",
    )
    assert rec["jurisdiction_type"] == "school_district"
    assert rec["parent_ocd_id"] == "ocd-division/country:us/state:tx/county:harris"


def test_parse_country_row_skips_invalid():
    # Empty inputs
    assert parse_country_row("", "x") is None
    assert parse_country_row("x", "") is None
    # No state component
    assert parse_country_row("ocd-division/country:us", "US") is None
    # State but no jurisdiction type
    assert parse_country_row("ocd-division/country:us/state:ca", "California") is None


def test_parse_local_gov_row_classification():
    # An ocd_id containing place: is classified as place first (if/elif order in
    # the original loader), so council_district / ward never win when place: is
    # present. Behavior preserved verbatim from the original loader.
    rec = parse_local_gov_row(
        "ocd-division/country:us/state:wa/place:seattle/council_district:1",
        "District 1",
        "WA",
    )
    assert rec["jurisdiction_type"] == "place"
    assert rec["parent_ocd_id"] is None

    # Without a place: segment, council_district / ward are classified as such,
    # but the parent-place extraction is dead code (it requires place:), so
    # parent_ocd_id stays None.
    cd = parse_local_gov_row(
        "ocd-division/country:us/state:wa/council_district:1", "District 1", "WA"
    )
    assert cd["jurisdiction_type"] == "council_district"
    assert cd["parent_ocd_id"] is None

    ward = parse_local_gov_row(
        "ocd-division/country:us/state:il/ward:5", "Ward 5", "IL"
    )
    assert ward["jurisdiction_type"] == "ward"
    assert ward["parent_ocd_id"] is None

    # row with no recognizable jurisdiction type is skipped
    assert parse_local_gov_row("ocd-division/country:us/state:il", "x", "IL") is None


def test_ocd_row_schema_accepts_valid():
    r = JurisdictionOcdRow(
        source="jurisdiction_pilot_ocd",
        source_version="country-us",
        natural_key="ocd-division/country:us/state:ca/county:los_angeles",
        ocd_id="ocd-division/country:us/state:ca/county:los_angeles",
        state_code="CA",
        jurisdiction_type="county",
        name="Los Angeles",
        parent_ocd_id=None,
    )
    assert r.ocd_id.endswith("los_angeles")
    assert r.state_code == "CA"
    assert r.parent_ocd_id is None


def test_ocd_row_schema_rejects_empty_required_and_extra():
    # empty required field
    with pytest.raises(Exception):
        JurisdictionOcdRow(
            source="jurisdiction_pilot_ocd",
            source_version="v",
            natural_key="k",
            ocd_id="",
            state_code="CA",
            jurisdiction_type="county",
            name="X",
        )
    # extra field forbidden by RawRow config
    with pytest.raises(Exception):
        JurisdictionOcdRow(
            source="jurisdiction_pilot_ocd",
            source_version="v",
            natural_key="k",
            ocd_id="ocd-division/country:us/state:ca/county:x",
            state_code="CA",
            jurisdiction_type="county",
            name="X",
            bogus="nope",
        )


def test_find_cache_dir_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.jurisdiction_pilot.ocd as op
    monkeypatch.setattr(op, "CACHE_DIR", tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        find_cache_dir()


def test_pipeline_metadata():
    p = JurisdictionPilotOcdPipeline()
    assert p.source == "jurisdiction_pilot_ocd"
    assert p.batch_size == 2000
    assert p.row_schema is JurisdictionOcdRow


def test_extract_roundtrip_country_and_local(tmp_path):
    identifiers = tmp_path / "identifiers"
    identifiers.mkdir()
    (identifiers / "country-us.csv").write_text(
        "ocd-division/country:us/state:ca/county:los_angeles,Los Angeles\n"
        "ocd-division/country:us/state:tx/county:harris/school_district:houston_isd,Houston ISD\n"
        ",skip\n"  # empty ocd_id -> dropped
        "ocd-division/country:us,US\n"  # no state -> dropped
    )
    country_us = identifiers / "country-us"
    country_us.mkdir()
    (country_us / "state-wa-local_gov.csv").write_text(
        "ocd-division/country:us/state:wa/place:seattle,Seattle\n"
        "ocd-division/country:us/state:wa/council_district:1,District 1\n"
    )

    p = JurisdictionPilotOcdPipeline(path=tmp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 4
    # country-us rows first, in file order
    assert extracted[0]["ocd_id"].endswith("county:los_angeles")
    assert extracted[0]["source"] == "jurisdiction_pilot_ocd"
    assert extracted[0]["source_version"] == "country-us"
    assert extracted[0]["natural_key"] == extracted[0]["ocd_id"]
    assert extracted[1]["jurisdiction_type"] == "school_district"
    # then the local_gov rows
    assert extracted[2]["jurisdiction_type"] == "place"
    assert extracted[2]["state_code"] == "WA"
    assert extracted[2]["source_version"] == "state-wa-local_gov"
    assert extracted[3]["jurisdiction_type"] == "council_district"

    # All extracted rows validate cleanly
    for raw in extracted:
        assert p.validate(raw) is not None


def test_limit_caps_extracted_rows(tmp_path):
    identifiers = tmp_path / "identifiers"
    identifiers.mkdir()
    lines = [
        f"ocd-division/country:us/state:ca/county:c{i},County {i}" for i in range(10)
    ]
    (identifiers / "country-us.csv").write_text("\n".join(lines) + "\n")

    p = JurisdictionPilotOcdPipeline(path=tmp_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

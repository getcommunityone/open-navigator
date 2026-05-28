"""Unit tests for the arcgis addresses pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


from ingestion.arcgis.addresses import (  # noqa: E402
    ArcgisAddressesPipeline,
    ParcelAddressRow,
    _build_situs_full,
    _clean_int,
    _clean_str,
    _first_int,
    _first_str,
    _source_record_id,
    normalize_column_names,
    row_to_record,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_clean_helpers_trim_and_coerce():
    assert _clean_str("  hello  ") == "hello"
    assert _clean_str("") is None
    assert _clean_str("   ") is None
    assert _clean_str(None) is None
    assert _clean_int("42") == 42
    assert _clean_int("42.9") == 42
    assert _clean_int("not-a-number") is None
    assert _clean_int(None) is None


def test_first_str_and_first_int_pick_first_present():
    row = {"a": "", "b": "  ", "c": "found", "n1": "x", "n2": "7"}
    assert _first_str(row, "a", "b", "c") == "found"
    assert _first_str(row, "a", "b") is None
    assert _first_int(row, "n1", "n2") == 7
    assert _first_int(row, "n1") is None


def test_source_record_id_falls_back_to_unknown():
    assert _source_record_id({"parcel_id": "P-1"}) == "P-1"
    assert _source_record_id({"OBJECTID": "99"}) == "99"
    assert _source_record_id({"irrelevant": "x"}) == "unknown"


def test_build_situs_full_composes_address():
    row = {
        "situs_address": "100 Main St",
        "addCITY": "Tuscaloosa",
        "stABBR": "AL",
        "addZIP": "35401",
    }
    assert _build_situs_full(row) == "100 Main St, Tuscaloosa, AL 35401"


def test_normalize_column_names_maps_aliases():
    import pandas as pd

    df = pd.DataFrame({"PARCELID": ["1"], "OWNER_NAME": ["Doe"], "weird": ["z"]})
    out = normalize_column_names(df)
    assert "parcel_id" in out.columns
    assert "owner_primary" in out.columns
    assert "weird" in out.columns  # untouched


def test_row_to_record_shapes_record():
    rec = row_to_record(
        {"parcel_id": "P-1", "OWNER_NAME": "Jane", "ADDRESS": "5 Oak Ave"},
        source_dataset="al_tuscaloosa_county_parcels",
        state_code="al",
        county_fips="01125",
        county_name="Tuscaloosa",
        jurisdiction_id="county_01125",
        esri_endpoint="https://example.com/0",
    )
    assert rec["source_dataset"] == "al_tuscaloosa_county_parcels"
    assert rec["source_record_id"] == "P-1"
    assert rec["state_code"] == "AL"
    assert rec["owner_name"] == "Jane"
    assert rec["situs_location"] == "5 Oak Ave"
    assert rec["data_source"] == "esri_parcel"
    assert rec["raw_attributes"]["parcel_id"] == "P-1"


def test_parcel_address_row_schema_accepts_and_rejects():
    r = ParcelAddressRow(
        source="arcgis_addresses",
        source_version="tuscaloosa_county_attrs",
        natural_key="ds:P-1",
        source_dataset="ds",
        source_record_id="P-1",
        state_code="AL",
        county_fips="01125",
        appraised_value=12345,
        raw_attributes={"k": "v"},
    )
    assert r.state_code == "AL"
    assert r.appraised_value == 12345
    assert r.data_source == "esri_parcel"

    # state_code must be max 2 chars
    with pytest.raises(Exception):
        ParcelAddressRow(
            source="arcgis_addresses",
            source_version="v",
            natural_key="ds:P-1",
            source_dataset="ds",
            source_record_id="P-1",
            state_code="ALA",
        )

    # source_record_id is required (min_length=1)
    with pytest.raises(Exception):
        ParcelAddressRow(
            source="arcgis_addresses",
            source_version="v",
            natural_key="ds:",
            source_dataset="ds",
            source_record_id="",
            state_code="AL",
        )


def test_pipeline_metadata():
    p = ArcgisAddressesPipeline()
    assert p.source == "arcgis_addresses"
    assert p.batch_size == 5000
    assert p.row_schema is ParcelAddressRow


def test_discover_path_raises_when_missing(tmp_path):
    p = ArcgisAddressesPipeline(path=tmp_path / "nope.csv")
    with pytest.raises(FileNotFoundError):
        p._discover_path()

    p2 = ArcgisAddressesPipeline()
    with pytest.raises(FileNotFoundError):
        p2._discover_path()


def test_extract_roundtrip_and_validate(tmp_path):
    csv_path = tmp_path / "tuscaloosa_county_attrs.csv"
    csv_path.write_text(
        "PARCELID,OWNER_NAME,ADDRESS,addCITY,addZIP\n"
        "P-1,Jane Doe,5 Oak Ave,Tuscaloosa,35401\n"
        "P-2,John Smith,6 Elm St,Tuscaloosa,35402\n"
    )
    p = ArcgisAddressesPipeline(
        path=csv_path,
        source_dataset="al_tuscaloosa_county_parcels",
        state_code="AL",
        county_fips="01125",
        county_name="Tuscaloosa",
        jurisdiction_id="county_01125",
        esri_endpoint="https://example.com/0",
    )

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["source"] == "arcgis_addresses"
    assert extracted[0]["source_record_id"] == "P-1"
    assert extracted[0]["state_code"] == "AL"
    assert extracted[0]["natural_key"] == "al_tuscaloosa_county_parcels:P-1"
    assert extracted[1]["owner_name"] == "John Smith"

    # All extracted rows validate cleanly against the schema.
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_limit_caps_rows(tmp_path):
    csv_path = tmp_path / "big_county_attrs.csv"
    lines = ["PARCELID,OWNER_NAME"]
    for i in range(10):
        lines.append(f"P-{i},Owner{i}")
    csv_path.write_text("\n".join(lines) + "\n")

    p = ArcgisAddressesPipeline(
        path=csv_path,
        limit=3,
        source_dataset="ds",
        state_code="AL",
    )

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

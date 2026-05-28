"""Unit tests for the TPC Government Finance ingestion pipeline.

Offline-only — no Drive, no DB. Exercises the deterministic helpers
(gov_type inference, FIELD_MAP coalescing, row-to-bronze translation,
zip-bundle extraction, end-to-end extract over a fixture CSV) so CI can
run these without ``gdown`` or a Postgres instance.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion.tpc.finance import (  # noqa: E402
    TpcGovernmentFinancePipeline,
    TpcGovernmentFinanceRow,
    extract_bundle,
    infer_gov_type,
    row_to_bronze_dict,
    _first_match,
    STATE_FIPS_TO_POSTAL,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


# ── helpers ────────────────────────────────────────────────────────────────

def test_infer_gov_type_matches_known_tokens() -> None:
    assert infer_gov_type("state_finances.csv") == "state"
    assert infer_gov_type("county_2022.csv") == "county"
    assert infer_gov_type("CityData.csv") == "city"
    assert infer_gov_type("municipal_2020.csv") == "city"
    assert infer_gov_type("school_district_2021.csv") == "school_district"
    assert infer_gov_type("special_district_yearly.csv") == "special_district"
    assert infer_gov_type("misc_data.csv") == "other"


def test_first_match_skips_empty_and_returns_first_hit() -> None:
    row = {"ID4": "", "ID": "g123", "id": "lowercase"}
    # ID4 is empty, ID wins (it's the second candidate after the empty first)
    assert _first_match(row, ("ID4", "ID", "id")) == "g123"
    # All empty → None
    assert _first_match({"a": "", "b": None}, ("a", "b")) is None
    # Missing keys → None (no KeyError)
    assert _first_match({}, ("a", "b")) is None


def test_state_fips_to_postal_has_50_states_plus_dc() -> None:
    # Sanity: 50 + DC = 51, plus territories. Spot-check a few.
    assert STATE_FIPS_TO_POSTAL["06"] == "CA"
    assert STATE_FIPS_TO_POSTAL["36"] == "NY"
    assert STATE_FIPS_TO_POSTAL["48"] == "TX"
    assert STATE_FIPS_TO_POSTAL["11"] == "DC"
    state_count = sum(1 for k in STATE_FIPS_TO_POSTAL if int(k) <= 56)
    assert state_count == 51  # 50 states + DC


# ── row translation ────────────────────────────────────────────────────────

def test_row_to_bronze_handles_modern_column_names() -> None:
    row = {
        "ID": "AL_001_2022",
        "Name": "Alabama State Government",
        "State": "01",  # FIPS
        "Year": "2022",
        "Population": "5074000",
        "T01_property_tax": "1234567",
        "R01_intergovt_rev_fed": "9876543",
    }
    out = row_to_bronze_dict(row, gov_type="state", source_file="state.csv")
    assert out is not None
    assert out["id_code"] == "AL_001_2022"
    assert out["name"] == "Alabama State Government"
    assert out["state_fips"] == "01"
    assert out["state_code"] == "AL"  # back-filled from FIPS
    assert out["gov_type"] == "state"
    assert out["fiscal_year"] == 2022
    assert out["population"] == 5074000
    assert out["natural_key"] == "state:AL_001_2022:2022"
    # raw_record carries every column verbatim, including the extracted ones.
    assert "T01_property_tax" in out["raw_record"]
    assert out["raw_record"]["Name"] == "Alabama State Government"


def test_row_to_bronze_handles_legacy_id4_year4_columns() -> None:
    """TPC's older releases use ID4 / Name4 / State4 / Year4. FIELD_MAP must
    accept both shapes without operator-side preprocessing."""
    row = {
        "ID4": "TX_county_201",
        "Name4": "Travis County",
        "State4": "48",
        "Year4": "2019",
        "Pop4": "1.3e6",
    }
    out = row_to_bronze_dict(row, gov_type="county", source_file="legacy.csv")
    assert out is not None
    assert out["id_code"] == "TX_county_201"
    assert out["state_fips"] == "48"
    assert out["state_code"] == "TX"
    assert out["fiscal_year"] == 2019
    # Scientific-notation population string → int via float cast.
    assert out["population"] == 1300000


def test_row_to_bronze_postal_overrides_fips_when_present() -> None:
    """When both numeric FIPS and 2-letter postal are present, postal wins
    (it's more specific to TPC's "human-friendly" releases)."""
    row = {
        "ID": "x",
        "Year": "2020",
        "State": "06",
        "StateAbbrev": "CA",
    }
    out = row_to_bronze_dict(row, gov_type="city", source_file="city.csv")
    assert out is not None
    assert out["state_code"] == "CA"
    assert out["state_fips"] == "06"


def test_row_to_bronze_drops_summary_rows_missing_id_or_year() -> None:
    """TPC bundles occasionally include subtotal rows with blank id or year
    — those should be silently skipped, not blow up the batch."""
    assert row_to_bronze_dict(
        {"Name": "TOTAL", "Year": "2022"}, gov_type="state", source_file="s.csv"
    ) is None
    assert row_to_bronze_dict(
        {"ID": "x", "Name": "Foo"}, gov_type="state", source_file="s.csv"
    ) is None
    # Un-parseable year is treated as missing.
    assert row_to_bronze_dict(
        {"ID": "x", "Year": "n/a"}, gov_type="state", source_file="s.csv"
    ) is None


# ── pydantic schema ────────────────────────────────────────────────────────

def test_tpc_row_schema_accepts_valid() -> None:
    r = TpcGovernmentFinanceRow(
        source="tpc_government_finance",
        source_version="state.csv",
        natural_key="state:AL_001_2022:2022",
        id_code="AL_001_2022",
        name="Alabama",
        state_fips="01",
        state_code="AL",
        gov_type="state",
        fiscal_year=2022,
        population=5_000_000,
        raw_record={"T01": "1234"},
        source_file="state.csv",
    )
    assert r.fiscal_year == 2022
    assert r.raw_record["T01"] == "1234"


def test_tpc_row_schema_rejects_oversized_state_code() -> None:
    with pytest.raises(Exception):
        TpcGovernmentFinanceRow(
            source="tpc_government_finance",
            source_version="x",
            natural_key="x",
            id_code="x",
            gov_type="state",
            fiscal_year=2022,
            raw_record={},
            source_file="x.csv",
            state_code="CALIFORNIA",  # > 2 chars
        )


# ── bundle extraction ──────────────────────────────────────────────────────

def test_extract_bundle_sorts_by_gov_type(tmp_path: Path) -> None:
    """Zip with three files → three gov-type subdirs in the cache."""
    zip_path = tmp_path / "tpc_bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("state_finances_2022.csv", "ID,Year\nx,2022\n")
        zf.writestr("county_data.csv", "ID,Year\ny,2022\n")
        zf.writestr("school_district_yearly.csv", "ID,Year\nz,2022\n")
        zf.writestr("totally_unknown.csv", "ID,Year\nw,2022\n")

    cache_dir = tmp_path / "tpc"
    discovered = extract_bundle(zip_path, cache_dir=cache_dir)
    assert set(discovered.keys()) == {"state", "county", "school_district", "other"}
    assert (cache_dir / "state" / "state_finances_2022.csv").exists()
    assert (cache_dir / "county" / "county_data.csv").exists()
    assert (cache_dir / "school_district" / "school_district_yearly.csv").exists()
    assert (cache_dir / "other" / "totally_unknown.csv").exists()


# ── end-to-end extract over a fixture ──────────────────────────────────────

def _write_fixture_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ID", "Name", "State", "Year", "Population", "T01"])
        writer.writerow(["AL_001", "Alabama", "01", "2022", "5074000", "1234567"])
        writer.writerow(["CA_001", "California", "06", "2022", "39000000", "9876543"])
        # Summary row with no ID → must be skipped.
        writer.writerow(["", "TOTAL", "", "2022", "", "11111111"])
        # Row with bad year → must be skipped.
        writer.writerow(["TX_001", "Texas", "48", "n/a", "30000000", "5555"])


def test_pipeline_extract_over_fixture_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "tpc" / "state" / "state_finances_2022.csv"
    _write_fixture_csv(csv_path)

    pipe = TpcGovernmentFinancePipeline(
        cache_dir=tmp_path / "tpc",
        gov_type="state",
    )

    async def _collect() -> list[dict]:
        out: list[dict] = []
        async for row in pipe.extract(_ctx()):
            out.append(row)
        return out

    import asyncio

    rows = asyncio.run(_collect())
    # 4 input rows, 2 dropped (TOTAL + bad year) → 2 valid rows
    assert len(rows) == 2
    by_id = {r["id_code"]: r for r in rows}
    assert by_id["AL_001"]["state_code"] == "AL"
    assert by_id["CA_001"]["state_code"] == "CA"
    assert by_id["AL_001"]["population"] == 5_074_000
    assert by_id["AL_001"]["raw_record"]["T01"] == "1234567"


def test_pipeline_raises_when_no_csvs_and_not_fetching(tmp_path: Path) -> None:
    """Cache-only mode with an empty cache must fail loudly so the operator
    gets a clear "download first" message instead of an empty bronze load."""
    pipe = TpcGovernmentFinancePipeline(cache_dir=tmp_path / "tpc")

    async def _drain() -> None:
        async for _ in pipe.extract(_ctx()):
            pass

    import asyncio

    with pytest.raises(FileNotFoundError):
        asyncio.run(_drain())

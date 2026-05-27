"""Unit tests for the NCCS Unified BMF pipeline port."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


import ingestion.nccs.bulk as mod  # noqa: E402
from ingestion.nccs.bulk import (  # noqa: E402
    NccsBulkPipeline,
    NccsBulkRow,
    clean_record,
    find_full_file,
    find_state_files,
    _clean_float,
    _clean_int,
    _clean_str,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


# A small subset of the BMF header, enough to exercise extract/validate.
_HEADER = (
    "EIN,EIN2,ORG_NAME_CURRENT,F990_ORG_ADDR_STATE,ORG_YEAR_LAST,"
    "LATITUDE,LONGITUDE,ORG_YEAR_COUNT,F990_TOTAL_REVENUE_RECENT"
)


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_csv(path: Path, data_rows: list[str]) -> None:
    path.write_text(_HEADER + "\n" + "\n".join(data_rows) + "\n")


def test_clean_str_trims_and_drops_na():
    assert _clean_str("  hello  ") == "hello"
    assert _clean_str("") is None
    assert _clean_str("   ") is None
    assert _clean_str(None) is None
    assert _clean_str("NaN") is None
    assert _clean_str("<NA>") is None


def test_clean_int_and_float():
    assert _clean_int("42") == 42
    assert _clean_int("42.0") == 42
    assert _clean_int("") is None
    assert _clean_int("not-a-number") is None
    assert _clean_float("1.5") == 1.5
    assert _clean_float(None) is None
    assert _clean_float("nan") is None


def test_clean_record_typing_and_year_normalization():
    rec = clean_record({
        "ein": "123456789",
        "org_year_last": "2024-01-01",  # normalized to "2024"
        "latitude": "40.5",
        "org_year_count": "3",
        "f990_total_revenue_recent": "1000",
        "f990_org_addr_state": " CA ",
    })
    assert rec["ein"] == "123456789"
    assert rec["org_year_last"] == "2024"
    assert rec["latitude"] == 40.5
    assert rec["org_year_count"] == 3
    assert rec["f990_total_revenue_recent"] == 1000
    assert rec["f990_org_addr_state"] == "CA"
    # Unsupplied columns present as None
    assert rec["ntee_nccs"] is None


def test_schema_accepts_valid_row():
    row = NccsBulkRow.model_validate({
        "source": "nccs_bulk",
        "source_version": "unified-bmf-v1.2",
        "natural_key": "123456789:2024",
        "ein": "123456789",
        "f990_org_addr_state": "CA",
        "org_year_last": "2024",
        "latitude": 40.5,
        "org_year_count": 3,
        "f990_total_revenue_recent": 1000,
    })
    assert row.ein == "123456789"
    assert row.org_year_last == "2024"
    assert row.latitude == 40.5
    assert row.ntee_nccs is None


def test_schema_rejects_missing_ein_and_overlong_state():
    base = {
        "source": "nccs_bulk",
        "source_version": "unified-bmf-v1.2",
        "natural_key": "x",
        "ein": "123456789",
    }
    with pytest.raises(Exception):
        NccsBulkRow.model_validate({**base, "ein": ""})  # empty ein
    with pytest.raises(Exception):
        NccsBulkRow.model_validate({**base, "f990_org_addr_state": "CAL"})  # 3 chars


def test_pipeline_metadata():
    p = NccsBulkPipeline()
    assert p.source == "nccs_bulk"
    assert p.batch_size == 5_000
    assert p.row_schema is NccsBulkRow


def test_find_full_file_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_full_file(tmp_path)


def test_find_state_files_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_state_files(tmp_path, ["CA", "NY"])


def test_extract_yields_validated_envelope_rows(tmp_path):
    csv_path = tmp_path / "nccs_sample.csv"
    _write_csv(csv_path, [
        "123456789,9876,Alpha Charity,CA,2024,40.5,-122.1,3,1000",
        "987654321,1234,Beta Fund,NY,2023,,,,",
        ",0000,Missing EIN,TX,2022,,,,",  # missing ein -> skipped
    ])
    p = NccsBulkPipeline(path=csv_path)

    async def collect():
        out = []
        async for raw in p.extract(_ctx()):
            row = p.validate(raw)
            assert row is not None, f"rejected: {raw}"
            out.append(row)
        return out

    rows = asyncio.run(collect())
    assert len(rows) == 2  # third row skipped (missing ein)
    first = rows[0]
    assert first.ein == "123456789"
    assert first.org_name_current == "Alpha Charity"
    assert first.f990_org_addr_state == "CA"
    assert first.org_year_last == "2024"
    assert first.latitude == 40.5
    assert first.org_year_count == 3
    assert first.natural_key == "123456789:2024"
    assert first.source == "nccs_bulk"
    assert first.source_version == "unified-bmf-v1.2"
    # Second row's empty numerics normalized to None
    assert rows[1].latitude is None
    assert rows[1].org_year_count is None


def test_extract_respects_limit(tmp_path):
    csv_path = tmp_path / "nccs_sample.csv"
    _write_csv(csv_path, [
        "111111111,,A,CA,2024,,,,",
        "222222222,,B,NY,2023,,,,",
        "333333333,,C,TX,2022,,,,",
    ])
    p = NccsBulkPipeline(path=csv_path, limit=2)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    assert len(asyncio.run(collect())) == 2

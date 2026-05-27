"""Unit tests for the NCES school-districts pipeline port."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest


import ingestion.nces.school_districts as mod  # noqa: E402
from ingestion.nces.school_districts import (  # noqa: E402
    NcesSchoolDistrictRow,
    NcesSchoolDistrictsPipeline,
    find_nces_files,
    _float_cell,
    _int_cell,
    _record_to_jsonb,
    _str_cell,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


# Raw NCES CCD headers consumed by NCESSchoolDistrictIngestion.parse_csv_to_dataframe.
_DIRECTORY_HEADER = (
    "LEAID,LEA_NAME,ST,FIPST,LSTREET1,LCITY,LZIP,PHONE,WEBSITE,"
    "LEA_TYPE_TEXT,OPERATIONAL_SCHOOLS"
)
_MEMBERSHIP_HEADER = "LEAID,ST,FIPST,STUDENT_COUNT"
_STAFF_HEADER = "LEAID,ST,FIPST,STAFF,STAFF_COUNT"


def _write_cache(tmp_path: Path) -> Path:
    cache = tmp_path / "nces"
    cache.mkdir()
    (cache / "nces_directory.csv").write_text(
        _DIRECTORY_HEADER + "\n"
        "0100005,Albertville City,AL,01,100 Main St,Albertville,35950,256-555-0100,"
        "http://acboe.org/,Local school district,5\n"
        "0600001,Big City USD,CA,06,1 Plaza,Sacramento,95814,916-555-0001,"
        "https://bigcity.edu,Local school district,42\n"
    )
    (cache / "nces_membership.csv").write_text(
        _MEMBERSHIP_HEADER + "\n"
        "0100005,AL,01,1200\n"
        "0600001,CA,06,50000\n"
    )
    (cache / "nces_staff.csv").write_text(
        _STAFF_HEADER + "\n"
        "0100005,AL,01,Teachers,75.0\n"
        "0100005,AL,01,Teachers,5.0\n"  # same category -> summed by groupby
        "0600001,CA,06,Teachers,2500.0\n"
    )
    return cache


def test_str_cell_trims_and_drops_nan():
    assert _str_cell("  hello  ") == "hello"
    assert _str_cell("") is None
    assert _str_cell("   ") is None
    assert _str_cell(None) is None
    assert _str_cell("nan") is None
    assert _str_cell("abcdef", 3) == "abc"


def test_int_and_float_cells():
    import math

    assert _int_cell("42") == 42
    assert _int_cell("42.0") == 42
    assert _int_cell("") is None
    assert _int_cell("nope") is None
    assert _float_cell("1.5") == 1.5
    assert _float_cell(None) is None
    assert _float_cell("nope") is None
    # The legacy helper relies on _scalar/pd.isna, so the literal string "nan"
    # parses to a float NaN (only true NaN/None inputs are coerced to None).
    assert math.isnan(_float_cell("nan"))


def test_record_to_jsonb_is_nan_safe():
    out = _record_to_jsonb({"a": 1, "b": float("nan"), "c": "x"})
    assert '"b": null' in out
    assert '"a": 1' in out
    assert '"c": "x"' in out


def test_schema_accepts_valid_directory_row():
    row = NcesSchoolDistrictRow.model_validate({
        "source": "nces_school_districts",
        "source_version": "2024-25",
        "natural_key": "directory:0100005",
        "dataset": "directory",
        "nces_id": "0100005",
        "state_code": "AL",
        "state_fips": "01",
        "school_year": "2024-25",
        "district_name": "Albertville City",
        "num_schools": 5,
        "raw_json": "{}",
    })
    assert row.nces_id == "0100005"
    assert row.state_code == "AL"
    assert row.num_schools == 5
    # Cross-dataset fields default to None.
    assert row.total_students is None
    assert row.staff_category is None


def test_schema_rejects_missing_nces_id_and_overlong_state():
    base = {
        "source": "nces_school_districts",
        "source_version": "2024-25",
        "natural_key": "x",
        "dataset": "directory",
        "nces_id": "0100005",
        "state_code": "AL",
        "school_year": "2024-25",
    }
    with pytest.raises(Exception):
        NcesSchoolDistrictRow.model_validate({**base, "nces_id": ""})  # empty id
    with pytest.raises(Exception):
        NcesSchoolDistrictRow.model_validate({**base, "state_code": "ALA"})  # 3 chars
    with pytest.raises(Exception):
        NcesSchoolDistrictRow.model_validate({**base, "extra_col": "x"})  # extra=forbid


def test_pipeline_metadata():
    p = NcesSchoolDistrictsPipeline()
    assert p.source == "nces_school_districts"
    assert p.batch_size == 2_000
    assert p.row_schema is NcesSchoolDistrictRow


def test_find_nces_files_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_nces_files(tmp_path, {"directory"})


def test_find_nces_files_returns_requested_subset(tmp_path):
    cache = _write_cache(tmp_path)
    found = find_nces_files(cache, {"directory", "membership"})
    assert set(found) == {"directory", "membership"}
    assert found["directory"].name == "nces_directory.csv"


def test_extract_yields_validated_envelope_rows(tmp_path):
    cache = _write_cache(tmp_path)
    p = NcesSchoolDistrictsPipeline(path=cache, school_year="2024-25")

    async def collect():
        out = []
        async for raw in p.extract(_ctx()):
            row = p.validate(raw)
            assert row is not None, f"rejected: {raw}"
            out.append(row)
        return out

    rows = asyncio.run(collect())
    by_dataset: dict[str, list] = {"directory": [], "membership": [], "staff": []}
    for r in rows:
        by_dataset[r.dataset].append(r)

    # 2 directory + 2 membership + 2 staff (the two AL Teachers rows summed into one)
    assert len(by_dataset["directory"]) == 2
    assert len(by_dataset["membership"]) == 2
    assert len(by_dataset["staff"]) == 2

    d = by_dataset["directory"][0]
    assert d.nces_id == "0100005"
    assert d.district_name == "Albertville City"
    assert d.state_code == "AL"
    assert d.num_schools == 5
    assert d.school_year == "2024-25"
    assert d.source == "nces_school_districts"
    assert d.source_version == "2024-25"
    assert d.natural_key == "directory:0100005"
    assert d.raw_json is not None

    m = next(x for x in by_dataset["membership"] if x.nces_id == "0600001")
    assert m.total_students == 50000

    al_staff = next(x for x in by_dataset["staff"] if x.nces_id == "0100005")
    assert al_staff.staff_category == "Teachers"
    assert al_staff.staff_count == 80.0  # 75 + 5 summed by groupby
    assert al_staff.natural_key == "staff:0100005:2024-25:Teachers"


def test_extract_respects_states_filter(tmp_path):
    cache = _write_cache(tmp_path)
    p = NcesSchoolDistrictsPipeline(path=cache, states=["CA"], school_year="2024-25")

    async def collect():
        return [r async for r in p.extract(_ctx())]

    rows = asyncio.run(collect())
    assert rows  # non-empty
    assert all(r["state_code"] == "CA" for r in rows)


def test_extract_respects_limit(tmp_path):
    cache = _write_cache(tmp_path)
    p = NcesSchoolDistrictsPipeline(path=cache, school_year="2024-25", limit=1)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    rows = asyncio.run(collect())
    assert len(rows) == 1
    assert rows[0]["dataset"] == "directory"

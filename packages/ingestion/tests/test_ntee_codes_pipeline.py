"""Unit tests for the NTEE codes pipeline (bronze.bronze_ntee_codes)."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest


from ingestion.ntee.codes import (  # noqa: E402
    NteeCodesPipeline,
    NteeCodesRow,
    VENDORED_CSV,
    _is_missing,
    _safe_str,
    resolve_source_path,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_csv(path: Path, rows: list[dict]) -> Path:
    if not rows:
        path.write_text("ntee_code,description,parent_code,ntee_type\n")
        return path
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    return path


def _write_parquet(path: Path, rows: list[dict]) -> Path:
    pd.DataFrame(rows).to_parquet(path)
    return path


def test_safe_str_trims_and_truncates():
    assert _safe_str("  hello  ") == "hello"
    assert _safe_str("") is None
    assert _safe_str("   ") is None
    assert _safe_str(None) is None
    assert _safe_str(float("nan")) is None
    assert _safe_str("abcdef", 3) == "abc"


def test_is_missing():
    assert _is_missing(None) is True
    assert _is_missing(float("nan")) is True
    assert _is_missing("") is True
    assert _is_missing("   ") is True
    assert _is_missing("A20") is False


def test_ntee_row_schema_enforces_max_lengths():
    r = NteeCodesRow(
        source="ntee_codes",
        source_version="bronze_ntee_codes",
        natural_key="A20",
        code="A20",
        name="Arts Multipurpose",
        description="Arts Multipurpose",
        cause_type="ntee",
        parent_code="A",
        category="major",
        subcategory=None,
        code_source="irs",
    )
    assert r.code == "A20"
    assert r.code_source == "irs"

    # code must be max 100 chars
    with pytest.raises(Exception):
        NteeCodesRow(
            source="ntee_codes",
            source_version="v",
            natural_key="x",
            code="x" * 101,
            name="n",
            cause_type="ntee",
            code_source="irs",
        )


def test_ntee_row_requires_name_and_code_source():
    # empty name rejected (NOT NULL / min_length=1)
    with pytest.raises(Exception):
        NteeCodesRow(
            source="ntee_codes",
            source_version="v",
            natural_key="A",
            code="A",
            name="",
            cause_type="ntee",
            code_source="irs",
        )
    # missing code_source rejected
    with pytest.raises(Exception):
        NteeCodesRow(
            source="ntee_codes",
            source_version="v",
            natural_key="A",
            code="A",
            name="Arts",
            cause_type="ntee",
        )


def test_pipeline_metadata():
    p = NteeCodesPipeline()
    assert p.source == "ntee_codes"
    assert p.batch_size == 1000
    assert p.row_schema is NteeCodesRow


def test_resolve_source_path_explicit_wins(tmp_path):
    explicit = tmp_path / "explicit.csv"
    explicit.write_text("ntee_code\nA\n")
    assert resolve_source_path(explicit) == explicit


def test_resolve_source_path_cache_dir_preferred(tmp_path, monkeypatch):
    import ingestion.ntee.codes as cp

    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    cached_csv = tmp_path / "causes_ntee_codes.csv"
    cached_csv.write_text("ntee_code,description,parent_code,ntee_type\nA,Arts,,major\n")
    assert resolve_source_path() == cached_csv


def test_resolve_source_path_falls_back_to_vendored(tmp_path, monkeypatch):
    import ingestion.ntee.codes as cp

    # Empty cache dir → vendored CSV.
    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    assert resolve_source_path() == VENDORED_CSV


def test_resolve_source_path_prefers_parquet_over_csv(tmp_path, monkeypatch):
    import ingestion.ntee.codes as cp

    monkeypatch.setattr(cp, "CACHE_DIR", tmp_path)
    (tmp_path / "causes_ntee_codes.csv").write_text("ntee_code\nA\n")
    parquet = tmp_path / "causes_ntee_codes.parquet"
    pd.DataFrame([{"ntee_code": "A"}]).to_parquet(parquet)
    assert resolve_source_path() == parquet


def test_extract_from_csv_yields_validated_rows(tmp_path):
    path = _write_csv(
        tmp_path / "causes_ntee_codes.csv",
        [
            {"ntee_code": "A", "description": "Arts", "parent_code": "", "ntee_type": "major"},
            {"ntee_code": "A20", "description": "Arts Multipurpose", "parent_code": "A", "ntee_type": "division"},
            {"ntee_code": "", "description": "junk", "parent_code": "", "ntee_type": ""},  # dropped
        ],
    )
    p = NteeCodesPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["code"] == "A"
    assert extracted[0]["cause_type"] == "ntee"
    assert extracted[0]["code_source"] == "irs"
    assert extracted[0]["parent_code"] is None
    assert extracted[1]["code"] == "A20"
    assert extracted[1]["parent_code"] == "A"
    assert extracted[1]["natural_key"] == "A20"
    assert extracted[1]["source_version"] == "causes_ntee_codes"
    # RAW landing only — no derived cause_breadcrumb in the extracted row.
    assert "cause_breadcrumb" not in extracted[1]

    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_from_parquet_yields_validated_rows(tmp_path):
    path = _write_parquet(
        tmp_path / "causes_ntee_codes.parquet",
        [
            {"ntee_code": "B", "description": "Education", "parent_code": None, "ntee_type": "major"},
        ],
    )
    p = NteeCodesPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    assert extracted[0]["code"] == "B"
    assert extracted[0]["parent_code"] is None


def test_extract_vendored_seed_is_loadable():
    """The package-vendored seed CSV must be parseable and validate cleanly."""
    p = NteeCodesPipeline(path=VENDORED_CSV)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    # Seed ships 26 major-group codes (A-Z).
    assert len(extracted) == 26
    codes = {row["code"] for row in extracted}
    assert codes == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    for raw in extracted:
        assert p.validate(raw) is not None


def test_limit_caps_extracted_rows(tmp_path):
    rows = [
        {"ntee_code": f"X{i}", "description": f"d{i}", "parent_code": "", "ntee_type": "t"}
        for i in range(10)
    ]
    path = _write_csv(tmp_path / "causes_ntee_codes.csv", rows)
    p = NteeCodesPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

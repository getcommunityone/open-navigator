"""Unit tests for the NTEE codes pipeline refactor."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

_NTEE_DIR = Path(__file__).resolve().parents[1] / "scripts" / "datasources" / "ntee"
sys.path.insert(0, str(_NTEE_DIR))

from codes_pipeline import (  # noqa: E402
    NteeCodesPipeline,
    NteeCodesRow,
    _is_missing,
    _safe_str,
    build_breadcrumb,
    find_latest_parquet,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


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


def test_build_breadcrumb_top_level_returns_name():
    code_lookup = {"A": "Arts"}
    parent_lookup = {"A": None}
    assert build_breadcrumb("A", None, code_lookup, parent_lookup) == "Arts"


def test_build_breadcrumb_walks_parent_chain():
    code_lookup = {"A": "Arts", "A20": "Arts Multipurpose", "A23": "Cultural"}
    parent_lookup = {"A": None, "A20": "A", "A23": "A20"}
    bc = build_breadcrumb("A23", "A20", code_lookup, parent_lookup)
    assert bc == "Arts > Arts Multipurpose > Cultural"


def test_ntee_row_schema_enforces_max_lengths():
    r = NteeCodesRow(
        source="ntee_codes",
        source_version="causes_ntee_codes",
        natural_key="A20",
        code="A20",
        name="Arts Multipurpose",
        description="Arts Multipurpose",
        cause_type="ntee",
        parent_code="A",
        category="major",
        subcategory=None,
        cause_breadcrumb="Arts > Arts Multipurpose",
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


def test_find_latest_parquet_raises_when_no_files(tmp_path, monkeypatch):
    import codes_pipeline as cp
    monkeypatch.setattr(cp, "GOLD_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_latest_parquet()


def test_find_latest_parquet_returns_most_recent(tmp_path, monkeypatch):
    import codes_pipeline as cp
    monkeypatch.setattr(cp, "GOLD_DIR", tmp_path)
    (tmp_path / "causes_ntee_codes.parquet").write_text("")
    (tmp_path / "causes_ntee_codes_20260101.parquet").write_text("")
    latest = find_latest_parquet()
    assert latest.name == "causes_ntee_codes_20260101.parquet"


def test_extract_yields_validated_rows(tmp_path):
    path = _write_parquet(
        tmp_path / "causes_ntee_codes.parquet",
        [
            {"ntee_code": "A", "description": "Arts", "parent_code": None, "ntee_type": "major"},
            {"ntee_code": "A20", "description": "Arts Multipurpose", "parent_code": "A", "ntee_type": "division"},
            {"ntee_code": "", "description": "junk", "parent_code": None, "ntee_type": None},  # dropped
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
    assert extracted[0]["cause_breadcrumb"] == "Arts"
    assert extracted[1]["code"] == "A20"
    assert extracted[1]["cause_breadcrumb"] == "Arts > Arts Multipurpose"
    assert extracted[1]["natural_key"] == "A20"
    assert extracted[1]["source_version"] == "causes_ntee_codes"

    for raw in extracted:
        assert p.validate(raw) is not None


def test_limit_caps_extracted_rows(tmp_path):
    rows = [
        {"ntee_code": f"X{i}", "description": f"d{i}", "parent_code": None, "ntee_type": "t"}
        for i in range(10)
    ]
    path = _write_parquet(tmp_path / "causes_ntee_codes.parquet", rows)
    p = NteeCodesPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

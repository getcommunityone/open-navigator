"""Unit tests for the IRS EO-BMF pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import pytest

from ingestion.irs.bmf import (  # noqa: E402
    IrsBmfPipeline,
    IrsBmfRow,
    _safe_int,
    _safe_str,
    find_latest_parquet,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_safe_str_trims_and_truncates():
    assert _safe_str("  hello  ") == "hello"
    assert _safe_str("") is None
    assert _safe_str("   ") is None
    assert _safe_str(None) is None
    assert _safe_str(float("nan")) is None
    assert _safe_str("abcdef", 3) == "abc"


def test_safe_int_coerces_and_nulls():
    assert _safe_int("123") == 123
    assert _safe_int(456) == 456
    assert _safe_int("1000.0") == 1000
    assert _safe_int("not-a-number") is None
    assert _safe_int(None) is None
    assert _safe_int("") is None


def test_irs_bmf_row_schema_enforces_max_lengths():
    r = IrsBmfRow(
        source="irs_bmf",
        source_version="all_regions_combined",
        natural_key="123456789",
        ein="123456789",
        name="Example Charity",
        state_code="AL",
        asset_amt=1000,
        income_amt=500,
        revenue_amt=750,
    )
    assert r.ein == "123456789"
    assert r.state_code == "AL"
    assert r.asset_amt == 1000

    # state_code must be max 2 chars
    with pytest.raises(Exception):
        IrsBmfRow(
            source="irs_bmf",
            source_version="v",
            natural_key="x",
            ein="123",
            state_code="ALA",
        )


def test_irs_bmf_row_requires_ein():
    with pytest.raises(Exception):
        IrsBmfRow(
            source="irs_bmf",
            source_version="v",
            natural_key="x",
            ein="",
        )


def test_pipeline_metadata():
    p = IrsBmfPipeline()
    assert p.source == "irs_bmf"
    assert p.batch_size == 50_000
    assert p.row_schema is IrsBmfRow


def test_find_latest_parquet_raises_when_no_files(tmp_path, monkeypatch):
    import ingestion.irs.bmf as bmf
    monkeypatch.setattr(bmf, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_latest_parquet()


def test_find_latest_parquet_prefers_combined(tmp_path, monkeypatch):
    import ingestion.irs.bmf as bmf
    monkeypatch.setattr(bmf, "CACHE_DIR", tmp_path)
    pd.DataFrame({"ein": ["1"]}).to_parquet(tmp_path / "region1.parquet")
    pd.DataFrame({"ein": ["2"]}).to_parquet(tmp_path / "all_regions_combined.parquet")
    latest = find_latest_parquet()
    assert latest.name == "all_regions_combined.parquet"


def test_extract_yields_validated_rows(tmp_path):
    df = pd.DataFrame(
        [
            {
                "EIN": "123456789",
                "NAME": "Example Charity",
                "STATE": "AL",
                "CITY": "Birmingham",
                "ZIP": "35201",
                "NTEE_CD": "E20",
                "ASSET_AMT": "1000",
                "INCOME_AMT": "500",
                "REVENUE_AMT": "750",
            },
            {  # NULL ein -> dropped
                "EIN": "",
                "NAME": "No EIN Org",
                "STATE": "GA",
                "CITY": "Atlanta",
                "ZIP": "30301",
                "NTEE_CD": "",
                "ASSET_AMT": "",
                "INCOME_AMT": "",
                "REVENUE_AMT": "",
            },
            {
                "EIN": "987654321",
                "NAME": "Second Org",
                "STATE": "FL",
                "CITY": "Miami",
                "ZIP": "33101",
                "NTEE_CD": "P20",
                "ASSET_AMT": "bad",  # non-numeric -> NULL
                "INCOME_AMT": "200",
                "REVENUE_AMT": "300",
            },
        ]
    )
    path = tmp_path / "all_regions_combined.parquet"
    df.to_parquet(path)
    p = IrsBmfPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["ein"] == "123456789"
    assert extracted[0]["state_code"] == "AL"
    assert extracted[0]["zip_code"] == "35201"
    assert extracted[0]["asset_amt"] == 1000
    assert extracted[1]["ein"] == "987654321"
    assert extracted[1]["asset_amt"] is None  # coerced from "bad"
    assert extracted[1]["income_amt"] == 200

    # All extracted rows validate cleanly
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_limit_caps_extracted_rows(tmp_path):
    rows = [
        {"EIN": f"{i:09d}", "NAME": f"Org {i}", "STATE": "AL"}
        for i in range(10)
    ]
    path = tmp_path / "region1.parquet"
    pd.DataFrame(rows).to_parquet(path)

    p = IrsBmfPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

"""Unit tests for the FEC contributions pipeline refactor."""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

_FEC_DIR = Path(__file__).resolve().parents[1] / "scripts" / "datasources" / "fec"
sys.path.insert(0, str(_FEC_DIR))

from contributions_pipeline import (  # noqa: E402
    RAW_COLUMN_COUNT,
    ContributionRow,
    FecContributionsPipeline,
    detect_source_cycle,
    discover_input_files,
    normalize_text,
    parse_amount,
    parse_transaction_date,
    row_is_header,
)


# -- pure helpers ----------------------------------------------------------

def test_normalize_text_strips_and_returns_none_on_empty():
    assert normalize_text("  hello  ") == "hello"
    assert normalize_text("") is None
    assert normalize_text("   ") is None
    assert normalize_text(None) is None


def test_parse_transaction_date_accepts_mmddyyyy_only():
    assert parse_transaction_date("01152024") == date(2024, 1, 15)
    assert parse_transaction_date("12312023") == date(2023, 12, 31)
    assert parse_transaction_date("1/15/24") is None
    assert parse_transaction_date("garbage") is None
    assert parse_transaction_date("") is None
    assert parse_transaction_date(None) is None


def test_parse_amount_handles_valid_and_invalid():
    assert parse_amount("123.45") == Decimal("123.45")
    assert parse_amount("0") == Decimal("0")
    assert parse_amount("-50.25") == Decimal("-50.25")
    assert parse_amount("not-a-number") is None
    assert parse_amount("") is None
    assert parse_amount(None) is None


def test_detect_source_cycle_finds_year_in_path():
    assert detect_source_cycle(Path("/x/y/2024/by_date")) == 2024
    assert detect_source_cycle(Path("/x/y/foo")) is None
    # When multiple 4-digit components exist, return the deepest (reversed iteration)
    assert detect_source_cycle(Path("/x/2020/y/2024/by_date")) == 2024


def test_row_is_header_detects_cmte_id_first_column():
    row = ["cmte_id"] + [""] * (RAW_COLUMN_COUNT - 1)
    assert row_is_header(row)
    row2 = ["committee_id"] + [""] * (RAW_COLUMN_COUNT - 1)
    assert row_is_header(row2)
    not_header = ["C00100001"] + [""] * (RAW_COLUMN_COUNT - 1)
    assert not row_is_header(not_header)
    wrong_length = ["cmte_id"]
    assert not row_is_header(wrong_length)


def test_discover_input_files_raises_on_missing_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        discover_input_files(missing)


def test_discover_input_files_finds_txt_shards(tmp_path):
    by_date = tmp_path / "by_date"
    by_date.mkdir()
    (by_date / "itcont_a.txt").write_text("")
    (by_date / "itcont_b.txt").write_text("")
    (by_date / "not_a_shard.csv").write_text("")
    files = discover_input_files(by_date)
    assert sorted(f.name for f in files) == ["itcont_a.txt", "itcont_b.txt"]


# -- pipeline shape --------------------------------------------------------

def test_pipeline_metadata():
    p = FecContributionsPipeline(input_dir=Path("/nonexistent"))
    assert p.source == "fec_contributions"
    assert p.batch_size == 5000
    assert p.row_schema is ContributionRow


def test_contribution_row_accepts_full_payload():
    r = ContributionRow(
        source="fec_contributions",
        source_version="2024",
        natural_key="abc123",
        contribution_id="abc123",
        committee_id="C00100001",
        contributor_name="Doe, Jane",
        transaction_date=date(2024, 1, 15),
        transaction_date_raw="01152024",
        contribution_amount=Decimal("500.00"),
        contribution_amount_raw="500.00",
        source_file="/tmp/x.txt",
        source_cycle=2024,
    )
    assert r.contribution_id == "abc123"
    assert r.contribution_amount == Decimal("500.00")
    assert r.transaction_date == date(2024, 1, 15)


def test_contribution_row_requires_contribution_id():
    with pytest.raises(Exception):
        ContributionRow(
            source="fec_contributions",
            source_version="2024",
            natural_key="x",
            contribution_id="",  # required min_length=1
            source_file="/tmp/x.txt",
        )


def test_extract_streams_pipe_delimited_file(tmp_path):
    """Smoke test: extract a tiny synthetic shard and confirm row shape."""
    import asyncio
    from datetime import datetime, timezone
    from core_lib.pipeline.schemas import PipelineContext

    by_date = tmp_path / "2024" / "by_date"
    by_date.mkdir(parents=True)
    shard = by_date / "itcont_test.txt"
    # 21 pipe-delimited columns matching SOURCE_COLUMNS order
    row = [
        "C00100001", "A", "Q1", "P", "img1", "15", "IND",
        "Doe, Jane", "Boston", "MA", "02101", "Acme", "Engineer",
        "01152024", "500.00", "other1", "txn1", "f1", "M", "memo",
        "sub-id-1",
    ]
    shard.write_text("|".join(row) + "\n")

    p = FecContributionsPipeline(input_dir=by_date)
    ctx = PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))

    async def collect():
        out = []
        async for raw in p.extract(ctx):
            out.append(raw)
        return out

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    r = extracted[0]
    assert r["contribution_id"] == "sub-id-1"
    assert r["contributor_name"] == "Doe, Jane"
    assert r["transaction_date"] == date(2024, 1, 15)
    assert r["contribution_amount"] == Decimal("500.00")
    assert r["source_cycle"] == 2024
    # And it must validate cleanly through the pydantic schema
    row_obj = p.validate(r)
    assert row_obj is not None
    assert row_obj.contribution_id == "sub-id-1"

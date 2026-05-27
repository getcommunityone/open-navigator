"""Unit tests for the GSA domains pipeline refactor."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_GSA_DIR = Path(__file__).resolve().parents[1] / "scripts" / "datasources" / "gsa"
sys.path.insert(0, str(_GSA_DIR))

from domains_pipeline import (  # noqa: E402
    DomainRow,
    GsaDomainsPipeline,
    _safe_str,
    find_latest_csv,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_safe_str_trims_and_truncates():
    assert _safe_str("  hello  ") == "hello"
    assert _safe_str("") is None
    assert _safe_str("   ") is None
    assert _safe_str(None) is None
    assert _safe_str("abcdef", 3) == "abc"


def test_domain_row_schema_enforces_max_lengths():
    r = DomainRow(
        source="gsa_domains",
        source_version="dotgov_domains_20260507",
        natural_key="example.gov",
        domain_name="example.gov",
        domain_type="Federal",
        agency="GSA",
        organization="Some Sub",
        city="Washington",
        state="DC",
        security_contact="sec@example.gov",
    )
    assert r.domain_name == "example.gov"
    assert r.state == "DC"

    # state must be max 2 chars
    with pytest.raises(Exception):
        DomainRow(
            source="gsa_domains",
            source_version="v",
            natural_key="x",
            domain_name="x.gov",
            state="DCA",
        )


def test_domain_row_requires_domain_name():
    with pytest.raises(Exception):
        DomainRow(
            source="gsa_domains",
            source_version="v",
            natural_key="x",
            domain_name="",
        )


def test_find_latest_csv_raises_when_no_files(tmp_path, monkeypatch):
    import domains_pipeline as dp
    monkeypatch.setattr(dp, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_latest_csv()


def test_find_latest_csv_returns_most_recent(tmp_path, monkeypatch):
    import domains_pipeline as dp
    monkeypatch.setattr(dp, "CACHE_DIR", tmp_path)
    (tmp_path / "dotgov_domains_20260101.csv").write_text("")
    (tmp_path / "dotgov_domains_20260507.csv").write_text("")
    (tmp_path / "dotgov_domains_20240101.csv").write_text("")
    latest = find_latest_csv()
    assert latest.name == "dotgov_domains_20260507.csv"


def test_extract_yields_validated_rows(tmp_path):
    csv_path = tmp_path / "dotgov_domains_20260507.csv"
    csv_path.write_text(
        "Domain name,Domain type,Organization name,Suborganization name,City,State,Security Contact Email\n"
        "example.gov,Federal,GSA,IT Office,Washington,DC,sec@example.gov\n"
        ",Federal,X,,X,XX,\n"  # NULL domain_name → dropped
        "city.gov,City,Boston,,Boston,MA,it@city.gov\n"
    )
    p = GsaDomainsPipeline(csv_path=csv_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["domain_name"] == "example.gov"
    assert extracted[0]["state"] == "DC"
    assert extracted[0]["security_contact"] == "sec@example.gov"
    assert extracted[1]["domain_name"] == "city.gov"

    # All extracted rows validate cleanly
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_limit_caps_extracted_rows(tmp_path):
    csv_path = tmp_path / "dotgov_domains_test.csv"
    rows = ["Domain name,Domain type,Organization name,Suborganization name,City,State,Security Contact Email"]
    for i in range(10):
        rows.append(f"x{i}.gov,Federal,Agency{i},,City{i},DC,a@b.gov")
    csv_path.write_text("\n".join(rows) + "\n")

    p = GsaDomainsPipeline(csv_path=csv_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3


def test_pipeline_metadata():
    p = GsaDomainsPipeline()
    assert p.source == "gsa_domains"
    assert p.batch_size == 5000
    assert p.row_schema is DomainRow

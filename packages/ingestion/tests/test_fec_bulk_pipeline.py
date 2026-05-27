"""Unit tests for the FEC bulk-data manifest pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion.fec.bulk import (  # noqa: E402
    FecBulkPipeline,
    FecBulkRow,
    discover_files,
    filter_files,
    parse_file_info,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_parse_file_info_year_prefix_and_path(tmp_path):
    bulk = tmp_path / "bulk-downloads"
    fi = parse_file_info("/files/bulk-downloads/2024/indiv24.zip", "indiv24.zip", bulk)
    assert fi["type"] == "indiv"
    assert fi["category"] == "contributions-by-individuals"
    assert fi["year"] == "2024"
    assert fi["url"] == "https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip"
    assert fi["path"] == bulk / "contributions-by-individuals" / "2024" / "indiv24.zip"


def test_parse_file_info_header_special_and_summary(tmp_path):
    bulk = tmp_path / "bulk-downloads"
    header = parse_file_info(
        "/files/bulk-downloads/cm_header_file.csv", "cm_header_file.csv", bulk
    )
    assert header["type"] == "header"
    assert header["category"] == "headers"
    assert header["year"] is None

    special = parse_file_info(
        "/files/bulk-downloads/lobbyist.csv", "lobbyist.csv", bulk
    )
    assert special["type"] == "special"
    assert special["category"] == "special-files"

    summary = parse_file_info(
        "/files/bulk-downloads/2024/candidate_summary_2024.csv",
        "candidate_summary_2024.csv",
        bulk,
    )
    assert summary["type"] == "candidate_summary"
    assert summary["category"] == "summary-reports"

    # absolute href is passed through unchanged
    abs_fi = parse_file_info(
        "https://x/files/bulk-downloads/2020/cn20.zip", "cn20.zip", bulk
    )
    assert abs_fi["url"] == "https://x/files/bulk-downloads/2020/cn20.zip"


def test_filter_files_by_year_keeps_yearless():
    files = [
        {"year": "2024", "type": "indiv", "filename": "indiv24.zip"},
        {"year": "2020", "type": "cn", "filename": "cn20.zip"},
        {"year": None, "type": "header", "filename": "cm_header_file.csv"},
    ]
    kept = filter_files(files, years=["2024"])
    names = {f["filename"] for f in kept}
    assert names == {"indiv24.zip", "cm_header_file.csv"}


def test_filter_files_by_type_always_keeps_header_special():
    files = [
        {"year": "2024", "type": "indiv", "filename": "indiv24.zip"},
        {"year": "2024", "type": "cn", "filename": "cn24.zip"},
        {"year": None, "type": "header", "filename": "cm_header_file.csv"},
        {"year": None, "type": "special", "filename": "lobbyist.csv"},
    ]
    kept = filter_files(files, file_types=["indiv"])
    names = {f["filename"] for f in kept}
    assert names == {"indiv24.zip", "cm_header_file.csv", "lobbyist.csv"}


def test_fec_bulk_row_schema_accepts_valid():
    r = FecBulkRow(
        source="fec_bulk",
        source_version="20260527",
        natural_key="https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip",
        url="https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip",
        filename="indiv24.zip",
        dest_path="/x/contributions-by-individuals/2024/indiv24.zip",
        file_type="indiv",
        category="contributions-by-individuals",
        year=2024,
    )
    assert r.url.endswith("indiv24.zip")
    assert r.year == 2024
    assert r.file_type == "indiv"


def test_fec_bulk_row_schema_rejects_missing_required():
    # empty url violates min_length
    with pytest.raises(Exception):
        FecBulkRow(
            source="fec_bulk",
            source_version="20260527",
            natural_key="x",
            url="",
            filename="indiv24.zip",
            dest_path="/x/indiv24.zip",
        )
    # extra field forbidden by RawRow config
    with pytest.raises(Exception):
        FecBulkRow(
            source="fec_bulk",
            source_version="20260527",
            natural_key="x",
            url="https://u",
            filename="f.zip",
            dest_path="/x/f.zip",
            bogus="nope",
        )


def test_pipeline_metadata():
    p = FecBulkPipeline()
    assert p.source == "fec_bulk"
    assert p.batch_size == 1000
    assert p.row_schema is FecBulkRow


_SYNTHETIC_HTML = """
<html><body>
  <a href="/files/bulk-downloads/2024/indiv24.zip">indiv24</a>
  <a href="/files/bulk-downloads/2024/cn24.zip">cn24</a>
  <a href="/files/bulk-downloads/cm_header_file.csv">header</a>
  <a href="/data/some-other-link">ignored not-bulk</a>
  <a href="/files/bulk-downloads/2020/cn20.zip">cn20</a>
</body></html>
"""


def test_extract_roundtrip_and_limit(tmp_path, monkeypatch):
    pytest.importorskip("bs4")
    import ingestion.fec.bulk as mod

    # Synthetic FEC index written to a tmp file, served via fetch_bulk_index.
    html_file = tmp_path / "fec_index.html"
    html_file.write_text(_SYNTHETIC_HTML)
    monkeypatch.setattr(mod, "fetch_bulk_index", lambda: html_file.read_text())

    base = tmp_path / "fec_data"
    p = FecBulkPipeline(path=base)

    async def collect(pipe):
        return [r async for r in pipe.extract(_ctx())]

    extracted = asyncio.run(collect(p))
    # 4 bulk-download anchors discovered; the non-bulk link is ignored.
    assert len(extracted) == 4
    by_name = {e["filename"]: e for e in extracted}
    assert set(by_name) == {"indiv24.zip", "cn24.zip", "cm_header_file.csv", "cn20.zip"}
    assert by_name["indiv24.zip"]["category"] == "contributions-by-individuals"
    assert by_name["indiv24.zip"]["year"] == 2024
    assert by_name["cm_header_file.csv"]["year"] is None
    assert by_name["indiv24.zip"]["dest_path"].endswith(
        str(Path("contributions-by-individuals") / "2024" / "indiv24.zip")
    )

    # Every extracted row validates cleanly.
    for raw in extracted:
        assert p.validate(raw) is not None

    # limit caps the number of extracted rows.
    p_limited = FecBulkPipeline(path=base, limit=2)
    assert len(asyncio.run(collect(p_limited))) == 2


def test_discover_files_ignores_non_bulk_links(tmp_path):
    pytest.importorskip("bs4")
    bulk = tmp_path / "bulk-downloads"
    files = discover_files(_SYNTHETIC_HTML, bulk)
    assert len(files) == 4
    assert all("/files/bulk-downloads/" in f["url"] for f in files)

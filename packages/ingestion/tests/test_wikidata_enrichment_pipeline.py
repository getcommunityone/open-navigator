"""Unit tests for the Wikidata enrichment bronze loader (LAND layer)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ingestion.wikidata.enrichment as mod
from ingestion.wikidata.enrichment import (
    COLUMNS,
    WikidataEnrichmentPipeline,
    WikidataEnrichmentRow,
    find_enrichment_files,
    _s,
)
from core_lib.pipeline.schemas import PipelineContext


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_cache(cache_dir: Path, usps: str, jtype: str, rows: list[dict]) -> Path:
    d = cache_dir / usps
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"wikidata_enrichment_{jtype}.json"
    p.write_text(json.dumps({
        "source": "wikidata", "state_code": usps, "jurisdiction_type": jtype,
        "fetched_at": "2026-05-27T00:00:00+00:00", "rows": rows,
    }))
    return p


def test_s_helper():
    assert _s("  x ") == "x"
    assert _s("") is None
    assert _s(None) is None
    assert _s(123) == "123"


def test_columns_align_with_schema():
    # Every insert column (except the envelope-free ones) is a Row field.
    for c in COLUMNS:
        assert c in WikidataEnrichmentRow.model_fields, c


def test_schema_accept_and_reject():
    ok = WikidataEnrichmentRow.model_validate({
        "source": "wikidata_enrichment", "source_version": "v", "natural_key": "CA:county:Q1",
        "state_code": "CA", "jurisdiction_type": "county", "wikidata_id": "Q1",
        "population": "12345", "fips_code": "06001",
    })
    assert ok.wikidata_id == "Q1" and ok.population == "12345"
    with pytest.raises(Exception):  # missing required wikidata_id
        WikidataEnrichmentRow.model_validate({
            "source": "s", "source_version": "v", "natural_key": "x",
            "state_code": "CA", "jurisdiction_type": "county", "wikidata_id": "",
        })
    with pytest.raises(Exception):  # overlong state_code
        WikidataEnrichmentRow.model_validate({
            "source": "s", "source_version": "v", "natural_key": "x",
            "state_code": "CAL", "jurisdiction_type": "county", "wikidata_id": "Q1",
        })


def test_pipeline_metadata():
    p = WikidataEnrichmentPipeline()
    assert p.source == "wikidata_enrichment"
    assert p.row_schema is WikidataEnrichmentRow


def test_find_enrichment_files_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_enrichment_files(tmp_path)


def test_extract_roundtrip_and_validate(tmp_path):
    _write_cache(tmp_path, "CA", "county", [
        {"wikidata_id": "Q11", "item_label": "Alpha County", "fips_code": "06001",
         "population": "100", "latitude": "37.1", "official_website": "https://a.gov"},
        {"wikidata_id": "Q12", "item_label": "Beta County", "gnis_id": "999"},
        {"item_label": "no qid — dropped"},  # missing wikidata_id -> skipped
    ])
    p = WikidataEnrichmentPipeline(cache_dir=tmp_path)

    async def collect():
        out = []
        async for raw in p.extract(_ctx()):
            row = p.validate(raw)
            assert row is not None, raw
            out.append(row)
        return out

    rows = asyncio.run(collect())
    assert len(rows) == 2  # third dropped
    first = rows[0]
    assert first.wikidata_id == "Q11"
    assert first.state_code == "CA" and first.jurisdiction_type == "county"
    assert first.fips_code == "06001" and first.population == "100"
    assert first.natural_key == "CA:county:Q11"
    assert first.fetched_at == "2026-05-27T00:00:00+00:00"
    assert first.source == "wikidata_enrichment"


def test_extract_respects_limit(tmp_path):
    _write_cache(tmp_path, "TX", "municipality", [
        {"wikidata_id": "Q1"}, {"wikidata_id": "Q2"}, {"wikidata_id": "Q3"},
    ])
    p = WikidataEnrichmentPipeline(cache_dir=tmp_path, limit=2)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    assert len(asyncio.run(collect())) == 2

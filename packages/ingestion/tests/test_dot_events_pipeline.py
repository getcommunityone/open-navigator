"""Unit tests for the DOT public events pipeline refactor."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest


from ingestion.dot.events import (  # noqa: E402
    DotEventRow,
    DotEventsPipeline,
    _parse_date_iso,
    _parse_scraped_at,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


# -- helpers --------------------------------------------------------------

def test_parse_date_iso_handles_full_iso_and_prefix():
    assert _parse_date_iso("2024-01-15") == date(2024, 1, 15)
    assert _parse_date_iso("2024-01-15T10:30:00") == date(2024, 1, 15)
    assert _parse_date_iso("garbage") is None
    assert _parse_date_iso(None) is None
    assert _parse_date_iso("") is None


def test_parse_scraped_at_normalizes_to_utc():
    out = _parse_scraped_at("2024-01-15T10:30:00Z")
    assert out.year == 2024 and out.tzinfo is not None
    # naive datetime → utc
    naive = datetime(2024, 1, 15, 10, 30, 0)
    out2 = _parse_scraped_at(naive)
    assert out2.tzinfo is not None
    # fallback to now() on invalid
    out3 = _parse_scraped_at("garbage")
    assert out3.tzinfo is not None


# -- schema ---------------------------------------------------------------

def test_dot_event_row_requires_state_usps_2chars():
    base = dict(
        source="dot_public_events", source_version="v",
        natural_key="abc", event_fingerprint="abc",
        scraped_at=datetime.now(timezone.utc),
    )
    DotEventRow(**base, state_usps="CA")  # ok
    with pytest.raises(Exception):
        DotEventRow(**base, state_usps="CAL")
    with pytest.raises(Exception):
        DotEventRow(**base, state_usps="C")


def test_dot_event_row_requires_fingerprint():
    with pytest.raises(Exception):
        DotEventRow(
            source="dot_public_events", source_version="v", natural_key="x",
            state_usps="CA", event_fingerprint="",
            scraped_at=datetime.now(timezone.utc),
        )


# -- pipeline -------------------------------------------------------------

def test_pipeline_metadata():
    p = DotEventsPipeline()
    assert p.source == "dot_public_events"
    assert p.batch_size == 500
    assert p.row_schema is DotEventRow


def test_extract_reads_jsonl_and_yields_validated_rows(tmp_path):
    jsonl = tmp_path / "unified_events.jsonl"
    rows = [
        {
            "event_fingerprint": "fp-1",
            "state_usps": "ca",
            "adapter": "ca_dot",
            "title": "Public hearing",
            "summary_text": "Meeting summary.",
            "list_page_url": "https://example.gov/events",
            "detail_url": "https://example.gov/events/1",
            "meeting_date": "2024-02-15",
            "meeting_date_raw": "Feb 15, 2024",
            "collateral": [{"label": "Agenda", "url": "x"}],
            "scraped_at": "2024-02-10T09:00:00Z",
        },
        {
            "event_fingerprint": "fp-2",
            "state_usps": "NY",
            "title": "Another event",
            "scraped_at": "2024-02-11T09:00:00Z",
        },
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    p = DotEventsPipeline(jsonl_path=jsonl)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["state_usps"] == "CA"  # uppercased
    assert extracted[0]["meeting_date"] == date(2024, 2, 15)
    assert extracted[0]["collateral"] == [{"label": "Agenda", "url": "x"}]
    assert extracted[0]["raw_record"]["event_fingerprint"] == "fp-1"
    # All validate cleanly
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_raises_on_missing_fingerprint(tmp_path):
    jsonl = tmp_path / "broken.jsonl"
    jsonl.write_text(json.dumps({"state_usps": "CA"}) + "\n")
    p = DotEventsPipeline(jsonl_path=jsonl)

    async def go():
        async for _ in p.extract(_ctx()):
            pass

    with pytest.raises(ValueError, match="missing event_fingerprint"):
        asyncio.run(go())


def test_extract_raises_on_bad_state(tmp_path):
    jsonl = tmp_path / "broken.jsonl"
    jsonl.write_text(json.dumps({"event_fingerprint": "x", "state_usps": "Cal"}) + "\n")
    p = DotEventsPipeline(jsonl_path=jsonl)

    async def go():
        async for _ in p.extract(_ctx()):
            pass

    with pytest.raises(ValueError, match="bad state_usps"):
        asyncio.run(go())


def test_extract_raises_on_missing_file(tmp_path):
    p = DotEventsPipeline(jsonl_path=tmp_path / "nope.jsonl")

    async def go():
        async for _ in p.extract(_ctx()):
            pass

    with pytest.raises(FileNotFoundError):
        asyncio.run(go())

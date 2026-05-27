"""Unit tests for the Google Civic officials pipeline refactor."""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone

import pytest

from ingestion.google_civic.officials import (  # noqa: E402
    GoogleCivicOfficialsPipeline,
    GoogleCivicOfficialsRow,
    _parse_election_day,
    _stable_id,
    _stable_key,
    _state_code_from_ocd_id,
    discover_cache_files,
    election_snapshot_records,
    voterinfo_records,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_pure_helpers():
    # _stable_id / _stable_key are deterministic.
    assert _stable_id("election", "abc") == _stable_id("election", "abc")
    assert _stable_id("election", "abc").startswith("ocd-election/")
    assert _stable_key("Google", " Civic ", None) == "google|civic|"

    # _state_code_from_ocd_id extracts the 2-letter code only when well-formed.
    assert _state_code_from_ocd_id("ocd-division/country:us/state:ma") == "MA"
    assert _state_code_from_ocd_id("ocd-division/country:us") is None
    assert _state_code_from_ocd_id(None) is None

    # _parse_election_day parses ISO prefixes, falls back to today otherwise.
    assert _parse_election_day("2026-11-03") == date(2026, 11, 3)
    assert _parse_election_day("2026-11-03T00:00:00Z") == date(2026, 11, 3)
    assert _parse_election_day("") == date.today()
    assert _parse_election_day("not-a-date") == date.today()


def test_row_schema_accepts_valid_record():
    r = GoogleCivicOfficialsRow(
        source="google_civic_officials",
        source_version="upcoming_elections_20260101T000000Z",
        natural_key="batch:election:ocd-election/x",
        scrape_batch_id="b1ed9a39-f6a5-44f7-8e4b-5e0f58d4c0da",
        record_type="election",
        ocd_id="ocd-election/x",
        election_name="General Election",
        election_date=date(2026, 11, 3),
        election_type="civic_calendar",
        election_status="confirmed",
        state_code="MA",
        raw_row={"id": "1"},
    )
    assert r.record_type == "election"
    assert r.state_code == "MA"
    assert r.raw_row == {"id": "1"}


def test_row_schema_rejects_bad_record_type_and_state():
    # record_type must be one of the CHECK set.
    with pytest.raises(Exception):
        GoogleCivicOfficialsRow(
            source="google_civic_officials",
            source_version="v",
            natural_key="x",
            scrape_batch_id="b",
            record_type="not_a_type",
        )
    # state_code is capped at 2 chars.
    with pytest.raises(Exception):
        GoogleCivicOfficialsRow(
            source="google_civic_officials",
            source_version="v",
            natural_key="x",
            scrape_batch_id="b",
            record_type="election",
            state_code="MAA",
        )


def test_row_schema_forbids_extra_fields():
    with pytest.raises(Exception):
        GoogleCivicOfficialsRow(
            source="google_civic_officials",
            source_version="v",
            natural_key="x",
            scrape_batch_id="b",
            record_type="election",
            bogus="nope",
        )


def test_pipeline_metadata():
    p = GoogleCivicOfficialsPipeline()
    assert p.source == "google_civic_officials"
    assert p.batch_size == 1000
    assert p.row_schema is GoogleCivicOfficialsRow


def test_election_snapshot_records_shape():
    records = election_snapshot_records(
        scrape_batch_id="batch-1",
        elections=[
            {"id": "2026", "name": "Statewide", "electionDay": "2026-11-03",
             "ocdDivisionId": "ocd-division/country:us/state:ma"},
        ],
        source_url="https://example/elections",
    )
    assert len(records) == 1
    rec = records[0]
    assert rec["record_type"] == "election"
    assert rec["election_type"] == "civic_calendar"
    assert rec["state_code"] == "MA"
    assert rec["election_date"] == date(2026, 11, 3)
    assert rec["source_url"] == "https://example/elections"


def test_voterinfo_records_explode_contests():
    payload = {
        "election_id": "9001",
        "election": {"id": "9001", "name": "City Election", "electionDay": "2026-05-12"},
        "contests": [
            {
                "type": "General",
                "office": "Mayor",
                "candidates": [
                    {"name": "Alice", "party": "Independent"},
                    {"name": "Bob", "party": "X"},
                ],
            },
            {"type": "Referendum", "referendumTitle": "Question 1"},
        ],
    }
    records = voterinfo_records(
        scrape_batch_id="batch-2",
        voter_info=payload,
        state_code="MA",
        jurisdiction_id="municipality_0177256",
        division_id="ocd-division/country:us/state:ma/place:boston",
        civic_address="Boston, MA",
    )
    kinds = [r["record_type"] for r in records]
    # 1 election + 2 candidacies + 1 ballot_measure
    assert kinds.count("election") == 1
    assert kinds.count("candidacy") == 2
    assert kinds.count("ballot_measure") == 1
    candidacy = next(r for r in records if r["record_type"] == "candidacy")
    assert candidacy["candidate_post"] == "Mayor"
    measure = next(r for r in records if r["record_type"] == "ballot_measure")
    assert measure["measure_title"] == "Question 1"


def test_discover_raises_when_cache_dir_missing(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        discover_cache_files(missing)


def test_extract_roundtrip_on_snapshot_file(tmp_path):
    snap = tmp_path / "elections" / "upcoming_elections_20260101T000000Z.json"
    snap.parent.mkdir(parents=True)
    snap.write_text(json.dumps({
        "source_url": "https://civicinfo.googleapis.com/elections",
        "elections": [
            {"id": "2026", "name": "Statewide", "electionDay": "2026-11-03",
             "ocdDivisionId": "ocd-division/country:us/state:ga"},
        ],
    }))

    p = GoogleCivicOfficialsPipeline(path=snap, scrape_batch_id="batch-x")

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    assert extracted[0]["record_type"] == "election"
    assert extracted[0]["state_code"] == "GA"
    assert extracted[0]["source"] == "google_civic_officials"
    # All extracted rows validate cleanly.
    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_voterinfo_roundtrip_and_limit(tmp_path):
    cache = tmp_path / "google_civic"
    vf_dir = cache / "MA" / "municipality" / "boston"
    vf_dir.mkdir(parents=True)
    payload = {
        "state_code": "MA",
        "jurisdiction_id": "municipality_0177256",
        "resolved_division_id": "ocd-division/country:us/state:ma/place:boston",
        "address": "Boston, MA",
        "election_id": "9001",
        "election": {"id": "9001", "name": "City Election", "electionDay": "2026-05-12"},
        "contests": [
            {"type": "General", "office": "Mayor",
             "candidates": [{"name": "Alice"}, {"name": "Bob"}, {"name": "Carol"}]},
        ],
    }
    (vf_dir / "municipality_0177256_voterinfo_9001_20260101T000000Z.json").write_text(json.dumps(payload))

    # Full extract: 1 election + 3 candidacies.
    full = GoogleCivicOfficialsPipeline(cache_dir=cache, states=("MA",))

    async def collect(pipe):
        return [r async for r in pipe.extract(_ctx())]

    extracted = asyncio.run(collect(full))
    assert len(extracted) == 4
    assert sum(r["record_type"] == "candidacy" for r in extracted) == 3
    for raw in extracted:
        assert full.validate(raw) is not None

    # limit caps emitted rows.
    capped = GoogleCivicOfficialsPipeline(cache_dir=cache, states=("MA",), limit=2)
    assert len(asyncio.run(collect(capped))) == 2

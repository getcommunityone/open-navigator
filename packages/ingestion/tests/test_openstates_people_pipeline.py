"""Unit tests for the OpenStates people pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from ingestion.openstates.people import (  # noqa: E402
    OpenstatesPeoplePipeline,
    OpenstatesPeopleRow,
    parse_person,
    find_all_people_files,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


_PERSON = {
    "id": "ocd-person/abc",
    "name": "Jane Doe",
    "party": [{"name": "Democratic"}],
    "image": "https://example.com/jane.png",
    "roles": [{"type": "lower", "district": "5", "jurisdiction": "ocd-jurisdiction/ma"}],
    "contact_details": [
        {
            "note": "Capitol Office",
            "email": "jane@example.gov",
            "voice": "555-1234",
            "address": "1 State House",
        }
    ],
}


def test_parse_person_extracts_fields():
    cols = parse_person(_PERSON, "ma")
    assert cols["id"] == "ocd-person/abc"
    assert cols["name"] == "Jane Doe"
    assert cols["state"] == "MA"  # uppercased
    assert cols["party"] == "Democratic"
    assert cols["role_type"] == "lower"
    assert cols["district"] == "5"
    assert cols["jurisdiction"] == "ocd-jurisdiction/ma"
    assert cols["email"] == "jane@example.gov"
    assert cols["phone"] == "555-1234"
    assert cols["address"] == "1 State House"
    assert cols["data"] is _PERSON


def test_parse_person_handles_missing_optional_fields():
    cols = parse_person({"id": "x", "name": "No Role"}, "ca")
    assert cols["state"] == "CA"
    assert cols["party"] is None
    assert cols["role_type"] is None
    assert cols["district"] is None
    assert cols["email"] is None
    assert cols["phone"] is None
    assert cols["address"] is None


def test_row_schema_accepts_valid_row():
    r = OpenstatesPeopleRow(
        source="openstates_people",
        source_version="people",
        natural_key="ocd-person/abc",
        id="ocd-person/abc",
        name="Jane Doe",
        state="MA",
        party="Democratic",
        role_type="lower",
        district="5",
        jurisdiction="ocd-jurisdiction/ma",
        email="jane@example.gov",
        phone="555-1234",
        address="1 State House",
        image="https://example.com/jane.png",
        data={"id": "ocd-person/abc"},
    )
    assert r.id == "ocd-person/abc"
    assert r.state == "MA"
    assert r.data == {"id": "ocd-person/abc"}


def test_row_schema_rejects_missing_name():
    with pytest.raises(Exception):
        OpenstatesPeopleRow(
            source="openstates_people",
            source_version="people",
            natural_key="x",
            id="x",
            name="",  # NOT NULL / min_length=1
        )


def test_row_schema_rejects_oversized_state():
    with pytest.raises(Exception):
        OpenstatesPeopleRow(
            source="openstates_people",
            source_version="people",
            natural_key="x",
            id="x",
            name="Someone",
            state="MAS",  # max_length=2
        )


def test_pipeline_metadata():
    p = OpenstatesPeoplePipeline()
    assert p.source == "openstates_people"
    assert p.batch_size == 1000
    assert p.row_schema is OpenstatesPeopleRow


def test_extract_raises_when_repo_missing(tmp_path, monkeypatch):
    import ingestion.openstates.people as op

    monkeypatch.setattr(op, "CACHE_DIR", tmp_path / "missing")
    p = OpenstatesPeoplePipeline()

    async def collect():
        return [r async for r in p.extract(_ctx())]

    with pytest.raises(FileNotFoundError):
        asyncio.run(collect())


def _write_person(tmp_path, state, subdir, fname, person):
    import yaml

    d = tmp_path / "people" / "data" / state / subdir
    d.mkdir(parents=True, exist_ok=True)
    (d / fname).write_text(yaml.safe_dump(person))


def test_find_all_people_files_discovers_yaml(tmp_path):
    _write_person(tmp_path, "ma", "legislature", "a.yml", {"id": "1", "name": "A"})
    _write_person(tmp_path, "ca", "executive", "b.yml", {"id": "2", "name": "B"})
    _write_person(tmp_path, "ny", "municipalities", "c.yml", {"id": "3", "name": "C"})
    found = find_all_people_files(tmp_path / "people")
    assert len(found) == 3
    assert {f.name for f in found} == {"a.yml", "b.yml", "c.yml"}


def test_extract_roundtrip_on_synthetic_files(tmp_path):
    _write_person(tmp_path, "ma", "legislature", "jane.yml", _PERSON)
    _write_person(
        tmp_path,
        "ca",
        "legislature",
        "noid.yml",
        {"name": "No Id"},  # missing id -> dropped
    )

    p = OpenstatesPeoplePipeline(path=tmp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    raw = extracted[0]
    assert raw["source"] == "openstates_people"
    assert raw["source_version"] == "people"
    assert raw["natural_key"] == "ocd-person/abc"
    assert raw["state"] == "MA"

    row = p.validate(raw)
    assert row is not None
    assert row.name == "Jane Doe"
    assert row.email == "jane@example.gov"


def test_extract_limit_caps_rows(tmp_path):
    for i in range(5):
        _write_person(
            tmp_path, "ma", "legislature", f"p{i}.yml", {"id": str(i), "name": f"P{i}"}
        )

    p = OpenstatesPeoplePipeline(path=tmp_path, limit=2)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2

"""Unit tests for the League of Cities directories pipeline refactor."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest


from ingestion.leagueofcities.directories import (  # noqa: E402
    CensusPlaceIndex,
    LeagueDirectoryRow,
    LeagueOfCitiesDirectoriesPipeline,
    _norm_placename,
    _row_key,
    _should_attempt_jurisdiction_match,
    _str,
    iter_city_files,
    sanitize_league_website,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_city_file(tmp_path, usps: str, doc: dict):
    state_dir = tmp_path / usps
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "cities.json").write_text(json.dumps(doc), encoding="utf-8")
    return state_dir / "cities.json"


def test_str_trims_and_truncates():
    assert _str("  hello  ") == "hello"
    assert _str("") is None
    assert _str("   ") is None
    assert _str(None) is None
    assert _str("abcdef", 3) == "abc"
    assert _str(123) == "123"


def test_sanitize_league_website_rejects_junk_and_normalizes():
    assert sanitize_league_website(None) is None
    assert sanitize_league_website("https://") is None
    assert sanitize_league_website("https:") is None
    # bare scheme-only with slash
    assert sanitize_league_website("http://") is None
    # http upgraded to https
    assert sanitize_league_website("http://example.com") == "https://example.com"
    # bare domain gets scheme
    assert sanitize_league_website("example.gov") == "https://example.gov"
    # double scheme repaired
    assert sanitize_league_website("http://https://city.org") == "https://city.org"


def test_norm_placename_strips_suffixes_and_saint():
    assert _norm_placename("City of Springfield") == "springfield"
    assert _norm_placename("Springfield City") == "springfield"
    assert _norm_placename("St. Louis") == "saint louis"
    assert _norm_placename("Orleans Parish") == "orleans county"


def test_row_key_is_stable_and_case_normalizes_state():
    a = _row_key("al", "Selma", "http://x", "detail")
    b = _row_key("AL", "Selma", "http://x", "detail")
    assert a == b
    # different municipality -> different key
    assert _row_key("AL", "Mobile", None, None) != _row_key("AL", "Selma", None, None)


def test_should_attempt_jurisdiction_match_rejects_junk():
    assert _should_attempt_jurisdiction_match("Selma") is True
    assert _should_attempt_jurisdiction_match("A") is False
    assert _should_attempt_jurisdiction_match("123 Main") is False
    assert _should_attempt_jurisdiction_match("10 to 20") is False


def test_census_place_index_exact_and_normalized_match():
    idx = CensusPlaceIndex()
    idx.add("AL", "Selma", "0100124", "jur-selma")
    idx.add("AL", "Mobile city", "0100130", "jur-mobile")

    jid, geoid, method = idx.match("AL", "Selma")
    assert (jid, geoid, method) == ("jur-selma", "0100124", "place_name_exact")

    # normalized: "Mobile" -> matches "Mobile city" after suffix strip
    jid, geoid, method = idx.match("AL", "Mobile")
    assert jid == "jur-mobile"
    assert method == "place_name_normalized"

    jid, geoid, method = idx.match("AL", "Nowhere")
    assert jid is None and method == "unmatched"


def test_league_directory_row_schema_accepts_and_rejects():
    r = LeagueDirectoryRow(
        source="leagueofcities_directories",
        source_version="AL",
        natural_key="abc",
        row_key="abc",
        state_code="AL",
        municipality_name="Selma",
        alternate_names=["Selma City"],
        raw_row=[["Selma", "8000"]],
    )
    assert r.state_code == "AL"
    assert r.alternate_names == ["Selma City"]
    assert r.raw_row == [["Selma", "8000"]]

    # state_code must be max 2 chars
    with pytest.raises(Exception):
        LeagueDirectoryRow(
            source="leagueofcities_directories",
            source_version="v",
            natural_key="x",
            row_key="x",
            state_code="ALA",
            municipality_name="Selma",
        )

    # municipality_name required (non-empty)
    with pytest.raises(Exception):
        LeagueDirectoryRow(
            source="leagueofcities_directories",
            source_version="v",
            natural_key="x",
            row_key="x",
            state_code="AL",
            municipality_name="",
        )


def test_pipeline_metadata():
    p = LeagueOfCitiesDirectoriesPipeline()
    assert p.source == "leagueofcities_directories"
    assert p.batch_size == 2000
    assert p.row_schema is LeagueDirectoryRow


def test_iter_city_files_empty_when_cache_missing(tmp_path, monkeypatch):
    import ingestion.leagueofcities.directories as dp
    monkeypatch.setattr(dp, "CACHE_DIR", tmp_path / "does_not_exist")
    assert iter_city_files(None) == []


def test_iter_city_files_discovers_and_filters_states(tmp_path, monkeypatch):
    import ingestion.leagueofcities.directories as dp
    monkeypatch.setattr(dp, "CACHE_DIR", tmp_path)
    _write_city_file(tmp_path, "AL", {"cities": []})
    _write_city_file(tmp_path, "TX", {"cities": []})
    # non-2-letter dir is ignored
    _write_city_file(tmp_path, "XYZ", {"cities": []})

    all_paths = iter_city_files(None)
    assert {p.parent.name for p in all_paths} == {"AL", "TX"}

    only_al = iter_city_files({"AL"})
    assert {p.parent.name for p in only_al} == {"AL"}


def test_extract_roundtrip_and_validate(tmp_path):
    _write_city_file(
        tmp_path,
        "AL",
        {
            "state_usps": "AL",
            "state_name": "Alabama",
            "league_organization": "Alabama League",
            "league_base_url": "https://alalm.org",
            "extracted_at": "2026-01-01T00:00:00Z",
            "extraction_status": "ok",
            "cities": [
                {
                    "name": "Selma",
                    "website": "http://selma-al.gov",
                    "phone": "334-555-0000",
                    "alternate_names": ["Selma City"],
                    "raw_row": [["Selma", "18000"]],
                    "population": 18000,
                },
                {"name": "   "},  # blank name -> dropped
            ],
        },
    )

    p = LeagueOfCitiesDirectoriesPipeline(path=tmp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    row = extracted[0]
    assert row["source"] == "leagueofcities_directories"
    assert row["source_version"] == "AL"
    assert row["natural_key"] == row["row_key"]
    assert row["state_code"] == "AL"
    assert row["state"] == "Alabama"
    assert row["municipality_name"] == "Selma"
    assert row["website"] == "https://selma-al.gov"  # http upgraded
    assert row["population_raw"] == "18000"
    assert row["alternate_names"] == ["Selma City"]
    assert row["raw_row"] == [["Selma", "18000"]]
    # no census index supplied -> no jurisdiction match attempted
    assert row["jurisdiction_id"] is None

    # All extracted rows validate cleanly
    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_limit_caps_rows(tmp_path):
    cities = [{"name": f"City{i}"} for i in range(10)]
    _write_city_file(tmp_path, "AL", {"state_usps": "AL", "cities": cities})

    p = LeagueOfCitiesDirectoriesPipeline(path=tmp_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3

"""#798: the facts behind the "how this summary was made" panel."""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # pydantic resolves annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


prov = _load("provenance_under_test", "api/provenance.py")


def test_all_recorded_facts_are_returned():
    p = prov.build_provenance(
        {
            "video_id": "abcdefghijk",
            "ai_model": "deepseek-flash",
            "generated_at": datetime(2026, 11, 20, 12, 0),
            "analysis_tier": "light",
            "prompt_name": "policy_analysis",
            "prompt_sha": "a1b2c3d4e5f6",
            "transcript_source": "youtube captions",
            "analyses_for_meeting": 2,
        },
    )
    assert p.model == "deepseek-flash" and p.tier == "light"
    assert p.prompt_name == "policy_analysis" and p.prompt_version == "a1b2c3d4e5f6"
    assert p.transcript_source == "youtube captions" and p.analyses_for_meeting == 2
    assert p.generated_at.startswith("2026-11-20T12:00")
    assert p.video_url == "https://www.youtube.com/watch?v=abcdefghijk"


def test_missing_facts_stay_none_never_filled_in():
    p = prov.build_provenance(None, source_ai_model="gemini-2.5-flash", extracted_at=datetime(2026, 1, 2))
    assert p.model == "gemini-2.5-flash" and p.generated_at.startswith("2026-01-02")
    assert p.tier is None and p.prompt_name is None and p.prompt_version is None
    assert p.transcript_source is None and p.video_url is None and p.analyses_for_meeting is None


def test_unknown_tier_is_dropped_and_nothing_recorded_gives_none():
    assert prov.build_provenance({"analysis_tier": "weird"}) is None  # a bad tier alone is not a recorded fact
    assert prov.build_provenance({"analysis_tier": "weird", "ai_model": "m"}).tier is None
    assert prov.build_provenance(None) is None
    assert prov.build_provenance({}, source_ai_model="  ") is None


def test_the_video_id_of_the_meeting_wins_over_the_row():
    p = prov.build_provenance({"video_id": "rowrowrowro"}, video_id="meetingvid1")
    assert p.video_url.endswith("meetingvid1")


loader_src = (ROOT / "packages/llm/src/llm/enrichment/load_analysis_cache_to_bronze.py").read_text()


def _fn(src: str, name: str):
    m = re.search(rf"^def {name}\(.*?(?=^\S)", src, re.S | re.M)
    ns: dict = {"Optional": __import__("typing").Optional, "Any": __import__("typing").Any}
    exec("from __future__ import annotations\n" + m.group(0), ns)  # noqa: S102 - our own source text
    return ns[name]


def test_transcript_source_is_read_from_the_run_metadata_or_none():
    f = _fn(loader_src, "transcript_source_from_meta")
    assert f({"transcript": {"source": " youtube captions "}}) == "youtube captions"
    assert f({"transcript": {}}) is None and f({}) is None and f(None) is None
    assert f({"transcript": "oops"}) is None


def test_loader_writes_the_tier_and_source_and_adds_the_columns_first():
    assert "analysis_tier = EXCLUDED.analysis_tier" in loader_src
    assert "transcript_source = EXCLUDED.transcript_source" in loader_src
    assert 'analysis_tier=e["tier"]' in loader_src
    assert "ensure_provenance_columns(conn)" in loader_src
    assert "ADD COLUMN IF NOT EXISTS analysis_tier" in loader_src


def test_run_metadata_records_the_transcript_source():
    src = (ROOT / "packages/llm/src/llm/gemini/meeting_transcript_policy.py").read_text()
    assert '"source": source_note' in src


def test_migration_is_additive_and_idempotent():
    sql = (ROOT / "packages/hosting/scripts/neon/migrations/115_add_analysis_provenance_columns.sql").read_text()
    assert sql.count("ADD COLUMN IF NOT EXISTS") == 2
    assert not re.search(r"\b(drop|delete|truncate)\b", sql, re.I)


def test_the_model_is_served_and_has_a_primary_key():
    macro = (ROOT / "dbt_project/macros/publish_public_serving.sql").read_text()
    assert macro.count("'event_analysis_provenance'") == 2  # launch predicate + served list
    yml = (ROOT / "dbt_project/models/marts/_schema_event_analysis_provenance.yml").read_text()
    assert "type: primary_key" in yml and "name: analysis_id" in yml
    neon = (ROOT / "packages/hosting/src/hosting/neon/sync_public_to_neon.py").read_text()
    assert '"event_analysis_provenance"' in neon


def test_the_decision_endpoint_returns_provenance():
    src = (ROOT / "api/routes/decisions.py").read_text()
    assert "provenance: Optional[Provenance]" in src and "FROM event_analysis_provenance" in src

"""#796 part 2: the model guard, per-tier metadata names, and the loader's skip rules."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LLM = ROOT / "packages" / "llm" / "src" / "llm"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, LLM / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


guard = _load("tier_model_guard_under_test", "gemini/tier_model_guard.py")
names = _load("tier_names_under_test", "gemini/tier_names.py")
gate = _load("analysis_load_gate_under_test", "enrichment/analysis_load_gate.py")

GEMINI = "gemini-2.5-flash-lite"


# --- the model guard --------------------------------------------------------------------------
def _conflict(tier, model="", part_2="", env=None):
    return guard.tier_model_conflict(
        tier=tier, model=model, part_2_model=part_2, gemini_default=GEMINI, env=env or {}
    )


def test_full_on_gemini_is_fine_while_light_is_deepseek():
    assert _conflict("full", GEMINI) is None
    assert _conflict("full", "") is None  # the Gemini default


def test_full_on_the_light_model_is_refused():
    msg = _conflict("full", "deepseek-flash")
    assert msg and "never share a model" in msg and "LIGHT_MODEL" in msg


def test_light_put_back_on_gemini_then_full_on_gemini_is_refused():
    # LIGHT_MODEL= (empty) means "use the Gemini default" for light: the collision this rule exists for.
    assert _conflict("full", GEMINI, env={"LIGHT_MODEL": ""}) is not None
    assert _conflict("full", "", env={"LIGHT_MODEL": ""}) is not None


def test_a_different_light_model_leaves_full_free():
    assert _conflict("full", GEMINI, env={"LIGHT_MODEL": "deepseek-v4-flash"}) is None


def test_part_2_model_is_checked_too():
    assert _conflict("full", GEMINI, part_2="deepseek-flash") is not None


def test_light_is_checked_against_full_model_only_when_set():
    assert _conflict("light", GEMINI) is None  # nothing says what full uses
    assert _conflict("light", GEMINI, env={"FULL_MODEL": GEMINI}) is not None
    assert _conflict("light", "deepseek-flash", env={"FULL_MODEL": GEMINI}) is None


# --- per-tier metadata names ------------------------------------------------------------------
def test_light_meta_name_is_unchanged_and_full_gets_the_suffix():
    p = Path("c/04_runs/2026-04-13_Council.meta.json")
    assert names.meta_with_tier_suffix(p, "light") == p
    assert names.meta_with_tier_suffix(p, "full") == Path("c/04_runs/2026-04-13_Council_full.meta.json")


def test_full_meta_suffix_is_not_applied_twice_and_other_files_are_untouched():
    p = Path("c/04_runs/x_full.meta.json")
    assert names.meta_with_tier_suffix(p, "full") == p
    other = Path("c/04_runs/x.diagrams.md")
    assert names.meta_with_tier_suffix(other, "full") == other


def test_light_and_full_meta_never_share_a_file():
    p = Path("c/04_runs/x.meta.json")
    assert names.meta_with_tier_suffix(p, "light") != names.meta_with_tier_suffix(p, "full")


# --- the loader's pairing and skip rules ------------------------------------------------------
def test_tier_comes_from_the_file_name():
    assert gate.tier_from_path(Path("x/02_analysis/2026-04-13_Council.json")) == "light"
    assert gate.tier_from_path(Path("x/02_analysis/2026-04-13_Council_full.json")) == "full"


def test_a_shared_pre_796_meta_is_not_paired_with_the_light_file():
    shared = {"gemini_model": "gemini-x", "files": {"analysis_json": "d/02_analysis/x_full.json"}}
    assert gate.meta_matches_file(shared, Path("d/02_analysis/x.json")) is False
    assert gate.meta_matches_file(shared, Path("d/02_analysis/x_full.json")) is True


def test_meta_without_a_recorded_file_is_given_the_benefit_of_the_doubt():
    assert gate.meta_matches_file({"gemini_model": "m"}, Path("d/02_analysis/x.json")) is True
    assert gate.meta_matches_file(None, Path("d/02_analysis/x.json")) is True


@pytest.mark.parametrize(
    ("info", "low", "reason"),
    [
        ({"meeting_type": "CITY_COUNCIL", "junk": False, "excluded": False}, False, None),
        ({"meeting_type": "city_council", "junk": False, "excluded": False}, False, None),
        ({"meeting_type": "OTHER", "junk": False, "excluded": False}, False, "non_meeting_type"),
        ({"meeting_type": "unknown", "junk": False, "excluded": False}, False, "non_meeting_type"),
        ({"meeting_type": "", "junk": False, "excluded": False}, False, "non_meeting_type"),
        ({"meeting_type": None, "junk": False, "excluded": False}, False, "non_meeting_type"),
        ({"meeting_type": "CITY_COUNCIL", "junk": True, "excluded": False}, False, "junk_channel"),
        ({"meeting_type": "CITY_COUNCIL", "junk": False, "excluded": True}, False, "policy_excluded"),
        ({"meeting_type": "CITY_COUNCIL", "junk": False, "excluded": False}, True, "low_keep_score"),
    ],
)
def test_decide_skip(info, low, reason):
    assert gate.decide_skip(info, low) == reason


def test_skip_reasons_are_reported_in_a_fixed_order():
    everything = {"meeting_type": "OTHER", "junk": True, "excluded": True}
    assert gate.decide_skip(everything, True) == "policy_excluded"
    assert gate.decide_skip({**everything, "excluded": False}, True) == "junk_channel"
    assert gate.decide_skip({**everything, "excluded": False, "junk": False}, True) == "non_meeting_type"


def test_a_video_with_no_bronze_row_is_not_skipped():
    assert gate.decide_skip(None, False) is None
    assert gate.decide_skip(None, True) is None  # unscreened and unknown: never guessed


class _Cur:
    def __init__(self, has_class=True, has_tx=True, rows=None):
        self.sql: list[str] = []
        self._has = (has_class, has_tx)
        self._rows = rows or []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql.append(" ".join(sql.split()))
        self._last = sql

    def fetchone(self):
        return self._has

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur


def test_fetch_video_info_builds_flags_per_video():
    cur = _Cur(rows=[("v1", "CITY_COUNCIL", False, False), ("v2", "", True, True)])
    out = gate.fetch_video_info(_Conn(cur), ["v1", "v2", "v1", ""])
    assert out == {
        "v1": {"meeting_type": "CITY_COUNCIL", "junk": False, "excluded": False},
        "v2": {"meeting_type": "", "junk": True, "excluded": True},
    }


def test_fetch_video_info_skips_tables_the_warehouse_lacks():
    cur = _Cur(has_class=False, has_tx=False, rows=[("v1", "CITY_COUNCIL", False, False)])
    gate.fetch_video_info(_Conn(cur), ["v1"])
    query = cur.sql[-1]
    assert "bronze_youtube_channel_classification" not in query
    assert "bronze_event_youtube_transcript" not in query


def test_fetch_video_info_with_no_videos_runs_no_query():
    cur = _Cur()
    assert gate.fetch_video_info(_Conn(cur), []) == {}
    assert cur.sql == []


def test_gate_module_never_writes():
    text = (LLM / "enrichment" / "analysis_load_gate.py").read_text(encoding="utf-8").lower()
    for word in ("insert ", "update ", "delete ", "drop ", "alter ", "truncate", "unlink", "rmtree", ".rename("):
        assert word not in text.replace('"""', ""), f"gate must be read-only, found {word!r}"

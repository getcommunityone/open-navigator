"""Public-comment stance rows in Part 1 / lite answers. No network."""

from __future__ import annotations

from pathlib import Path

from llm.gemini.part1_schema import validate_part1

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"
STANCES = "For, Against, Mixed or neutral, Not stated"


def _analysis(**extra):
    return {"meeting": {"meeting_id": "m1", "body_name": "Council"}, "decisions": [], **extra}


def test_rows_are_kept_as_written():
    row = {
        "speaker_id": "ann_lowe_resident",
        "decision_id": "D001",
        "stance": "Against",
        "stance_evidence": "please vote no",
        "timestamp_start_seconds": "125",
    }
    result = validate_part1(_analysis(public_participation=[row]))
    assert result.ok, result.errors
    kept = result.data["public_participation"][0]
    assert (kept["speaker_id"], kept["decision_id"], kept["stance"]) == ("ann_lowe_resident", "D001", "Against")


def test_missing_or_null_array_is_empty():
    assert validate_part1(_analysis()).ok
    assert validate_part1(_analysis(public_participation=None)).ok


def test_light_row_without_summary_or_times_is_valid():
    result = validate_part1(_analysis(public_participation=[{"speaker_id": "a_b_resident", "stance": "For"}]))
    assert result.ok, result.errors


def test_both_prompts_ask_the_same_stance_vocabulary():
    for name in ("policy_analysis_part_1.md", "policy_analysis_lite.md"):
        text = (PROMPTS / name).read_text(encoding="utf-8")
        assert '"public_participation": [' in text, name
        assert f'"stance": "one of: {STANCES}"' in text, name

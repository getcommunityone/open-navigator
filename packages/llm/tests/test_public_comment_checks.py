"""Public-comment stance checks (#818). Constructed cases only; no network, database or model."""

from __future__ import annotations

import json

import pytest
from llm.gemini import public_comment_checks as pc

TRANSCRIPT = (
    "thank you chair my name is ann lowe i live on oak street and i strongly oppose this rezoning. "
    "Next speaker. I'm Bo Ray, and I support the ordinance — please approve it tonight. "
    "How many gallons of water will the site use each day? "
    "If you pass this we will see you in court."
)


@pytest.mark.parametrize(
    ("quote", "side"),
    [
        ("I strongly oppose this rezoning", "against"),
        ("We are opposed to the data center", "against"),
        ("Please vote no on item seven", "against"),
        ("I urge you to deny this permit", "against"),
        ("I do not support this project", "against"),
        ("I'm not in favor of the rezoning", "against"),
        ("I support the ordinance", "for"),
        ("We are in favor of the plan", "for"),
        ("Please approve it tonight", "for"),
        ("I am not opposed to this", "for"),
        ("I don't object to the setback", "for"),
        ("How many gallons of water will the site use?", "question"),
        ("The setback is 500 feet", None),
        ("I support it, but only with a 1,000-foot setback", "for"),
        ("", None),
    ],
)
def test_side_from_quote(quote, side):
    assert pc.side_from_quote(quote) == side


def test_quote_found_ignores_case_punctuation_and_spacing():
    assert pc.quote_found("I strongly oppose this rezoning!", TRANSCRIPT)
    assert pc.quote_found("I support the ordinance - please approve it", TRANSCRIPT)
    assert not pc.quote_found("I strongly oppose this data center", TRANSCRIPT)
    assert not pc.quote_found("", TRANSCRIPT)


def test_stance_bucket_covers_the_prompt_values_only():
    assert [pc.stance_bucket(s) for s in ("For", "Against", "Asked questions", "Mixed or neutral", "Not stated")] == [
        "for", "against", "question", "neutral", "neutral"]
    assert pc.stance_bucket("For.") == "for"
    assert pc.stance_bucket("Unknown") is None
    assert pc.stance_bucket(None) is None


def test_prompt_stance_values_all_have_a_bucket():
    """If a prompt gains a stance value, this module must learn it too."""
    from pathlib import Path

    prompts = Path(__file__).resolve().parents[3] / "prompts"
    for name in ("policy_analysis_part_1.md", "policy_analysis_lite.md"):
        text = (prompts / name).read_text(encoding="utf-8")
        values = text.split('"stance": "one of: ', 1)[1].split('"', 1)[0].split(", ")
        assert all(pc.stance_bucket(v) is not None for v in values), (name, values)


def test_heat_flag():
    assert pc.heat_flag({"heat": 1, "stance_evidence": "we will see you in court"})
    assert pc.heat_flag({"heat": 5, "stance": "Asked questions", "stance_evidence": "How many gallons?"})
    assert pc.heat_flag({"heat": 5, "stance": "Against", "stance_evidence": "we will see you in court"}) is None
    assert pc.heat_flag({"heat": 2, "stance": "For", "stance_evidence": "please approve"}) is None
    assert pc.heat_flag({"heat": "hot", "stance_evidence": "see you in court"}) is None


def _analysis(*rows):
    return {"meeting": {}, "decisions": [], "public_participation": list(rows)}


def test_clean_analysis_passes():
    report = pc.check_analysis(
        _analysis(
            {"speaker_id": "ann_lowe_resident", "stance": "Against", "stance_evidence": "I strongly oppose this rezoning", "heat": 3},
            {"speaker_id": "bo_ray", "stance": "For", "stance_evidence": "I support the ordinance", "heat": 2},
            {"speaker_id": "cy_poe", "stance": "Asked questions", "stance_evidence": "How many gallons of water will the site use each day?", "heat": 1},
            {"speaker_id": "di_fox", "stance": "Not stated", "stance_evidence": None},
        ),
        TRANSCRIPT,
    )
    assert (report.rows, report.quotes, report.quotes_found, report.sided_quotes, report.flips) == (4, 3, 3, 2, 0)
    assert report.passed and report.findings == []


def test_invented_quote_and_wrong_side_fail():
    report = pc.check_analysis(
        _analysis(
            {"speaker_id": "ann_lowe_resident", "stance": "For", "stance_evidence": "I strongly oppose this rezoning"},
            {"speaker_id": "bo_ray", "stance": "For", "stance_evidence": "This will be great for jobs"},
            {"speaker_id": "ed_kim", "stance": "Maybe"},
        ),
        TRANSCRIPT,
    )
    assert report.flips == 1 and report.quotes_found == 1 and report.unknown_stance == 1
    assert not report.passed
    assert {f["check"] for f in report.findings} == {"quote_matches_label", "quote_found", "stance"}


def test_nothing_to_check_is_not_a_failure():
    assert pc.check_analysis({"meeting": {}}, TRANSCRIPT).passed
    assert pc.check_analysis(_analysis(), TRANSCRIPT).passed


def test_cli_exit_codes(tmp_path, capsys):
    t = tmp_path / "t.txt"
    t.write_text(TRANSCRIPT, encoding="utf-8")
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_analysis({"speaker_id": "a", "stance": "For", "stance_evidence": "I support the ordinance"})))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(_analysis({"speaker_id": "a", "stance": "For", "stance_evidence": "never said"})))
    assert pc.main(["--analysis", str(good), "--transcript", str(t), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True
    assert pc.main(["--analysis", str(bad), "--transcript", str(t), "--json"]) == 1
    assert pc.main(["--analysis", str(tmp_path / "missing.json"), "--transcript", str(t)]) == 2

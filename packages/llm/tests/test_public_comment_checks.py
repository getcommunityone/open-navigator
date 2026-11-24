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
        # plain statements
        ("I strongly oppose this rezoning", "against"),
        ("We are opposed to the data center", "against"),
        ("Please vote no on item seven", "against"),
        ("I urge you to deny this permit", "against"),
        ("I support the ordinance", "for"),
        ("We are in favor of the plan", "for"),
        ("Please approve it tonight", "for"),
        # a negator directly before the phrase flips it
        ("I do not support this project", "against"),
        ("I'm not in favor of the rezoning", "against"),
        ("I am not opposed to this", "for"),
        ("I don't object to the setback", "for"),
        ("We don't oppose; we support", "for"),
        ("don't vote no", "for"),
        ("I will not vote no", "for"),
        ("please do not deny this", "for"),
        ("please don't reject this", "for"),
        ("I urge you to not reject this", "for"),
        ("do not pass this", "against"),
        # no safe reading: hedges, conditions, both sides, narration (review of #819)
        ("I don't just support, I love it", None),
        ("I do not know if I support", None),
        ("I'm not sure I support", None),
        ("I do not support or oppose", None),
        ("I am not opposed to growth but I oppose this", None),
        ("I support this but I oppose the amendment", None),
        ("I support it, but only with a 1,000-foot setback", None),
        ("vote no on the bond but vote yes on the park", None),
        ("I cannot oppose enough", None),
        ("If you pass this we will see you in court", None),
        ("they will approve this next week", None),
        ("child support is expensive", None),
        ("we are up against the fence", None),
        ("The setback is 500 feet", None),
        ("", None),
        (None, None),
        # a question is never a stance, even with a side word in it
        ("How many gallons of water will the site use?", "question"),
        ("will you vote no on this?", "question"),
        ("Why should I support this?", "question"),
        ("do I support this? no", None),
    ],
)
def test_side_from_quote(quote, side):
    assert pc.side_from_quote(quote) == side


def test_quote_found_ignores_case_punctuation_and_spacing():
    assert pc.quote_found("I strongly oppose this rezoning!", TRANSCRIPT)
    assert pc.quote_found("I support the ordinance - please approve it", TRANSCRIPT)
    assert not pc.quote_found("I strongly oppose this data center", TRANSCRIPT)
    assert not pc.quote_found("", TRANSCRIPT)
    assert not pc.quote_found(None, TRANSCRIPT)


def test_quote_found_matches_whole_words_and_tolerates_how_models_quote():
    assert not pc.quote_found("no", "I know")  # substring of a word is not a match
    assert pc.quote_found("a 1,000 foot setback", "we want a 1000 foot setback please")
    assert pc.quote_found("Tom\u2019s plan is bad", "toms plan is bad")
    assert pc.quote_found("I oppose ... this rezoning tonight", "i oppose strongly this rezoning tonight")
    assert not pc.quote_found("this rezoning tonight ... I oppose", "i oppose strongly this rezoning tonight")
    assert pc.quote_found("I [inaudible] oppose this", "i uh oppose this")
    assert pc.quote_found("Estoy en contra del café", "estoy en contra del cafe hoy")
    assert pc.quote_found("Я против этого", "да я против этого")


def test_short_quotes_are_not_counted_as_evidence():
    assert not pc.quote_checkable("vote no")
    assert pc.quote_checkable("please vote no")
    report = pc.check_analysis(_analysis({"speaker_id": "a", "stance": "Against", "stance_evidence": "No."}), TRANSCRIPT)
    assert (report.quotes, report.short_quotes) == (0, 1) and report.passed


def test_stance_bucket_covers_the_prompt_values_only():
    assert [pc.stance_bucket(s) for s in ("For", "Against", "Asked questions", "Mixed or neutral", "Not stated")] == [
        "for", "against", "question", "neutral", "neutral"]
    assert pc.stance_bucket("For.") == "for"
    assert pc.stance_bucket("Unknown") is None
    assert all(pc.stance_bucket(v) is None for v in (None, 5, True, ["For"], {"a": 1}))


def test_prompt_stance_values_are_exactly_the_buckets_known_here():
    """If a prompt gains or drops a stance value, this module must change with it."""
    import re
    from pathlib import Path

    prompts = Path(__file__).resolve().parents[3] / "prompts"
    for name in ("policy_analysis_part_1.md", "policy_analysis_lite.md"):
        match = re.search(r'"stance": "one of: ([^"]+)"', (prompts / name).read_text(encoding="utf-8"))
        assert match, f"{name}: the stance vocabulary line was not found"
        assert {v.strip().lower() for v in match.group(1).split(",")} == set(pc._BUCKETS), name


def test_heat_flag():
    assert pc.heat_flag({"heat": 1, "stance_evidence": "we will see you in court"})
    assert pc.heat_flag({"heat": 5, "stance": "Asked questions", "stance_evidence": "How many gallons?"})
    assert pc.heat_flag({"heat": 5, "stance": "Against", "stance_evidence": "we will see you in court"}) is None
    assert pc.heat_flag({"heat": 2, "stance": "For", "stance_evidence": "please approve"}) is None
    assert pc.heat_flag({"heat": 3, "stance": "Asked questions", "stance_evidence": "How many gallons?"}) is None
    assert pc.heat_flag({"heat": "hot", "stance_evidence": "see you in court"}) is None
    # a neutral mention of a lawsuit is not a threat, and the model's summary is not the speaker's words
    assert pc.heat_flag({"heat": 1, "stance_evidence": "there is a pending lawsuit about the site"}) is None
    assert pc.heat_flag({"heat": 1, "stance_evidence": "thank you", "summary": "threatened to see you in court"}) is None


def test_heat_accepts_only_whole_numbers_one_to_five():
    assert [pc._heat(v) for v in ("3", 3.0, 5, 6, 3.5, True, None, "abc", [])] == [3, 3, 5, None, None, None, None, None, None]


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
    assert not report.passed  # the invented quote fails at any sample size
    assert {f["check"] for f in report.findings} == {"quote_matches_label", "quote_found", "stance"}


def test_malformed_rows_do_not_crash():
    report = pc.check_analysis(
        _analysis({"speaker_id": {"x": 1}, "stance": 5, "stance_evidence": ["x"], "heat": True}, "junk", None),
        TRANSCRIPT,
    )
    assert report.rows == 1 and report.unknown_stance == 1 and report.passed


def test_flip_bar_needs_enough_quotes_and_reports_are_added_together():
    wrong = {"speaker_id": "a", "stance": "For", "stance_evidence": "I strongly oppose this rezoning"}
    right = {"speaker_id": "b", "stance": "Against", "stance_evidence": "I strongly oppose this rezoning"}
    small = pc.check_analysis(_analysis(wrong), TRANSCRIPT)
    assert small.flips == 1 and not small.flip_bar_applied and small.passed  # one quote proves nothing
    report = pc.Report()
    for _ in range(pc.MIN_SIDED_QUOTES):
        pc.check_analysis(_analysis(right), TRANSCRIPT, report)
    assert report.analyses == pc.MIN_SIDED_QUOTES and report.flip_bar_applied and report.passed
    for _ in range(3):
        pc.check_analysis(_analysis(wrong), TRANSCRIPT, report)
    assert report.flip_rate > pc.MAX_FLIP_RATE and not report.passed


def test_nothing_to_check_is_not_a_failure():
    assert pc.check_analysis({"meeting": {}}, TRANSCRIPT).passed
    assert pc.check_analysis(_analysis(), TRANSCRIPT).passed


def test_cli_exit_codes(tmp_path, capsys):
    t = tmp_path / "t.txt"
    t.write_text(TRANSCRIPT, encoding="utf-8")
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_analysis({"speaker_id": "a", "stance": "For", "stance_evidence": "I support the ordinance"})))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(_analysis({"speaker_id": "a", "stance": "For", "stance_evidence": "this was never said at all"})))
    assert pc.main(["--analysis", str(good), "--transcript", str(t), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True
    assert pc.main(["--analysis", str(bad), "--transcript", str(t), "--json"]) == 1
    assert pc.main(["--analysis", str(tmp_path / "missing.json"), "--transcript", str(t)]) == 2
    assert pc.main(["--analysis", str(good), str(good), "--transcript", str(t)]) == 2  # one transcript per analysis
    capsys.readouterr()
    assert pc.main(["--analysis", str(good), str(good), "--transcript", str(t), str(t), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["analyses"] == 2
    assert pc.main(["--analysis", str(good), "--transcript", str(t)]) == 0  # the text report path runs too

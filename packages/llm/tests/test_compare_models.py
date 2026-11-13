"""Model comparison on the transcript Part 1 analysis (#267). No network, no database."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

import pytest
from llm.gemini import compare_models as cm


def _analysis(decisions=(), uncontested=(), people=(), places=(), amounts=()):
    return {
        "meeting": {"body_name": "City Council"},
        "decisions": [
            {"headline": h, "decision_statement": s, "vote_tally": {"yes": y, "no": n},
             "media_anchor": {"timestamp_start_seconds": t}}
            for h, s, y, n, t in decisions
        ],
        "uncontested_items": [{"headline": h, "one_line_summary": s, "vote": v} for h, s, v in uncontested],
        "people": [{"full_name": n} for n in people],
        "places": [{"normalized_address": a} for a in places],
        "financial_items": [{"amount": a} for a in amounts],
    }  # fmt: skip


REFERENCE = _analysis(
    decisions=[
        ("Rezoning of 412 Maple Street for a pharmacy", "Council rezoned 412 Maple Street from R-1 to C-2", 5, 2, 60),
        ("Short-term rental cap", "Ordinance limits short-term rentals to 90 nights a year", 4, 3, 660),
    ],
    uncontested=[("Oak Avenue paving contract", "Hartwell Paving resurfaces Oak Avenue for $1.25M", "7-0")],
    people=["Mayor Dana Whitfield", "Councilmember Priya Shah", "Carol Beech"],
    places=["412 Maple Street, Riverbend, AL", "Oak Avenue, Riverbend, AL"],
    amounts=[1250000],
)


# --------------------------------------------------------------------------- #
# Arms
# --------------------------------------------------------------------------- #
def test_parse_arm():
    assert cm.parse_arm("gemini-2.5-flash:-1") == cm.Arm("gemini-2.5-flash:-1", "gemini-2.5-flash", None)
    assert cm.parse_arm("gemini-2.5-flash:512").thinking_budget == 512
    assert cm.parse_arm("gemma-4-31b-it") == cm.Arm("gemma-4-31b-it", "gemma-4-31b-it", 0)
    with pytest.raises(ValueError):
        cm.parse_arm("gemini-2.5-flash:lots")


def test_parse_arms_defaults_and_dedupes():
    assert [a.label for a in cm.parse_arms("")] == list(cm.DEFAULT_ARMS)
    assert {"gemma-4-26b-a4b-it", "gemini-3.5-flash-lite"} <= set(cm.DEFAULT_ARMS)
    assert [a.label for a in cm.parse_arms("a:0, b ,a:0")] == ["a:0", "b"]
    assert cm.parse_arm("gemini-2.5-flash:-1").slug == "gemini-2.5-flash_-1"


def test_gemma_output_is_capped():
    assert cm.output_token_cap("gemma-4-31b-it", 65536) == 32768
    assert cm.output_token_cap("gemma-4-31b-it", 1000) == 1000
    assert cm.output_token_cap("gemini-2.5-flash", 65536) == 65536


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def test_parse_vote():
    assert cm.parse_vote({"yes": 5, "no": 2}) == (5, 2)
    assert cm.parse_vote({"yes": 5, "no": None}) is None
    assert cm.parse_vote("Carried 7-0") == (7, 0)
    assert cm.parse_vote("6 to 1") == (6, 1)
    assert cm.parse_vote("unanimous") is None


def test_identical_analysis_scores_perfectly():
    score = cm.score_analysis(REFERENCE, REFERENCE)
    for column in ("item_recall", "item_precision", "decision_recall", "vote_agreement",
                   "people_recall", "place_recall", "amount_recall"):  # fmt: skip
        assert score[column] == 1.0, column
    assert score["missed"] == [] and score["added"] == []


def test_partial_analysis():
    candidate = _analysis(
        decisions=[
            # same item, reworded, wrong vote
            ("Pharmacy rezoning at 412 Maple", "Rezoned 412 Maple Street to C-2 for a pharmacy", 6, 1, None),
            # same item, different words, matched by timestamp
            ("STR limits adopted", "Nightly cap", 4, 3, 700),
            ("A water rate increase", "Water rates rise 3 percent", 6, 1, 1200),  # not in the reference
        ],
        people=["Dana Whitfield", "P. Shah"],
        places=["412 Maple St, Riverbend AL"],
    )
    score = cm.score_analysis(candidate, REFERENCE)
    assert score["item_recall"] == round(2 / 3, 3)
    assert score["item_precision"] == round(2 / 3, 3)
    assert score["decision_recall"] == 1.0
    assert score["vote_agreement"] == 0.5
    assert score["people_recall"] == round(2 / 3, 3)
    assert score["place_recall"] == 0.5
    assert score["amount_recall"] == 0.0
    assert score["missed"] == ["Oak Avenue paving contract"]
    assert score["added"] == ["A water rate increase"]
    assert score["vote_mismatches"] == ["Rezoning of 412 Maple Street for a pharmacy: reference 5-2, arm 6-1"]


def test_street_abbreviations_match():
    reference = _analysis(places=["412 Maple Street, Riverbend, AL", "88 Elm Court, Riverbend, AL"])
    candidate = _analysis(places=["412 Maple St, Riverbend, AL", "88 Elm Ct Riverbend AL"])
    assert cm.score_analysis(candidate, reference)["place_recall"] == 1.0


def test_an_item_moved_between_contested_and_uncontested_still_matches():
    candidate = _analysis(uncontested=[("Rezoning of 412 Maple Street for a pharmacy",
                                        "Council rezoned 412 Maple Street from R-1 to C-2", "5-2")])  # fmt: skip
    score = cm.score_analysis(candidate, REFERENCE)
    assert score["decision_recall"] == 0.5 and score["vote_agreement"] == 1.0


def test_not_json_scores_zero_and_empty_reference_lists_score_none():
    score = cm.score_analysis(None, REFERENCE)
    assert score["json_ok"] is False and score["item_recall"] == 0.0 and score["item_precision"] is None
    assert len(score["missed"]) == 3
    bare = _analysis()
    score = cm.score_analysis(bare, bare)
    assert score["json_ok"] is True and score["item_recall"] is None and score["people_recall"] is None


def test_names():
    assert cm.normalize_name("Councilmember Priya Shah") == "priya shah"
    assert cm._name_found("priya shah", ["p shah"])
    assert cm._name_found("shah", ["priya shah"])
    assert not cm._name_found("priya shah", ["tom shah"])


def test_parse_answer():
    text = json.dumps(REFERENCE)
    assert cm.parse_answer(text)["meeting"]["body_name"] == "City Council"
    assert cm.parse_answer("```json\n" + text + "\n```")["decisions"]
    assert cm.parse_answer("[" + text + "]")["meeting"]["body_name"] == "City Council"  # Gemma's array wrapper
    assert cm.parse_answer('{"no_meeting": 1}') is None
    assert cm.parse_answer("") is None


# --------------------------------------------------------------------------- #
# Summary and a run on disk
# --------------------------------------------------------------------------- #
def test_summarize_means_and_cost_rules():
    rows = [
        {"arm": "a", "is_ok": True, "json_ok": True, "item_recall": 1.0, "people_recall": None,
         "input_token_count": 100, "output_token_count": 10, "model": "m", "api_mode": "interactive"},
        {"arm": "a", "is_ok": True, "json_ok": False, "item_recall": 0.0, "people_recall": 0.5,
         "input_token_count": 300, "output_token_count": 30, "model": "m", "api_mode": "interactive"},
        {"arm": "b", "is_ok": False, "json_ok": False, "item_recall": 0.0, "model": "m", "api_mode": "interactive"},
    ]  # fmt: skip
    prices = {"models": {"m": {"source": "s", "read_date": "d",
                               "interactive": {"input_usd_per_1m": 1.0, "output_usd_per_1m": 10.0}}}}  # fmt: skip
    a, b = cm.summarize(rows, ["a", "b", "never-ran"], prices)
    assert a["meeting_count"] == 2 and a["json_ok_rate"] == 0.5 and a["item_recall"] == 0.5
    assert a["people_recall"] == 0.5  # the None is left out of the mean
    assert a["mean_input_token_count"] == 200.0
    assert a["mean_cost_usd"] == pytest.approx((0.0002 + 0.0006) / 2, abs=1e-5)
    assert b["call_failed_count"] == 1 and b["mean_cost_usd"] is None
    assert cm.summarize(rows, ["a"], {"models": {}})[0]["mean_cost_usd"] is None


def test_score_run_and_outputs(tmp_path, monkeypatch):
    run = tmp_path / "run"
    video = run / "vid00000001"
    video.mkdir(parents=True)
    (video / "reference.json").write_text(json.dumps(REFERENCE))
    good, bad, fail = cm.parse_arm("good:0"), cm.parse_arm("bad"), cm.parse_arm("fails")
    (video / f"{good.slug}.txt").write_text(json.dumps(REFERENCE))
    (video / f"{good.slug}.call.json").write_text(json.dumps(
        {"arm": "good:0", "model": "good", "is_ok": True, "input_token_count": 9}))  # fmt: skip
    (video / f"{bad.slug}.txt").write_text("I could not do that.")
    (video / f"{bad.slug}.call.json").write_text(json.dumps({"arm": "bad", "model": "bad", "is_ok": True}))
    (video / f"{fail.slug}.failed.json").write_text(json.dumps(
        {"arm": "fails", "model": "fails", "is_ok": False, "error": "GenAIServerOverloadGiveUp: 504"}))  # fmt: skip
    rows = cm.score_run(run, [good, bad, fail], cm.REFERENCE_EXISTING)
    by_arm = {r["arm"]: r for r in rows}
    assert by_arm["good:0"]["item_recall"] == 1.0 and by_arm["good:0"]["input_token_count"] == 9
    assert by_arm["bad"]["json_ok"] is False
    assert by_arm["fails"]["is_ok"] is False and by_arm["fails"]["item_recall"] == 0.0

    meta = {"run_id": "run", "created_at": "2026-11-13T21:00:00+00:00", "reference": "existing",
            "video_ids": ["vid00000001"]}  # fmt: skip
    out = cm.write_outputs(run, meta, rows, [good, bad, fail])
    text = out.read_text()
    assert "| good:0 | 1 | 0 | 1 | 1 |" in text
    assert "call failed: GenAIServerOverloadGiveUp: 504" in text
    assert "the answer was not Part 1 JSON" in text
    assert "vote differs" not in text
    assert (run / "comparison.csv").read_text().startswith("video_id,arm,model,is_ok,json_ok")

    # an arm as the reference: that arm is not scored against itself
    rows = cm.score_run(run, [good, bad], "good:0")
    assert [r["arm"] for r in rows] == ["bad"]


def test_run_arm_reuses_a_saved_answer_and_retries_a_failed_one(tmp_path, monkeypatch):
    from llm.gemini import genai_text_client as gtc

    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        if kwargs["model"] == "broken":
            raise RuntimeError("504")
        return SimpleNamespace(text="{}", usage=None)

    monkeypatch.setattr(gtc, "call_gemini_text", fake)
    request = SimpleNamespace(user_message="M", video=SimpleNamespace(video_id="v", jurisdiction_id="j"))
    args = argparse.Namespace(temperature=0.1, max_output_tokens=65536, no_json_mode=False)
    arm = cm.parse_arm("gemma-4-31b-it")
    first = cm.run_arm(arm, request, tmp_path, args, "k")
    assert first["is_ok"] and calls[0]["max_output_tokens"] == 32768 and calls[0]["json_mode"] is True
    cm.run_arm(arm, request, tmp_path, args, "k")
    assert len(calls) == 1  # the saved answer is reused
    broken = cm.parse_arm("broken")
    assert cm.run_arm(broken, request, tmp_path, args, "k")["is_ok"] is False
    cm.run_arm(broken, request, tmp_path, args, "k")
    assert len(calls) == 3  # a failed arm is called again

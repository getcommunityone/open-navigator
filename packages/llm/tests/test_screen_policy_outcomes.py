"""#1029: the combined Jev screen asks the outcome Choices and policy-question Nouls, and can target cohorts."""

from llm.typesafe import screen_transcripts as st


def test_questions_include_outcomes_and_policy_questions() -> None:
    assert {"dc_outcome", "str_outcome", "mentions_short_term_rentals"} <= set(st.QUESTIONS)
    for slug in st.POLICY_QUESTIONS:
        assert f"q_{slug}" in st.QUESTIONS
    assert set(st.DC_OUTCOMES) == {
        "approved", "denied", "tabled_or_deferred", "moratorium", "discussed_no_action", "no_data_center_item",
    }
    assert "no_short_term_rental_item" in st.STR_OUTCOMES


def test_cohort_filter_targets_data_center_and_str_meetings() -> None:
    sql, _ = st.select_sql(states=[], jurisdiction_id="", rescreen=True, cohorts=["data-centers", "short-term-rentals"])
    assert "data_center_meeting_mention" in sql
    assert "topic_transcript_link WHERE topic_id = 100003" in sql
    assert " OR " in sql


class _Ans:
    def __init__(self, noul=None, probabilities=None):
        self.noul = noul
        self.probabilities = probabilities


class _Resp:
    def __init__(self, answers):
        self.answers = answers


def test_aggregate_averages_outcomes_and_maxes_questions() -> None:
    a = _Resp({
        "dc_outcome": _Ans(probabilities={"approved": 0.8, "discussed_no_action": 0.2}),
        "q_allow_data_centers": _Ans(noul=0.3),
    })
    b = _Resp({
        "dc_outcome": _Ans(probabilities={"approved": 0.4, "discussed_no_action": 0.6}),
        "q_allow_data_centers": _Ans(noul=0.9),
    })
    out = st.aggregate([a, b])
    assert out["dc_outcome"] == "approved"
    assert out["dc_outcome_probabilities"] == {"approved": 0.6, "discussed_no_action": 0.4}
    assert out["question_probabilities"]["allow_data_centers"] == 0.9
    assert out["str_outcome"] is None


def test_public_lean_ignores_chunks_without_public_comment() -> None:
    """#1113: a long meeting's quiet chunks don't drown out the chunk where residents spoke."""
    quiet = _Resp({"dc_public_lean": _Ans(probabilities={"no_public_comment_on_data_center": 0.95, "mostly_opposed": 0.05})})
    spoke = _Resp({"dc_public_lean": _Ans(probabilities={
        "mostly_opposed": 0.7, "mixed": 0.15, "mostly_supported": 0.05, "no_public_comment_on_data_center": 0.1,
    })})
    out = st.public_lean([quiet, quiet, quiet, spoke])
    assert out["dc_public_lean"] == "mostly_opposed"
    assert "no_public_comment_on_data_center" not in out["dc_public_lean_probabilities"]
    assert abs(sum(out["dc_public_lean_probabilities"].values()) - 1.0) < 0.01


def test_public_lean_none_when_no_chunk_has_public_comment() -> None:
    quiet = _Resp({"dc_public_lean": _Ans(probabilities={"no_public_comment_on_data_center": 0.9, "mixed": 0.1})})
    out = st.public_lean([quiet, quiet])
    assert out["dc_public_lean"] == "no_public_comment_on_data_center"
    assert st.public_lean([])["dc_public_lean"] is None


def test_public_lean_is_a_question_and_a_column() -> None:
    assert "dc_public_lean" in st.QUESTIONS
    assert set(st.DC_PUBLIC_LEAN) == {"mostly_opposed", "mostly_supported", "mixed", "no_public_comment_on_data_center"}
    assert "dc_public_lean" in st.UPSERT_SQL and "dc_public_lean" in st.ALTER_TOPIC_COLUMNS_SQL

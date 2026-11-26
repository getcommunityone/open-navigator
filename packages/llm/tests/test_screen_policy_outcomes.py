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

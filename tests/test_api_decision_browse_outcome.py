"""GET /api/decisions?question_id=&outcome= (#499): a question's outcome family filters the list."""

from __future__ import annotations

from api.routes.decision_browse import _build_filters

QID = "f7001f99695ccecb1e8df4ab0ee721fd"


def test_outcome_filters_inside_the_question_exists() -> None:
    _, where, params, _ = _build_filters(None, QID, "AL", None, None, None, "moratorium")
    assert "qi.question_id = $1 AND qi.outcome_family = $2)" in where
    assert "ii.state_code = $3" in where
    assert params == [QID, "moratorium", "AL"]


def test_no_outcome_keeps_the_question_filter_unchanged() -> None:
    _, where, params, _ = _build_filters(None, QID, None, None, None)
    assert "outcome_family" not in where
    assert params == [QID]


def test_outcome_without_question_is_ignored() -> None:
    _, where, params, _ = _build_filters(None, None, None, None, None, None, "denied")
    assert where == "TRUE" and params == []

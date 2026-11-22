# tests/test_batch_job_cohorts.py
from api.batch_jobs.cohorts import (
    PRIORITY_STATE_CODES,
    cohort_state_codes,
    resolve_launch_states,
)


def test_priority_states_are_fixed():
    assert cohort_state_codes("priority") == PRIORITY_STATE_CODES


def test_resolve_launch_states_default_priority_all():
    assert resolve_launch_states("priority", []) == PRIORITY_STATE_CODES


def test_resolve_launch_states_rejects_state_outside_cohort():
    try:
        resolve_launch_states("priority", ["TX"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "TX" in str(e)


def test_resolve_launch_states_data_centers_intersects(monkeypatch):
    monkeypatch.setattr(
        "api.batch_jobs.cohorts.cohort_state_codes",
        lambda cohort, **kw: ["AL", "VA", "TX"] if cohort == "data_centers" else [],
    )
    assert resolve_launch_states("data_centers", ["AL"]) == ["AL"]
    try:
        resolve_launch_states("data_centers", ["HI"])
        assert False
    except ValueError:
        pass
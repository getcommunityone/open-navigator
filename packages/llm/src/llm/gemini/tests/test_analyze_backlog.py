"""Pure-logic tests for the backlog driver: model-cycling state machine and the
recency jurisdiction-plan construction. No DB, no clock, no API calls."""

from datetime import datetime, timezone

import pytest

from llm.gemini.analyze_backlog import (
    DEFAULT_MODELS,
    AllModelsExhausted,
    JurisdictionPlan,
    ModelCycler,
    format_eta,
    next_pacific_midnight,
    parse_models,
    rows_to_plans,
    seconds_until_pacific_midnight,
)


# --------------------------------------------------------------------------- #
# parse_models
# --------------------------------------------------------------------------- #
def test_parse_models_default_when_blank():
    assert parse_models(None) == list(DEFAULT_MODELS)
    assert parse_models("") == list(DEFAULT_MODELS)


def test_parse_models_dedupes_and_trims_order():
    assert parse_models("a, b , a,c") == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# ModelCycler state machine
# --------------------------------------------------------------------------- #
def test_cycler_starts_at_first_model():
    c = ModelCycler(models=["m1", "m2", "m3"])
    assert c.current == "m1"
    assert not c.all_exhausted


def test_cycler_dedupes_models():
    c = ModelCycler(models=["m1", "m1", "m2"])
    assert c.models == ["m1", "m2"]


def test_cycler_advance_on_exhaustion():
    c = ModelCycler(models=["m1", "m2", "m3"])
    c.mark_exhausted("m1")
    assert c.current == "m2"
    assert c.advance() == "m2"
    c.mark_exhausted("m2")
    assert c.current == "m3"


def test_cycler_marks_current_when_no_arg():
    c = ModelCycler(models=["m1", "m2"])
    c.mark_exhausted()  # marks current (m1)
    assert "m1" in c.exhausted
    assert c.current == "m2"


def test_cycler_all_exhausted_detection():
    c = ModelCycler(models=["m1", "m2"])
    c.mark_exhausted("m1")
    assert not c.all_exhausted
    c.mark_exhausted("m2")
    assert c.all_exhausted
    with pytest.raises(AllModelsExhausted):
        _ = c.current
    with pytest.raises(AllModelsExhausted):
        c.advance()


def test_cycler_reset_clears_and_wraps():
    c = ModelCycler(models=["m1", "m2"])
    c.mark_exhausted("m1")
    c.mark_exhausted("m2")
    assert c.all_exhausted
    c.reset()
    assert not c.all_exhausted
    assert c.current == "m1"  # wraps back to the front after the daily reset


def test_cycler_empty_models_rejected():
    with pytest.raises(ValueError):
        ModelCycler(models=[])
    with pytest.raises(ValueError):
        ModelCycler(models=["", "  "])


# --------------------------------------------------------------------------- #
# rows_to_plans (recency plan construction from fake DB rows)
# --------------------------------------------------------------------------- #
def _dt(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def test_rows_to_plans_preserves_recency_order():
    # SQL already orders recency-DESC; helper keeps the order it's given.
    rows = [
        ("muni_recent", "GA", 76, _dt(2026, 6, 4)),
        ("muni_mid", "AL", 40, _dt(2025, 1, 1)),
        ("muni_old", "wi", 622, _dt(2020, 3, 2)),
    ]
    plans = rows_to_plans(rows)
    assert [p.jurisdiction_id for p in plans] == ["muni_recent", "muni_mid", "muni_old"]
    assert plans[0].pending == 76
    assert plans[2].state_code == "WI"  # upper-cased


def test_rows_to_plans_skips_blank_jid_and_zero_pending():
    rows = [
        ("", "GA", 5, _dt(2026, 1, 1)),
        ("muni_a", "GA", 0, _dt(2026, 1, 1)),
        ("muni_b", "GA", 3, _dt(2026, 1, 1)),
    ]
    plans = rows_to_plans(rows)
    assert [p.jurisdiction_id for p in plans] == ["muni_b"]


def test_rows_to_plans_handles_null_newest():
    rows = [("muni_a", "GA", 3, None)]
    plans = rows_to_plans(rows)
    assert plans[0].newest_pending is None
    assert isinstance(plans[0], JurisdictionPlan)


def test_rows_to_plans_coerces_nonsense_newest_to_none():
    rows = [("muni_a", "GA", 3, "not-a-datetime")]
    plans = rows_to_plans(rows)
    assert plans[0].newest_pending is None


# --------------------------------------------------------------------------- #
# Pacific reset clock helpers (pure: clock passed in)
# --------------------------------------------------------------------------- #
def test_next_pacific_midnight_is_after_now():
    now = _dt(2026, 6, 4)  # aware UTC
    nxt = next_pacific_midnight(now)
    assert nxt.hour == 0 and nxt.minute == 0
    assert nxt > now.astimezone(nxt.tzinfo)


def test_seconds_until_pacific_midnight_nonnegative():
    now = _dt(2026, 6, 4)
    assert seconds_until_pacific_midnight(now) >= 0


# --------------------------------------------------------------------------- #
# format_eta
# --------------------------------------------------------------------------- #
def test_format_eta_buckets():
    assert format_eta(float("nan")) == "?"
    assert format_eta(-1) == "?"
    assert format_eta(45) == "45s"
    assert format_eta(125).endswith("s") and format_eta(125).startswith("2m")
    assert format_eta(3700).startswith("1h")

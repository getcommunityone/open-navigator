"""Pure-logic tests for the backlog driver: model-cycling state machine and the
recency jurisdiction-plan construction. No DB, no clock, no API calls."""

from datetime import datetime, timezone

import pytest

from llm.gemini.analyze_backlog import (
    DEFAULT_MODELS,
    DEFAULT_OVERLOAD_COOLDOWN_SECONDS,
    AllModelsExhausted,
    JurisdictionPlan,
    ModelCycler,
    filter_plans,
    format_eta,
    next_pacific_midnight,
    parse_models,
    parse_shard,
    parse_states,
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


# --------------------------------------------------------------------------- #
# ModelCycler cooldowns (server-overload temporary rotation — clock passed in)
# --------------------------------------------------------------------------- #
def test_overloaded_model_skipped_until_cooldown_expires():
    c = ModelCycler(models=["m1", "m2"])
    now = 1000.0
    # m1 hit a sustained 504: cool it down for 600s. current_or_none must skip it.
    c.mark_overloaded("m1", now=now, cooldown_seconds=600.0)
    assert c.current_or_none(now=now) == "m2"
    # While still cooling, m1 stays skipped.
    assert c.current_or_none(now=now + 599.0) == "m2"
    # m1 is NOT daily-walled — it must not be in the exhausted set.
    assert "m1" not in c.exhausted
    # After the cooldown expires, m1 is available again (front of rotation).
    assert c.current_or_none(now=now + 601.0) == "m1"


def test_default_cooldown_constant_applied():
    c = ModelCycler(models=["m1", "m2"])
    now = 0.0
    c.mark_overloaded("m1", now=now)  # default cooldown
    assert c.cooldowns["m1"] == now + DEFAULT_OVERLOAD_COOLDOWN_SECONDS


def test_current_property_ignores_cooldowns_backward_compat():
    # The no-arg property only considers DAILY walls (cooldowns need a clock). A model
    # that is only cooling down still shows as `current` to legacy callers.
    c = ModelCycler(models=["m1", "m2"])
    c.mark_overloaded("m1", now=100.0, cooldown_seconds=600.0)
    assert c.current == "m1"  # cooldowns ignored without `now`


def test_all_cooling_down_advance_raises():
    c = ModelCycler(models=["m1", "m2"])
    now = 50.0
    c.mark_overloaded("m1", now=now, cooldown_seconds=300.0)
    c.mark_overloaded("m2", now=now, cooldown_seconds=600.0)
    with pytest.raises(AllModelsExhausted):
        c.advance(now=now)
    # all_exhausted is about DAILY walls only — cooling down is not "exhausted".
    assert not c.all_exhausted


# --------------------------------------------------------------------------- #
# seconds_until_any_available math
# --------------------------------------------------------------------------- #
def test_seconds_until_any_available_none_when_model_free():
    c = ModelCycler(models=["m1", "m2"])
    c.mark_overloaded("m1", now=0.0, cooldown_seconds=600.0)
    # m2 is free right now -> nothing to wait for.
    assert c.seconds_until_any_available(now=0.0) is None


def test_seconds_until_any_available_soonest_cooldown():
    c = ModelCycler(models=["m1", "m2"])
    now = 100.0
    c.mark_overloaded("m1", now=now, cooldown_seconds=300.0)  # frees at 400
    c.mark_overloaded("m2", now=now, cooldown_seconds=600.0)  # frees at 700
    # Both cooling -> wait until the soonest (m1 at 400) = 300s from now.
    assert c.seconds_until_any_available(now=now) == 300.0


def test_seconds_until_any_available_none_when_only_daily_walls():
    # Every model is DAILY-walled (not cooling) -> None, so the caller falls back to
    # the Pacific-midnight wait rather than a short cooldown wait.
    c = ModelCycler(models=["m1", "m2"])
    c.mark_exhausted("m1")
    c.mark_exhausted("m2")
    assert c.seconds_until_any_available(now=999.0) is None


def test_clear_expired_cooldowns():
    c = ModelCycler(models=["m1", "m2"])
    c.mark_overloaded("m1", now=0.0, cooldown_seconds=100.0)
    c.mark_overloaded("m2", now=0.0, cooldown_seconds=500.0)
    c.clear_expired_cooldowns(now=200.0)
    assert "m1" not in c.cooldowns  # expired
    assert "m2" in c.cooldowns  # still cooling


def test_reset_clears_daily_not_cooldowns():
    c = ModelCycler(models=["m1", "m2"])
    c.mark_exhausted("m1")
    c.mark_overloaded("m2", now=0.0, cooldown_seconds=600.0)
    c.reset()
    assert not c.exhausted  # daily wall cleared
    assert "m2" in c.cooldowns  # cooldown left to expire on its own clock


# --------------------------------------------------------------------------- #
# parse_states / parse_shard / filter_plans (jurisdiction-slice flags)
# --------------------------------------------------------------------------- #
def test_parse_states_repeatable_and_comma():
    assert parse_states(["GA,AL", "wi"]) == ["GA", "AL", "WI"]
    assert parse_states(["GA", "GA"]) == ["GA"]  # de-duped
    assert parse_states(None) == []


def test_parse_shard_valid_and_none():
    assert parse_shard(None) is None
    assert parse_shard("") is None
    assert parse_shard("0/3") == (0, 3)
    assert parse_shard(" 2 / 4 ") == (2, 4)


def test_parse_shard_rejects_bad_specs():
    with pytest.raises(ValueError):
        parse_shard("3")  # no slash
    with pytest.raises(ValueError):
        parse_shard("3/3")  # index out of range
    with pytest.raises(ValueError):
        parse_shard("0/0")  # zero count
    with pytest.raises(ValueError):
        parse_shard("a/b")  # non-integer


def _plan(jid, state="GA"):
    return JurisdictionPlan(jurisdiction_id=jid, state_code=state, pending=1, newest_pending=None)


def test_filter_plans_by_state():
    plans = [_plan("a", "GA"), _plan("b", "AL"), _plan("c", "ga")]
    kept = filter_plans(plans, states=["GA"])
    assert [p.jurisdiction_id for p in kept] == ["a", "c"]  # case-insensitive


def test_filter_plans_shards_are_disjoint_and_cover_all():
    plans = [_plan(f"muni_{i}") for i in range(60)]
    shards = [filter_plans(plans, shard=(i, 3)) for i in range(3)]
    ids = [{p.jurisdiction_id for p in s} for s in shards]
    # disjoint
    assert ids[0] & ids[1] == set()
    assert ids[0] & ids[2] == set()
    assert ids[1] & ids[2] == set()
    # complete cover, no loss
    assert ids[0] | ids[1] | ids[2] == {p.jurisdiction_id for p in plans}


def test_filter_plans_shard_is_stable_across_calls():
    plans = [_plan(f"muni_{i}") for i in range(30)]
    first = [p.jurisdiction_id for p in filter_plans(plans, shard=(1, 4))]
    second = [p.jurisdiction_id for p in filter_plans(plans, shard=(1, 4))]
    assert first == second and first  # deterministic, non-empty


def test_filter_plans_combines_state_and_shard():
    plans = [_plan(f"m{i}", "GA" if i % 2 == 0 else "AL") for i in range(40)]
    kept = filter_plans(plans, states=["GA"], shard=(0, 2))
    assert all(p.state_code == "GA" for p in kept)


# --------------------------------------------------------------------------- #
# run-level: a server-overload give-up rotates the model (does NOT daily-wall)
# --------------------------------------------------------------------------- #
def test_run_backlog_overload_rotates_model(monkeypatch):
    """A GenAIServerOverloadGiveUp on the first model must put it on a cooldown and
    retry the same jurisdiction on the next live model — NOT wall it for the day."""
    import llm.gemini.analyze_backlog as ab
    from llm.gemini.genai_text_client import GenAIServerOverloadGiveUp

    monkeypatch.setattr(ab, "_resolve_database_url", lambda *_a, **_k: "fake-dsn")
    monkeypatch.setattr(
        ab, "fetch_pending_plans", lambda *_a, **_k: [_plan("muni_x", "GA")]
    )
    # Avoid any real sleeping in the wait path (shouldn't be hit here anyway).
    monkeypatch.setattr(ab.time, "sleep", lambda *_a, **_k: None)

    calls: list[str] = []

    def _fake_run(ns):
        calls.append(ns.model)
        if len(calls) == 1:
            raise GenAIServerOverloadGiveUp("504 DEADLINE_EXCEEDED")
        # second model succeeds
        return None

    monkeypatch.setattr(ab, "run_jurisdiction", _fake_run)

    args = ab.build_parser().parse_args(
        ["--models", "m1,m2", "--on-exhaust", "exit"]
    )
    ab.run_backlog(args)

    # m1 overloaded -> cooled down + rotated to m2 which succeeded.
    assert calls == ["m1", "m2"]


def test_run_backlog_daily_quota_walls_then_exits(monkeypatch):
    """A daily-quota wall on every model with --on-exhaust exit ends cleanly without
    looping forever (distinct control path from the overload cooldown)."""
    import llm.gemini.analyze_backlog as ab
    from llm.gemini.genai_text_client import GenAIDailyQuotaGiveUp

    monkeypatch.setattr(ab, "_resolve_database_url", lambda *_a, **_k: "fake-dsn")
    monkeypatch.setattr(
        ab, "fetch_pending_plans", lambda *_a, **_k: [_plan("muni_y", "GA")]
    )
    monkeypatch.setattr(ab.time, "sleep", lambda *_a, **_k: None)

    def _always_quota(ns):
        raise GenAIDailyQuotaGiveUp("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(ab, "run_jurisdiction", _always_quota)

    args = ab.build_parser().parse_args(["--models", "m1,m2", "--on-exhaust", "exit"])
    # Should return (exit) rather than hang.
    ab.run_backlog(args)

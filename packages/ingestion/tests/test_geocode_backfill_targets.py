"""Target selection for the geocode backfill (#495). Pure SQL building; no DB, no network."""
from __future__ import annotations

import asyncio

import pytest

from ingestion.geocode import backfill_places as bp


def _sql(**kwargs) -> tuple[str, dict[str, object]]:
    kwargs.setdefault("schema", "gold")
    kwargs.setdefault("source", "all")
    return bp.build_targets_query(**kwargs)


def test_reads_gold_event_place_by_default():
    sql, _ = _sql(schema=bp.resolve_schema())
    assert "FROM gold.event_place ep" in sql
    assert "public.event_place" not in sql


def test_schema_env_and_cli_precedence(monkeypatch):
    monkeypatch.delenv("EVENT_PLACE_SCHEMA", raising=False)
    assert bp.resolve_schema() == "gold"
    monkeypatch.setenv("EVENT_PLACE_SCHEMA", "staging_copy")
    assert bp.resolve_schema() == "staging_copy"
    assert bp.resolve_schema("other") == "other"


@pytest.mark.parametrize("bad", ["gold; drop table x", "gold.event_place", "1gold", "go-ld"])
def test_rejects_non_identifier_schema(bad):
    with pytest.raises(ValueError):
        bp.resolve_schema(bad)
    with pytest.raises(ValueError):
        bp.build_targets_query(schema=bad, source="all")


@pytest.mark.parametrize("source", ["all", "census", "nominatim"])
def test_jurisdiction_wide_always_excluded(source):
    sql, _ = _sql(source=source)
    assert "ep.place_type <> 'jurisdiction_wide'" in sql


def test_census_lane_is_street_address_only():
    sql, _ = _sql(source="census")
    assert "AND ep.place_type = 'street_address'" in sql
    assert "ep.place_type <> 'street_address'" not in sql


def test_nominatim_lane_excludes_street_address():
    sql, _ = _sql(source="nominatim")
    assert "AND ep.place_type <> 'street_address'" in sql


def test_unknown_source_rejected():
    with pytest.raises(ValueError):
        _sql(source="google")


def test_only_pending_and_uncached_targets():
    sql, _ = _sql()
    assert "ep.geocode_status = 'pending' OR ep.geocode_status IS NULL" in sql
    assert "NOT EXISTS" in sql and "bronze.place_geocode_cache" in sql


def test_cache_key_matches_dbt_model_expression():
    # event_place_geocoded.sql joins on this exact normalization.
    assert bp._KEY_EXPR == (
        "lower(regexp_replace(trim(coalesce(ep.normalized_address, "
        "ep.geocode_query, ep.raw_text)), '\\s+', ' ', 'g'))"
    )
    sql, _ = _sql()
    assert f"c.geocode_key = {bp._KEY_EXPR}" in sql


def test_prioritize_decisions_restricts_to_linked_places():
    plain, _ = _sql(source="nominatim")
    prio, _ = _sql(source="nominatim", prioritize_decisions=True)
    linked = "AND (jsonb_typeof(ep.linked_decision_ids) = 'array'"
    assert linked not in plain
    assert linked in prio
    # Decision-linked places sort first either way.
    assert "ORDER BY has_decision DESC, raw_key" in plain


def test_state_and_limit_are_bound_params():
    sql, params = _sql(state="al", limit=500)
    assert ":state" in sql and params["state"] == "AL"
    assert "LIMIT :limit" in sql and params["limit"] == 500
    sql, params = _sql()
    assert "LIMIT" not in sql and params == {}


def test_rows_to_targets_dedupes_on_normalized_key():
    rows = [
        {"query_text": "100 Main St,  Tuscaloosa AL", "place_type": "street_address",
         "street_address": "100 Main St", "city": "Tuscaloosa", "state_code": "AL"},
        {"query_text": "100 main st, tuscaloosa al", "place_type": "street_address",
         "street_address": None, "city": None, "state_code": None},
        {"query_text": "   ", "place_type": "other",
         "street_address": None, "city": None, "state_code": None},
    ]
    targets = bp.rows_to_targets(rows)
    assert [t.geocode_key for t in targets] == ["100 main st, tuscaloosa al"]
    assert targets[0].street_address == "100 Main St"


def test_empty_target_set_logs_and_skips_geocoders(monkeypatch):
    messages: list[str] = []
    handler = bp.logger.add(lambda m: messages.append(str(m)), level="WARNING")

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def _noop(*a, **k):
        return None

    async def _no_targets(*a, **k):
        return []

    async def _boom(*a, **k):
        raise AssertionError("geocoder must not run with no targets")

    monkeypatch.setattr(bp, "prepare_cache_table", _noop)
    monkeypatch.setattr(bp, "async_session", lambda: _Session())
    monkeypatch.setattr(bp, "assert_source_table", _noop)
    monkeypatch.setattr(bp, "fetch_targets", _no_targets)
    monkeypatch.setattr(bp, "run_census", _boom)
    monkeypatch.setattr(bp, "run_nominatim", _boom)
    try:
        args = bp.build_parser().parse_args(["--source", "census"])
        asyncio.run(bp._run(args))
    finally:
        bp.logger.remove(handler)
    assert any("No geocode targets in gold.event_place" in m for m in messages)

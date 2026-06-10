"""Tests for jurisdiction mapping unmapped SQL builders."""

from ingestion.jurisdictions.mapping.queries import (
    build_unmapped_where_asyncpg,
    build_unmapped_where_psycopg,
)


def test_build_unmapped_where_cities_state() -> None:
    sql, params = build_unmapped_where_psycopg("cities", state_code="al")
    assert "incorporated_city" in sql
    assert "NOT COALESCE(has_primary_website" in sql
    assert params == ["al"]


def test_build_unmapped_where_asyncpg_acs_bucket() -> None:
    sql, params, n = build_unmapped_where_asyncpg(
        "towns",
        acs_population_tier="Very Small (<15k)",
        param_start=1,
    )
    assert "acs_population_tier::text = $1" in sql
    assert params == ["Very Small (<15k)"]
    assert n == 2

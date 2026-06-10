"""Tests for jurisdiction mapping quality query helpers."""

from ingestion.jurisdictions.mapping.queries import (
    build_missing_youtube_where_asyncpg,
    build_missing_youtube_where_psycopg,
)


def test_missing_youtube_where_counties_psycopg() -> None:
    where, params = build_missing_youtube_where_psycopg("counties", state_code="AL")
    assert "NOT COALESCE(has_youtube_channel, FALSE)" in where
    assert "jurisdiction_type = 'county'" in where
    assert params == ["AL"]


def test_missing_youtube_where_cities_asyncpg() -> None:
    where, params, next_idx = build_missing_youtube_where_asyncpg(
        "cities",
        acs_population_tier="Mid (50k-250k)",
        param_start=1,
    )
    assert "NOT COALESCE(has_youtube_channel, FALSE)" in where
    assert "municipality_place_kind = 'incorporated_city'" in where
    assert "acs_population_tier::text = $1" in where
    assert params == ["Mid (50k-250k)"]
    assert next_idx == 2

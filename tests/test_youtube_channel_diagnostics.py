from scripts.datasources.jurisdictions.youtube_channel_diagnostics import (
    build_youtube_coverage_where_asyncpg,
    build_youtube_diagnostics_where_asyncpg,
    compute_youtube_gap_reason,
)


def test_compute_gap_reason_no_channel() -> None:
    code, _ = compute_youtube_gap_reason(
        {"has_youtube_channel": False, "n_bronze_videos": 0, "n_candidates": 0, "n_verified_candidates": 0}
    )
    assert code == "no_channel_discovered"


def test_compute_gap_reason_channel_no_bronze() -> None:
    code, _ = compute_youtube_gap_reason(
        {"has_youtube_channel": True, "n_bronze_videos": 0, "n_candidates": 0, "n_verified_candidates": 0}
    )
    assert code == "golden_channel_no_bronze_videos"


def test_compute_gap_reason_verified_not_promoted() -> None:
    code, _ = compute_youtube_gap_reason(
        {"has_youtube_channel": False, "n_bronze_videos": 0, "n_candidates": 2, "n_verified_candidates": 1}
    )
    assert code == "verified_candidates_not_promoted"


def test_build_where_requires_state() -> None:
    import pytest

    with pytest.raises(ValueError, match="state_code"):
        build_youtube_diagnostics_where_asyncpg("counties", state_code="")


def test_build_coverage_where_ga_optional_national() -> None:
    where_ga, params_ga, _ = build_youtube_coverage_where_asyncpg("counties", state_code="GA")
    assert "county" in where_ga.lower()
    assert params_ga == ["GA"]

    where_all, params_all, _ = build_youtube_coverage_where_asyncpg("counties")
    assert "county" in where_all.lower()
    assert params_all == []


def test_build_where_ga_counties() -> None:
    where, params, n = build_youtube_diagnostics_where_asyncpg(
        "counties", state_code="GA", name_search="dekalb", param_start=1
    )
    assert "county" in where.lower()
    assert "GA" in params
    assert "dekalb" in params[1].lower() or "%dekalb%" in str(params[1]).lower()
    assert n == 3

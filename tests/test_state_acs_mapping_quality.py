"""State population tier buckets for jurisdiction mapping quality dashboard."""

from ingestion.jurisdictions.mapping.state_acs_quality import (
    state_income_tier,
    state_population_tier,
)


def test_state_population_tiers() -> None:
    assert state_population_tier(39_000_000) == "Very Large"
    assert state_population_tier(20_000_001) == "Very Large"
    assert state_population_tier(20_000_000) == "Large"
    assert state_population_tier(10_000_001) == "Large"
    assert state_population_tier(10_000_000) == "Major Mid-Sized"
    assert state_population_tier(5_000_001) == "Major Mid-Sized"
    assert state_population_tier(5_000_000) == "Mid-Sized"
    assert state_population_tier(2_000_001) == "Mid-Sized"
    assert state_population_tier(2_000_000) == "Small"
    assert state_population_tier(500_000) == "Small"


def test_state_income_tiers() -> None:
    assert state_income_tier(80_000) == "High Earner"
    assert state_income_tier(65_000) == "Middle Class"
    assert state_income_tier(55_000) == "Lower Middle"
    assert state_income_tier(40_000) == "Low Income"

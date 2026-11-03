"""Unit tests for the Connecticut FIPS planning region to legacy county crosswalk (Issue #71)."""
from __future__ import annotations

import math
import pytest

from ingestion.census.export_census_map_static import (
    CONNECTICUT_LEGACY_COUNTY_CROSSWALK,
    METRICS,
    synthesize_connecticut_legacy_counties,
    synthesize_connecticut_county_trends,
)


def test_crosswalk_weights_sum_to_one():
    """Verify all 8 legacy Connecticut counties have constituent region weights summing to 1.0."""
    assert len(CONNECTICUT_LEGACY_COUNTY_CROSSWALK) == 8
    expected_fips = {
        "09001",
        "09003",
        "09005",
        "09007",
        "09009",
        "09011",
        "09013",
        "09015",
    }
    assert set(CONNECTICUT_LEGACY_COUNTY_CROSSWALK.keys()) == expected_fips

    for fips, spec in CONNECTICUT_LEGACY_COUNTY_CROSSWALK.items():
        assert "name" in spec
        assert "regions" in spec
        weights = spec["regions"]
        total_weight = sum(weights.values())
        assert math.isclose(total_weight, 1.0, rel_tol=1e-5), f"{fips} weights do not sum to 1: {total_weight}"
        for r_fips, w in weights.items():
            assert r_fips.startswith("091"), f"Invalid planning region FIPS {r_fips} for {fips}"
            assert 0.0 < w <= 1.0, f"Weight {w} out of bounds for {r_fips}"


def test_synthesize_connecticut_legacy_counties_basic():
    """Verify legacy county synthesis for count, currency, ratio, percent, and year metrics."""
    input_values = {
        # Planning regions
        "09190": {
            "NAME": "Western Connecticut Planning Region",
            "median_household_income": 120_000,
            "total_population": 600_000,
            "gini_income_inequality": 0.4850,
            "median_gross_rent_pct_hhincome": 28.50,
            "median_age": 41.2,
        },
        "09120": {
            "NAME": "Greater Bridgeport Planning Region",
            "median_household_income": 90_000,
            "total_population": 350_000,
            "gini_income_inequality": 0.5120,
            "median_gross_rent_pct_hhincome": 34.00,
            "median_age": 39.8,
        },
        "09130": {
            "NAME": "Lower Connecticut River Valley Planning Region",
            "median_household_income": 95_000,
            "total_population": 170_000,
            "gini_income_inequality": 0.4410,
            "median_gross_rent_pct_hhincome": 26.20,
            "median_age": 45.1,
        },
        # Non-CT county should remain untouched
        "06001": {
            "NAME": "Alameda County",
            "median_household_income": 112_000,
            "total_population": 1_650_000,
        },
    }

    result = synthesize_connecticut_legacy_counties(dict(input_values))

    # Non-CT county untouched
    assert result["06001"]["median_household_income"] == 112_000
    assert result["06001"]["total_population"] == 1_650_000

    # Fairfield County (09001): 64% 09190 + 36% 09120
    assert "09001" in result
    ff = result["09001"]
    assert ff["NAME"] == "Fairfield County"
    assert ff["GEOID"] == "09001"
    # Currency: 120,000 * 0.64 + 90,000 * 0.36 = 76,800 + 32,400 = 109,200
    assert ff["median_household_income"] == 109_200
    # Count: 600,000 * 0.64 + 350,000 * 0.36 = 384,000 + 126,000 = 510,000
    assert ff["total_population"] == 510_000
    # Ratio: 0.4850 * 0.64 + 0.5120 * 0.36 = 0.3104 + 0.18432 = 0.49472 -> round(0.4947, 4)
    assert ff["gini_income_inequality"] == 0.4947
    # Percent: 28.5 * 0.64 + 34.0 * 0.36 = 18.24 + 12.24 = 30.48
    assert ff["median_gross_rent_pct_hhincome"] == 30.48
    # Years: 41.2 * 0.64 + 39.8 * 0.36 = 26.368 + 14.328 = 40.696 -> round(40.7, 1)
    assert ff["median_age"] == 40.7

    # Middlesex County (09007): 100% 09130
    assert "09007" in result
    mx = result["09007"]
    assert mx["NAME"] == "Middlesex County"
    assert mx["median_household_income"] == 95_000
    assert mx["total_population"] == 170_000
    assert mx["gini_income_inequality"] == 0.4410
    assert mx["median_gross_rent_pct_hhincome"] == 26.20
    assert mx["median_age"] == 45.1


def test_synthesize_connecticut_legacy_counties_no_planning_regions():
    """Verify that if no planning regions (091xx) are present, values are untouched."""
    input_values = {
        "09001": {"NAME": "Fairfield County", "median_household_income": 105_000},
        "12086": {"NAME": "Miami-Dade County", "median_household_income": 58_000},
    }
    result = synthesize_connecticut_legacy_counties(dict(input_values))
    assert result == input_values


def test_synthesize_connecticut_legacy_counties_does_not_overwrite_existing():
    """Verify that existing legacy county data with valid metrics is not overwritten."""
    input_values = {
        "09001": {
            "NAME": "Fairfield County",
            "median_household_income": 999_999,
        },
        "09190": {"median_household_income": 120_000},
        "09120": {"median_household_income": 90_000},
    }
    result = synthesize_connecticut_legacy_counties(dict(input_values))
    assert result["09001"]["median_household_income"] == 999_999


def test_synthesize_connecticut_county_trends_multi_vintage():
    """Verify multi-year trend synthesis preserving legacy vintages (2020-2021) and synthesizing 2022+."""
    vintages = ["2020", "2021", "2022", "2023", "2024"]
    by_geoid = {
        "09001": {
            "GEOID": "09001",
            "NAME": "Fairfield County",
            "median_household_income": {
                "2020": 100_000,
                "2021": 104_000,
            },
        },
        "09190": {
            "GEOID": "09190",
            "NAME": "Western Connecticut Planning Region",
            "median_household_income": {
                "2022": 115_000,
                "2023": 120_000,
                "2024": 125_000,
            },
        },
        "09120": {
            "GEOID": "09120",
            "NAME": "Greater Bridgeport Planning Region",
            "median_household_income": {
                "2022": 85_000,
                "2023": 90_000,
                "2024": 95_000,
            },
        },
    }

    result = synthesize_connecticut_county_trends(by_geoid, vintages)

    ff_series = result["09001"]["median_household_income"]
    # Existing vintages preserved
    assert ff_series["2020"] == 100_000
    assert ff_series["2021"] == 104_000

    # 2022 synthesized: 115,000 * 0.64 + 85,000 * 0.36 = 73,600 + 30,600 = 104,200
    assert ff_series["2022"] == 104_200
    # 2023 synthesized: 120,000 * 0.64 + 90,000 * 0.36 = 76,800 + 32,400 = 109,200
    assert ff_series["2023"] == 109_200
    # 2024 synthesized: 125,000 * 0.64 + 95,000 * 0.36 = 80,000 + 34,200 = 114,200
    assert ff_series["2024"] == 114_200

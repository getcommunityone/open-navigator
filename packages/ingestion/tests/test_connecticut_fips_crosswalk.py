"""Tests for Connecticut legacy counties vs planning regions (Issue #71).

Since the 2022 ACS vintage Connecticut reports by planning region (091xx), not by the
8 legacy counties (090xx). We never blend planning-region values into counties (that
would invent county figures); legacy counties are emitted with null metrics and a note.
"""
from __future__ import annotations

from ingestion.census.export_census_map_static import (
    CONNECTICUT_LEGACY_COUNTY_NAMES,
    CONNECTICUT_PLANNING_REGION_NOTE,
    METRICS,
    mark_connecticut_legacy_counties_unavailable,
    mark_connecticut_county_trends_unavailable,
)

EXPECTED_NAMES = {
    "09001": "Fairfield County",
    "09003": "Hartford County",
    "09005": "Litchfield County",
    "09007": "Middlesex County",
    "09009": "New Haven County",
    "09011": "New London County",
    "09013": "Tolland County",
    "09015": "Windham County",
}


def test_legacy_county_names_are_plain_fips_to_name_mapping():
    """Only the real FIPS to name mapping is kept: no weights, no region lists."""
    assert CONNECTICUT_LEGACY_COUNTY_NAMES == EXPECTED_NAMES
    assert all(isinstance(v, str) for v in CONNECTICUT_LEGACY_COUNTY_NAMES.values())


def test_planning_regions_make_legacy_counties_null_with_note():
    input_values = {
        "09190": {"NAME": "Western Connecticut Planning Region", "median_household_income": 120_000, "total_population": 600_000},
        "09120": {"NAME": "Greater Bridgeport Planning Region", "median_household_income": 90_000, "total_population": 350_000},
        "06001": {"NAME": "Alameda County", "median_household_income": 112_000},
    }
    result = mark_connecticut_legacy_counties_unavailable(dict(input_values))

    # Other counties and the planning regions themselves are untouched
    assert result["06001"] == input_values["06001"]
    assert result["09190"]["median_household_income"] == 120_000

    assert set(EXPECTED_NAMES) <= set(result)
    for fips, name in EXPECTED_NAMES.items():
        row = result[fips]
        assert row["NAME"] == name
        assert row["GEOID"] == fips
        assert row["data_note"] == CONNECTICUT_PLANNING_REGION_NOTE
        for m in METRICS:
            assert row[m["slug"]] is None, f"{fips} {m['slug']} must be null, not blended"


def test_note_text():
    assert "planning region" in CONNECTICUT_PLANNING_REGION_NOTE
    assert "no county figure" in CONNECTICUT_PLANNING_REGION_NOTE


def test_no_planning_regions_leaves_values_untouched():
    input_values = {
        "09001": {"NAME": "Fairfield County", "median_household_income": 105_000},
        "12086": {"NAME": "Miami-Dade County", "median_household_income": 58_000},
    }
    result = mark_connecticut_legacy_counties_unavailable(dict(input_values))
    assert result == input_values
    assert "data_note" not in result["09001"]


def test_existing_real_legacy_county_data_is_kept():
    input_values = {
        "09001": {"NAME": "Fairfield County", "median_household_income": 999_999},
        "09190": {"median_household_income": 120_000},
    }
    result = mark_connecticut_legacy_counties_unavailable(dict(input_values))
    assert result["09001"]["median_household_income"] == 999_999
    assert "data_note" not in result["09001"]


def test_trends_keep_real_legacy_years_and_never_blend():
    vintages = ["2020", "2021", "2022", "2023"]
    by_geoid = {
        "09001": {
            "GEOID": "09001",
            "NAME": "Fairfield County",
            "median_household_income": {"2020": 100_000, "2021": 104_000},
        },
        "09190": {"GEOID": "09190", "NAME": "Western", "median_household_income": {"2022": 115_000, "2023": 120_000}},
        "09120": {"GEOID": "09120", "NAME": "Bridgeport", "median_household_income": {"2022": 85_000, "2023": 90_000}},
    }
    result = mark_connecticut_county_trends_unavailable(by_geoid, vintages)

    series = result["09001"]["median_household_income"]
    assert series == {"2020": 100_000, "2021": 104_000}
    assert "2022" not in series and "2023" not in series
    assert result["09001"]["data_note"] == CONNECTICUT_PLANNING_REGION_NOTE

    # Every legacy county exists with name and note, and no metric series at all if it had none
    for fips, name in EXPECTED_NAMES.items():
        assert result[fips]["NAME"] == name
        assert result[fips]["data_note"] == CONNECTICUT_PLANNING_REGION_NOTE
    assert "median_household_income" not in result["09007"]


def test_trends_without_planning_regions_untouched():
    by_geoid = {"09001": {"GEOID": "09001", "NAME": "Fairfield County", "median_household_income": {"2020": 1}}}
    assert mark_connecticut_county_trends_unavailable(dict(by_geoid), ["2020"]) == by_geoid

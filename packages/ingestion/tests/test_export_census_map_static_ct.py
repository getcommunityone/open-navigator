"""Tests for the census map export: CT planning-region -> legacy county crosswalk (#71).

Connecticut replaced its eight legacy counties with nine planning regions as
Census county-equivalents in June 2022, so ACS county parquets from the 2022
vintage onward are keyed by region codes (09110-09190) while the site's county
basemap uses the legacy codes (09001-09015). These tests pin the collapse
(regions -> dominant legacy county, counts summed, rates population-weighted).
"""
from __future__ import annotations

import pandas as pd
import pytest

from ingestion.census.export_census_map_static import (
    build_county_trends_for_state,
    build_county_values,
)


def _write_county_parquet(acs_dir, table: str, year: int, rows: list[dict]) -> None:
    path = acs_dir / f"{table}_county_*_{year}.parquet"
    pd.DataFrame(rows).to_parquet(path)


def _region_pops() -> list[dict]:
    return [
        {"state": 9, "county": 110, "NAME": "Capitol Planning Region", "B01003_001E": 600_000},
        {"state": 9, "county": 120, "NAME": "Greater Bridgeport Planning Region", "B01003_001E": 300_000},
        {"state": 9, "county": 190, "NAME": "Western Connecticut Planning Region", "B01003_001E": 400_000},
        {"state": 9, "county": 140, "NAME": "Naugatuck Valley Planning Region", "B01003_001E": 270_000},
        {"state": 9, "county": 170, "NAME": "South Central Connecticut Planning Region", "B01003_001E": 260_000},
        {"state": 9, "county": 150, "NAME": "Northeastern Connecticut Planning Region", "B01003_001E": 120_000},
        {"state": 6, "county": 37, "NAME": "Los Angeles County", "B01003_001E": 10_000_000},
    ]


def _write_2022_region_frames(acs_dir) -> None:
    _write_county_parquet(
        acs_dir,
        "B01003",
        2022,
        _region_pops(),
    )
    _write_county_parquet(
        acs_dir,
        "B19013",
        2022,
        [
            {"state": 9, "county": 110, "NAME": "Capitol Planning Region", "B19013_001E": 90_000},
            {"state": 9, "county": 120, "NAME": "Greater Bridgeport Planning Region", "B19013_001E": 100_000},
            {"state": 9, "county": 190, "NAME": "Western Connecticut Planning Region", "B19013_001E": 80_000},
            {"state": 9, "county": 140, "NAME": "Naugatuck Valley Planning Region", "B19013_001E": 85_000},
            {"state": 9, "county": 170, "NAME": "South Central Connecticut Planning Region", "B19013_001E": 92_000},
            {"state": 9, "county": 150, "NAME": "Northeastern Connecticut Planning Region", "B19013_001E": 72_000},
            {"state": 6, "county": 37, "NAME": "Los Angeles County", "B19013_001E": 98_000},
        ],
    )
    _write_county_parquet(
        acs_dir,
        "B17001",
        2022,
        [
            {"state": 9, "county": 110, "NAME": "Capitol Planning Region", "B17001_001E": 590_000, "B17001_002E": 64_000},
            {"state": 9, "county": 120, "NAME": "Greater Bridgeport Planning Region", "B17001_001E": 295_000, "B17001_002E": 28_000},
            {"state": 9, "county": 190, "NAME": "Western Connecticut Planning Region", "B17001_001E": 392_000, "B17001_002E": 45_000},
            {"state": 6, "county": 37, "NAME": "Los Angeles County", "B17001_001E": 9_800_000, "B17001_002E": 1_100_000},
        ],
    )


def test_build_county_values_crosswalks_ct_regions_to_legacy_counties(tmp_path):
    _write_2022_region_frames(tmp_path)

    out = build_county_values(tmp_path, 2022)

    # Region codes must not leak through to the basemap.
    assert "09110" not in out
    assert "09120" not in out
    assert "09013" not in out  # Tolland County: no majority region in 2022+
    # Fairfield County (09001) merges Greater Bridgeport (09120) + Western CT (09190).
    assert out["09001"]["NAME"] == "Fairfield County"
    expected_rate = (100_000 * 300_000 + 80_000 * 400_000) / (300_000 + 400_000)
    assert out["09001"]["median_household_income"] == pytest.approx(expected_rate)
    assert out["09001"]["population_income_below_poverty_level"] == pytest.approx(28_000 + 45_000)
    assert out["09001"]["poverty_universe"] == pytest.approx(295_000 + 392_000)
    # New Haven County (09009) merges Naugatuck Valley (09140) + South Central (09170).
    expected_nh = (85_000 * 270_000 + 92_000 * 260_000) / (270_000 + 260_000)
    assert out["09009"]["median_household_income"] == pytest.approx(expected_nh)
    # Single-region counties and out-of-state counties pass through unchanged.
    assert out["09003"]["median_household_income"] == pytest.approx(90_000)
    assert out["09015"]["median_household_income"] == pytest.approx(72_000)
    assert out["06037"]["NAME"] == "Los Angeles County"
    assert out["06037"]["median_household_income"] == pytest.approx(98_000)


def test_build_county_values_falls_back_to_plain_mean_without_weights(tmp_path):
    _write_2022_region_frames(tmp_path)
    (tmp_path / "B01003_county_*_2022.parquet").unlink()

    out = build_county_values(tmp_path, 2022)

    expected = (100_000 + 80_000) / 2
    assert out["09001"]["median_household_income"] == pytest.approx(expected)


def test_build_county_trends_for_state_crosswalks_each_vintage(tmp_path):
    _write_2022_region_frames(tmp_path)
    _write_county_parquet(
        tmp_path,
        "B19013",
        2020,
        [
            {"state": 9, "county": 1, "NAME": "Fairfield County", "B19013_001E": 95_000},
            {"state": 9, "county": 15, "NAME": "Windham County", "B19013_001E": 70_000},
        ],
    )

    trends = build_county_trends_for_state(tmp_path, "09", [2020, 2022])

    by_geoid = trends["byGeoid"]
    assert "09110" not in by_geoid
    assert by_geoid["09001"]["NAME"] == "Fairfield County"
    income = by_geoid["09001"]["median_household_income"]
    assert income["2020"] == pytest.approx(95_000)
    expected_2022 = (100_000 * 300_000 + 80_000 * 400_000) / (300_000 + 400_000)
    assert income["2022"] == pytest.approx(expected_2022)
    assert by_geoid["09015"]["median_household_income"]["2020"] == pytest.approx(70_000)
    assert by_geoid["09015"]["median_household_income"]["2022"] == pytest.approx(72_000)
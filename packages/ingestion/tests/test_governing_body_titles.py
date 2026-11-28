"""Meeting title -> governing body (#1442): the Python twin of the dbt resolution, on real titles."""

from __future__ import annotations

import csv

import pytest

from ingestion.governance.body_titles import (
    clean_title,
    default_seed_path,
    display_name,
    jurisdiction_kind,
    load_patterns,
    match_body,
    slug,
)

PATTERNS = load_patterns()


def _examples() -> list[dict[str, str]]:
    with open(default_seed_path("governing_body_title_example.csv"), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("row", _examples(), ids=lambda r: r["title"][:50])
def test_example_seed(row: dict[str, str]) -> None:
    """Every real title in the shared example seed resolves as expected (the dbt test checks the SQL on the same rows)."""
    got = match_body(row["title"], row["jurisdiction_name"], row["jurisdiction_type"], PATTERNS)
    assert (got.body_key if got else "") == row["expected_body_key"]
    assert ((got.body_name or "") if got else "") == row["expected_body_name"]


def test_tuscaloosa_bodies() -> None:
    city = ("Tuscaloosa", "city")
    cases = {
        "Tuscaloosa City Council Meeting - Nov 17, 2026": ("governing_body", "City Council"),
        "Tuscaloosa Planning and Zoning Commission Meeting - Nov 16, 2026": ("planning_zoning", "Planning and Zoning Commission"),
        "Tuscaloosa Zoning Board of Adjustments": ("board_of_adjustment", "Zoning Board of Adjustment"),
        "Tuscaloosa Finance Committee Meeting - Oct 27, 2026": ("committee:finance_committee", "Finance Committee"),
    }
    for title, (key, name) in cases.items():
        got = match_body(title, *city, PATTERNS)
        assert got is not None and got.body_key == key and got.body_name == name, title
    # A pre-council briefing is a session of the council; it does not rename the body.
    briefing = match_body("Tuscaloosa Pre-Council Briefing - Nov 03, 2026", *city, PATTERNS)
    assert briefing is not None and briefing.body_key == "governing_body" and briefing.body_name is None


def test_county_body_in_a_city_video_is_not_the_citys() -> None:
    assert match_body("Tuscaloosa County Commission Meeting 11/2/2026", "Tuscaloosa", "city", PATTERNS) is None
    got = match_body("Tuscaloosa County Commission Meeting 11/2/2026", "Tuscaloosa County", "county", PATTERNS)
    assert got is not None and got.body_key == "governing_body" and got.body_type == "county_commission"


def test_school_district_board_is_the_school_board() -> None:
    got = match_body("Regular Board Meeting - 6/24/2025", "Bloomfield School District", "school_district", PATTERNS)
    assert got is not None and (got.body_key, got.body_type) == ("school_board", "school_board")
    # The same words in a city are not a body.
    assert match_body("Regular Board Meeting - 6/24/2025", "Bloomfield", "city", PATTERNS) is None


def test_a_person_named_in_a_title_is_not_a_body() -> None:
    assert match_body("Commissioner Ammons and Councilor Williams talk Collaboration", "Jefferson County", "county", PATTERNS) is None
    assert match_body("Mayor Steven L. Reed's Speech from E.D. Nixon School", "Montgomery", "city", PATTERNS) is None


def test_clean_title_drops_dates_place_and_filler() -> None:
    assert clean_title("Tuscaloosa City Council Meeting - Nov 17, 2026", "Tuscaloosa") == "city council"
    assert clean_title("City of Brentwood - Board of Aldermen - October 20, 2025", "Brentwood") == "board of aldermen"
    assert clean_title("Town of Nashville NC, Council Meeting (January 17th, 2023)", "Nashville") == "council"
    assert clean_title("Dover MA Selectmen's Meeting of May 14, 2014", "Dover") == "selectmen"
    assert clean_title("Chilton County Commission Work Session 6/22/26", "Chilton County") == "county commission work session"


def test_helpers() -> None:
    assert display_name("planning and zoning commission") == "Planning and Zoning Commission"
    assert display_name("board of estimate and apportionment") == "Board of Estimate and Apportionment"
    assert slug("budget & appropriations committee") == "budget_and_appropriations_committee"
    assert jurisdiction_kind("town") == "municipal"
    assert jurisdiction_kind("county") == "county"


def test_seed_is_ordered_and_skips_come_first() -> None:
    priorities = [p.priority for p in PATTERNS]
    assert priorities == sorted(priorities)
    skip = [p for p in PATTERNS if p.body_key == "__skip__"]
    first_governing = min(p.priority for p in PATTERNS if p.body_key == "governing_body")
    assert skip and all(p.priority < first_governing for p in skip)

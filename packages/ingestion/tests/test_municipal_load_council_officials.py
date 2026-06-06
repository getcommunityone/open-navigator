"""Unit tests for the council-officials loader (no network, no DB).

Guards the INSERT plumbing: the column list, the VALUES template placeholders,
and shape_row() must stay the same width, and a scraped biography must reach the
last positional slot (it flows bronze.bronze_officials_scraped.biography ->
contact_official.biography -> the PersonDetail page).
"""

from ingestion.municipal.load_council_officials import (
    _INSERT_COLUMNS,
    _INSERT_TEMPLATE,
    shape_row,
    synthesize_membership_id,
)
from scrapers.municipal.council_roster import CouncilMember

_BATCH = "00000000-0000-0000-0000-000000000000"


def test_insert_columns_template_and_shape_row_stay_aligned():
    member = CouncilMember(
        "Jane Doe", "City Councilor", "Northport Government", "AL", "Alabama",
        district="District 1", biography="A short bio.",
    )
    row = shape_row(_BATCH, member)
    assert len(_INSERT_COLUMNS) == _INSERT_TEMPLATE.count("%s") == len(row)


def test_shape_row_carries_biography_in_last_slot():
    member = CouncilMember(
        "Jane Doe", "City Councilor", "Northport Government", "AL", "Alabama",
        district="District 1", biography="Personal Profile\nServed since 2025.",
    )
    row = shape_row(_BATCH, member)
    assert _INSERT_COLUMNS[-1] == "biography"
    assert row[-1] == "Personal Profile\nServed since 2025."


def test_shape_row_blanks_empty_biography_to_none():
    member = CouncilMember(
        "Jane Doe", "City Councilor", "Northport Government", "AL", "Alabama",
        district="District 1", biography="",
    )
    row = shape_row(_BATCH, member)
    assert row[-1] is None


def test_membership_id_is_deterministic_and_scoped():
    member = CouncilMember(
        "Jane Doe", "City Councilor", "Northport Government", "AL", "Alabama",
        district="District 1",
    )
    mid = synthesize_membership_id(member)
    assert mid.startswith("ocd-membership/scraped-")
    assert synthesize_membership_id(member) == mid  # stable across calls

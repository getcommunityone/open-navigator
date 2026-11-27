"""Who supported and opposed a decision, from the record's speaker slugs (#1320).

The slugs below are the shapes the meeting analysis writes into event_decision.competing_views (the Tuscaloosa ones are
quoted from the record behind "Prohibiting firearm possession while under the influence"); the official rows are test
stand-ins for person_government.
"""

from __future__ import annotations

import pytest

from api.routes.decision_people import OfficialIndex, decision_people, is_school_board, person_for, vote_counts

OFFICIALS = OfficialIndex(
    [
        {"full_name": "John Faile", "title": "City Councilor", "jurisdiction": "Tuscaloosa Government", "state_code": "AL"},
        {"full_name": "Joseph Eatmon, Sr.", "title": "City Councilor", "jurisdiction": "Tuscaloosa Government", "state_code": "AL"},
    ]
)


def who(slug: str, *, place: str | None = "Tuscaloosa", school: bool = False):
    return person_for(slug, jurisdiction_name=place, state_code="AL", school_board=school, officials=OFFICIALS)


def test_official_matched_to_the_officials_record_gets_canonical_name_and_title():
    assert who("john_faile_councilor_tuscaloosa") == {"name": "John Faile", "role": "City Councilor", "kind": "official"}
    assert who("joseph_eatmon_sr_councilor_tuscaloosa")["name"] == "Joseph Eatmon, Sr."


def test_unmatched_official_title_keeps_the_slug_title():
    assert who("lee_busby_councilor_tuscaloosa") == {"name": "Lee Busby", "role": "Councilor", "kind": "official"}


def test_a_title_heard_as_address_stays_in_the_name_with_no_role():
    # "chief_sky_unknown": the role word is "unknown", so no role is claimed; "Chief" is how they were addressed.
    assert who("chief_sky_unknown_tuscaloosa") == {"name": "Chief Sky", "role": None, "kind": "official"}


def test_a_non_official_is_first_l_with_no_role():
    assert who("scott_holmes_unknown_tuscaloosa") == {"name": "Scott H.", "role": None, "kind": "resident"}
    assert who("caroline_pantskey_resident_oshkosh", place=None)["name"] == "Caroline P."


@pytest.mark.parametrize(
    "slug",
    [
        "ian_miller_student_north_reading_2501748955",  # a student: never shown
        "unknown_unknown_unknown_pickens_13227",  # no name
        "mrs_gonzalez_north_reading",  # an honorific and a surname is not a first name
        "robey_oshkosh",  # one word may be a surname
        "david_zumwalt_former_homeless_drug_addict_federal_way_5323515",  # a description runs into the name
        "lawrence_biloxi_2806220",  # no role word and no place to tell the name from
        "artist_murphy_entrepreneur_federal_way",  # no role word and three words: where the name ends is a guess
    ],
)
def test_left_out(slug):
    assert who(slug, place=None if "biloxi" in slug else "Federal Way") is None


def test_no_resident_at_a_school_board_but_officials_still_shown():
    assert who("scott_holmes_unknown_tuscaloosa", school=True) is None
    assert who("lee_busby_councilor_tuscaloosa", school=True)["name"] == "Lee Busby"
    assert is_school_board("Tuscaloosa City Board of Education") and is_school_board(None, jurisdiction_type="school_district")
    assert not is_school_board("Tuscaloosa", "City Council")


def test_decision_people_sides_order_and_opposition():
    cv = {
        "dominant_view": {
            "view_label": "Prohibit firearm possession while impaired",
            "held_by": ["scott_holmes_unknown_tuscaloosa", "chief_sky_unknown_tuscaloosa", "john_faile_councilor_tuscaloosa"],
        },
        "counter_views": [],
    }
    out = decision_people(cv, speakers=["john_faile_councilor_tuscaloosa", "kip_tyner_councilor_tuscaloosa"],
                          jurisdiction_name="Tuscaloosa", state_code="AL", school_board=False, officials=OFFICIALS)
    # Officials with a role, then officials without, then everyone else.
    assert [p["name"] for p in out["supported_by"]] == ["John Faile", "Chief Sky", "Scott H."]
    assert out["opposed_by"] == [] and out["opposition_recorded"] is False
    # A speaker already on a side is not repeated.
    assert [p["name"] for p in out["spoke_on_it"]] == ["Kip Tyner"]
    assert out["supported_view"] == "Prohibit firearm possession while impaired"


def test_counter_view_without_names_is_still_recorded_opposition():
    out = decision_people({"dominant_view": {"held_by": []}, "counter_views": [{"view_label": "No"}]},
                          jurisdiction_name="X", state_code="AL", school_board=False)
    assert out["opposition_recorded"] is True and out["opposed_by"] == []


def test_no_competing_views_claims_nothing():
    out = decision_people(None, jurisdiction_name="X", state_code="AL", school_board=False)
    assert out["opposition_recorded"] is None and out["supported_by"] == []


def test_vote_counts():
    assert vote_counts({"yes": 11, "no": 0}) == (11, 0)
    assert vote_counts({"yes": None, "no": None}) == (None, None)
    assert vote_counts(None) == (None, None)

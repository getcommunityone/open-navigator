"""Unit tests for the CivicSearch → jurisdiction resolver (pure logic, no DB).

Cover the three matching regimes that the resolver has to get right:
  * municipal name with a legal-status suffix ("Johnson City" ~ "Johnson City"),
  * school-district abbreviation vs full NCES name where pure nearest-centroid
    mis-picks ("Austin Isd" must beat the geographically-closer "Eanes ISD"),
  * Canadian / unknown state tokens that must stay unresolved.
"""
from __future__ import annotations

from scrapers.youtube.enrich_civicsearch_jurisdictions import (
    Jurisdiction,
    core_tokens,
    parse_location,
    resolve_place,
    resolve_state_code,
)


def _juris(jid, name, jtype, code, lat, lon) -> Jurisdiction:
    return Jurisdiction(
        jurisdiction_id=jid,
        name=name,
        jurisdiction_type=jtype,
        state_code=code,
        state={"TX": "Texas", "TN": "Tennessee"}.get(code, code),
        latitude=lat,
        longitude=lon,
        core_place=core_tokens(name, is_school=False),
        core_school=core_tokens(name, is_school=True),
    )


def test_parse_location_uses_last_comma():
    assert parse_location("Johnson City, TN") == ("Johnson City", "TN")
    assert parse_location("Winston-Salem, NC") == ("Winston-Salem", "NC")
    assert parse_location("New Haven School District, Connecticut") == (
        "New Haven School District",
        "Connecticut",
    )
    assert parse_location("NoComma") == ("NoComma", "")


def test_resolve_state_code_abbrev_and_fullname():
    name_to_code = {"texas": "TX", "connecticut": "CT"}
    valid = {"TX", "CT", "TN"}
    assert resolve_state_code("TN", name_to_code, valid) == "TN"
    assert resolve_state_code("Texas", name_to_code, valid) == "TX"
    # Canadian province → no US code.
    assert resolve_state_code("British Columbia", name_to_code, valid) is None
    assert resolve_state_code("", name_to_code, valid) is None


def test_school_name_token_beats_nearer_centroid():
    by_state = {
        "TX": [
            # Geographically closest to the Austin city centroid, wrong by name.
            _juris("school_district_eanes", "Eanes Independent School District",
                   "school_district", "TX", 30.30, -97.80),
            # Farther centroid, but the correct district by name.
            _juris("school_district_austin", "Austin Independent School District",
                   "school_district", "TX", 30.20, -97.69),
        ]
    }
    res = resolve_place(
        "Austin Isd", "TX", 30.27, -97.74, is_school=True, by_state=by_state
    )
    assert res is not None
    assert res.jurisdiction_id == "school_district_austin"
    assert res.confidence == "high"


def test_municipal_suffix_match():
    by_state = {
        "TN": [
            _juris("municipality_johnson", "Johnson City", "municipality", "TN",
                   36.31, -82.35),
        ]
    }
    res = resolve_place(
        "Johnson City", "TN", 36.31, -82.35, is_school=False, by_state=by_state
    )
    assert res is not None
    assert res.jurisdiction_id == "municipality_johnson"
    assert res.confidence == "high"


def test_unresolved_when_no_state():
    by_state = {"TX": [_juris("m", "Austin", "municipality", "TX", 30.2, -97.7)]}
    assert (
        resolve_place("Austin", None, 30.2, -97.7, is_school=False, by_state=by_state)
        is None
    )

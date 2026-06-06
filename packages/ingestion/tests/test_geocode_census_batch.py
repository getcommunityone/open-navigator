"""Unit tests for the Census batch geocoder CSV parser and request building."""
from __future__ import annotations

from ingestion.geocode.census_batch import (  # noqa: E402
    CensusAddress,
    CensusBatchGeocoder,
    build_census_csv,
    parse_census_csv,
)
from ingestion.geocode.backfill_places import normalize_key  # noqa: E402


# Real-shape Census response: header-less, coordinate field is "lon,lat".
_MATCH_ROW = (
    '"1","1600 Pennsylvania Ave NW, Washington, DC, 20500","Match","Exact",'
    '"1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500",'
    '"-77.03518753691,38.89869893252","76225813","L"'
)
_NO_MATCH_ROW = '"2","Nowhere Rd, Atlantis, ZZ, 00000","No_Match"'
_TIE_ROW = '"3","123 Main St, Springfield, IL","Tie"'


def test_parse_match_row_splits_lon_lat_correctly():
    results = parse_census_csv(_MATCH_ROW + "\n")
    assert len(results) == 1
    r = results[0]
    assert r.record_id == "1"
    assert r.matched is True
    # Latitude ~38.9 (DC), longitude ~-77.0 — order must be swapped from CSV.
    assert r.latitude == 38.89869893252
    assert r.longitude == -77.03518753691
    assert r.matched_address and r.matched_address.startswith("1600 PENNSYLVANIA")


def test_parse_no_match_row_yields_unmatched_with_no_coords():
    results = parse_census_csv(_NO_MATCH_ROW + "\n")
    assert len(results) == 1
    r = results[0]
    assert r.record_id == "2"
    assert r.matched is False
    assert r.latitude is None
    assert r.longitude is None
    assert r.matched_address is None


def test_parse_tie_row_is_treated_as_unmatched():
    results = parse_census_csv(_TIE_ROW + "\n")
    assert results[0].matched is False
    assert results[0].latitude is None


def test_parse_mixed_body_preserves_all_ids_and_order():
    body = "\n".join([_MATCH_ROW, _NO_MATCH_ROW, _TIE_ROW]) + "\n"
    results = parse_census_csv(body)
    assert [r.record_id for r in results] == ["1", "2", "3"]
    assert [r.matched for r in results] == [True, False, False]


def test_parse_skips_blank_lines_and_empty_ids():
    body = _MATCH_ROW + "\n\n" + ',"x","Match"\n'
    results = parse_census_csv(body)
    # Blank line dropped; row with empty id dropped.
    assert [r.record_id for r in results] == ["1"]


def test_parse_malformed_coord_demotes_to_unmatched():
    bad = (
        '"9","addr","Match","Exact","ADDR","not-a-coord","123","L"'
    )
    r = parse_census_csv(bad + "\n")[0]
    assert r.matched is False
    assert r.latitude is None


def test_build_census_csv_emits_id_street_city_state_zip():
    csv_text = build_census_csv(
        [
            CensusAddress("k1", "1600 Pennsylvania Ave NW", "Washington", "DC", "20500"),
            CensusAddress("k2", "Dacas Lane", "Gulf Shores", "AL"),
        ]
    )
    lines = csv_text.strip().splitlines()
    assert lines[0] == "k1,1600 Pennsylvania Ave NW,Washington,DC,20500"
    assert lines[1] == "k2,Dacas Lane,Gulf Shores,AL,"


def test_geocode_batch_rejects_oversized_input():
    g = CensusBatchGeocoder(max_batch=2)
    addrs = [CensusAddress(str(i), "x") for i in range(3)]
    try:
        g.geocode_batch(addrs)
    except ValueError as exc:
        assert "limited to 2" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for oversized batch")


def test_geocode_batch_empty_is_noop():
    assert CensusBatchGeocoder().geocode_batch([]) == []


def test_normalize_key_collapses_whitespace_and_lowercases():
    assert normalize_key("  32054  Bartell   Street, Lillian, AL ") == (
        "32054 bartell street, lillian, al"
    )
    assert normalize_key("") == ""

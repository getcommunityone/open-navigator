"""County → Wikidata item matching must use the full 5-digit FIPS and the state (issue #461).

Fixtures mirror the real collision: Allen County, Indiana (FIPS 18003, Q493443)
was given Baldwin County, Alabama's item (FIPS 01003, Q156163) because both
counties have county code 003 and Alabama (01) sorted first.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scrapers.wikidata import parquet_qid_lookup as pql
from scrapers.wikidata.fips_match import (
    county_fips_literals,
    county_item_matches,
    county_p882_to_geoid,
    municipality_wd_literal_sets,
    normalize_county_geoid,
)
from scrapers.wikidata.geography_qid_cache import GeographyQidCache, cache_key
from scrapers.wikidata.rehydrate_county_qids import (
    ITEM_COLUMNS,
    AuditResult,
    entity_to_row,
    is_local_database,
    item_matches_row,
    local_database_url,
    plan_updates,
    redact_url,
    resolve_county_qid,
    summarize,
)

BALDWIN_AL = ("Q156163", "01003")
ALLEN_IN = ("Q493443", "18003")
CAMUY_PR = ("Q2380860", "72027")
BELL_TX = ("Q108428", "48027")


# --- literals -----------------------------------------------------------------


def test_county_literals_are_only_the_full_fips() -> None:
    assert county_fips_literals("18003", "18") == {"18003"}
    assert county_fips_literals("18-003") == {"18003"}
    # The bare tails that used to be emitted ("003", "8003") are gone.
    assert "003" not in county_fips_literals("18003", "18")
    assert "8003" not in county_fips_literals("18003", "18")


def test_county_literals_reject_state_disagreement_and_short_codes() -> None:
    assert county_fips_literals("18003", "01") == set()
    assert county_fips_literals("003", "18") == set()
    assert county_fips_literals("1003", "01") == {"01003"}  # lost leading zero


def test_p882_short_code_needs_a_known_state() -> None:
    assert county_p882_to_geoid("003") is None
    assert county_p882_to_geoid("003", "18") == "18003"
    assert county_p882_to_geoid("01003", "18") is None
    assert county_p882_to_geoid("01-003") == "01003"
    assert normalize_county_geoid("abc") is None


def test_item_match_requires_exact_fips_and_state() -> None:
    assert county_item_matches("18003", ["18003"], "18")
    assert not county_item_matches("18003", ["01003"], "01")
    assert not county_item_matches("18003", ["01003"])
    # A bare "003" on an Alabama item never matches Indiana's 18003.
    assert not county_item_matches("18003", ["003"], "01")
    assert county_item_matches("01003", ["003"], "01")


def test_municipality_literals_keep_the_state_prefix() -> None:
    fl, gl = municipality_wd_literal_sets("1807000", "2394712")
    assert fl == {"1807000"}
    assert "07000" not in fl
    assert gl == {"2394712"}
    fl6, _ = municipality_wd_literal_sets("100100", None)  # 01-00100 lost its zero
    assert fl6 == {"0100100"}
    fl5, _ = municipality_wd_literal_sets("07000", None)  # no state → no FIPS literal
    assert fl5 == set()


# --- geography cache ----------------------------------------------------------


def test_cache_never_resolves_18003_to_an_alabama_item(tmp_path: Path) -> None:
    cache = GeographyQidCache(cache_dir=tmp_path)
    # Legacy poisoned keys (the old namespace) are ignored by the lookup.
    cache.set_q(cache_key("county", "882", "003"), BALDWIN_AL[0])
    cache.set_q(cache_key("county", "882", "18003"), BALDWIN_AL[0])
    cache.remember_county(BALDWIN_AL[0], "003", None, None)  # short P882 is dropped
    cache.remember_county(BALDWIN_AL[0], BALDWIN_AL[1], None, None)
    assert cache.lookup_q_for_county(county_fips_literals("18003", "18")) is None
    cache.remember_county(ALLEN_IN[0], ALLEN_IN[1], None, None)
    assert cache.lookup_q_for_county(county_fips_literals("18003", "18")) == ALLEN_IN[0]
    assert cache.lookup_q_for_county(county_fips_literals("01003", "01")) == BALDWIN_AL[0]
    # Even a caller passing the old tails cannot hit anything.
    assert cache.lookup_q_for_county({"003", "8003"}) is None


def test_cache_marks_two_items_for_one_fips_ambiguous(tmp_path: Path) -> None:
    cache = GeographyQidCache(cache_dir=tmp_path)
    cache.remember_county("Q1", "18003", None, None)
    cache.remember_county("Q2", "18003", None, None)
    assert cache.lookup_q_for_county({"18003"}) is None


def test_cache_does_not_warm_counties_from_bronze_rows(tmp_path: Path) -> None:
    cache = GeographyQidCache(cache_dir=tmp_path)
    cache.warm_from_enriched_rows("county", "IN", [("18003", None, BALDWIN_AL[0])])
    assert cache.lookup_q_for_county({"18003"}) is None


# --- parquet index ------------------------------------------------------------


def test_parquet_index_drops_ambiguous_and_never_matches_county_tail(monkeypatch) -> None:
    rows = [
        (BALDWIN_AL[0], BALDWIN_AL[1], None),
        (ALLEN_IN[0], ALLEN_IN[1], None),
        ("Q999", "003", None),  # an item storing only the county code
        ("Q7", "48027", None),
        ("Q8", "48027", None),  # two items claim 48027
        ("Q50", None, "18003"),  # a GNIS id that equals a county FIPS
    ]
    monkeypatch.setattr(pql, "iter_parquet_rows", lambda *_a, **_k: iter(rows))
    fips_index, gnis_index = pql.build_parquet_indexes(Path("unused.parquet"))
    assert "48027" not in fips_index
    lits = county_fips_literals("18003", "18")
    # County FIPS literals are never looked up in the GNIS index.
    assert pql.lookup_qid_from_literals(lits, set(), fips_index, gnis_index) == ALLEN_IN[0]
    assert pql.lookup_qid_from_literals(county_fips_literals("01003", "01"), set(), fips_index, gnis_index) == BALDWIN_AL[0]


# --- re-hydration decisions ---------------------------------------------------


def test_audit_flags_the_wrong_state_item() -> None:
    assert not item_matches_row("18003", {"p882": {"01003"}, "state_fips": {"01"}})
    assert not item_matches_row("48027", {"p882": {"72027"}, "state_fips": {"72"}})
    assert item_matches_row("18003", {"p882": {"18003"}, "state_fips": {"18"}})
    assert not item_matches_row("18003", {"p882": set(), "state_fips": set()})


def test_resolve_picks_the_in_state_item() -> None:
    assert resolve_county_qid("18003", [(ALLEN_IN[0], "18", True)]) == (ALLEN_IN[0], "resolved")
    # An item in another state carrying the same code is dropped.
    assert resolve_county_qid("18003", [(BALDWIN_AL[0], "01", True), (ALLEN_IN[0], "18", True)])[0] == ALLEN_IN[0]
    assert resolve_county_qid("18003", [(BALDWIN_AL[0], "01", True)]) == (None, "no_item")
    assert resolve_county_qid("18003", []) == (None, "no_item")


def test_resolve_prefers_the_county_over_a_village_with_the_same_fips() -> None:
    # King George County, VA vs Port Conway (an unincorporated community with P882 51099).
    got = resolve_county_qid("51099", [("Q1375967", "51", False), ("Q2613700", "51", True)])
    assert got == ("Q2613700", "resolved_county_type")
    assert resolve_county_qid("51099", [("Qa", "51", True), ("Qb", "51", True)]) == (None, "ambiguous")


def test_entity_to_row_maps_item_columns() -> None:
    entity = {
        "modified": "2026-10-01T12:00:00Z",
        "claims": {
            "P856": [{"rank": "normal", "mainsnak": {"datavalue": {"value": "https://www.allencounty.in.gov/"}}}],
            "P882": [{"rank": "normal", "mainsnak": {"datavalue": {"value": "18003"}}}],
            "P1082": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {"amount": "+385410"}}}}],
            "P2046": [
                {
                    "rank": "normal",
                    "mainsnak": {
                        "datavalue": {
                            "value": {"amount": "+660", "unit": "http://www.wikidata.org/entity/Q232291"}
                        }
                    },
                }
            ],
            "P6": [
                {
                    "rank": "normal",
                    "mainsnak": {"datavalue": {"value": {"id": "Q42"}}},
                    "qualifiers": {"P580": [{"datavalue": {"value": {"time": "+2021-01-00T00:00:00Z"}}}]},
                }
            ],
        },
    }
    row = entity_to_row(entity, ALLEN_IN[0], {"Q42": "A. Commissioner"})
    assert set(row) == set(ITEM_COLUMNS)
    assert row["wikidata_id"] == ALLEN_IN[0]
    assert row["official_website"] == "https://www.allencounty.in.gov/"
    assert row["wikidata_fips_code"] == "18003"
    assert row["population"] == 385410
    assert row["area_sq_km"] == pytest.approx(660 * 2.589988, rel=1e-4)
    assert row["head_of_government"] == "A. Commissioner"
    assert row["head_of_government_start_time"] == "2021-01-01T00:00:00"
    assert row["facebook_url"] is None


def test_apply_is_local_only() -> None:
    assert is_local_database("postgresql://postgres:x@localhost:5433/open_navigator")
    assert not is_local_database("postgresql://u:p@ep-x.us-east-2.aws.neon.tech/db")


def test_local_url_ignores_a_cloud_open_navigator_url(monkeypatch) -> None:
    monkeypatch.delenv("OPEN_NAVIGATOR_LOCAL_DATABASE_URL", raising=False)
    monkeypatch.setenv("OPEN_NAVIGATOR_DATABASE_URL", "postgresql://u:p@ep-x.neon.tech/db")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    url = local_database_url()
    assert is_local_database(url)
    assert "pw" not in redact_url(url)


def _audit_fixture() -> AuditResult:
    res = AuditResult(rows=[], items={})
    res.mismatched = [
        ("18003", "IN", BALDWIN_AL[0]),  # resolves to Allen County, IN
        ("48027", "TX", CAMUY_PR[0]),  # no trustworthy in-state item
    ]
    res.resolutions = {"18003": (ALLEN_IN[0], "resolved"), "48027": (None, "ambiguous")}
    return res


def test_plan_updates_rehydrates_resolved_and_clears_the_rest() -> None:
    res = _audit_fixture()
    hydrated = {
        ALLEN_IN[0]: {
            **{c: None for c in ITEM_COLUMNS},
            "wikidata_id": ALLEN_IN[0],
            "official_website": "https://www.allencounty.in.gov/",
            "wikidata_fips_code": "003",  # short first claim: stamped with the matched GEOID
        }
    }
    updates = dict(plan_updates(res, hydrated))
    assert updates["18003"]["wikidata_id"] == ALLEN_IN[0]
    assert updates["18003"]["wikidata_fips_code"] == "18003"
    assert all(v is None for v in updates["48027"].values())
    assert set(updates["48027"]) == set(ITEM_COLUMNS)


def test_summarize_counts_wrong_websites_and_their_fate() -> None:
    res = _audit_fixture()
    updates = [
        ("18003", {"official_website": "https://www.allencounty.in.gov/"}),
        ("48027", {"official_website": None}),
    ]
    current = {
        "18003": ("Allen County", "https://baldwincountyal.gov/"),
        "48027": ("Bell County", "http://www.gobierno.pr/OCAM/DirectorioMunicipios/Camuy.htm"),
    }
    assert summarize(res, updates, current) == {
        "rows_with_wrong_item_website": 2,
        "websites_replaced_with_own_item": 1,
        "websites_cleared_no_own_website": 1,
        "websites_same_after_fix": 0,
    }

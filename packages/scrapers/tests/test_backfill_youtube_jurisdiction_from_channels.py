"""Unit tests for the channel→jurisdiction backfill resolver (pure logic, no DB).

The hard part is namespace reconciliation: bronze and ``int_jurisdictions`` key on
slug-form ids (``dekalb_1719161``), while the channel catalog also carries a foreign
``municipality_1719161`` form for the SAME place. Both must collapse to the one slug
id, deduped by their shared trailing geoid. Cover:
  * a foreign ``<type>_<geoid>`` entry reconciled to the canonical slug id,
  * duplicate id forms of one place → a single high-confidence pick,
  * a genuine multi-jurisdiction channel → low confidence, most-specific-type pick,
  * an unresolvable id (no geoid match) → ``None``.
"""
from __future__ import annotations

from scrapers.youtube.backfill_youtube_jurisdiction_from_channels import (
    JurisInfo,
    _geoid_of,
    _to_canonical,
    resolve_from_catalog,
)

# Minimal int_jurisdictions stand-ins (slug-form ids, the namespace bronze uses).
_LOOKUP = {
    "dekalb_1719161": JurisInfo("DeKalb", "IL", "Illinois", "municipality"),
    "floresville_4826160": JurisInfo("Floresville", "TX", "Texas", "municipality"),
    "wilson_4879612": JurisInfo("Wilson", "TX", "Texas", "municipality"),
    "carver_2502311665": JurisInfo("Carver", "MA", "Massachusetts", "township"),
    "howell_3402533300": JurisInfo("Howell", "NJ", "New Jersey", "township"),
    "monmouth_34025": JurisInfo("Monmouth County", "NJ", "New Jersey", "county"),
}
_GEOID_INDEX = {_geoid_of(jid): {jid} for jid in _LOOKUP}


def _entry(jid, name=None, jtype=None, sc=None):
    return {
        "jurisdiction_id": jid,
        "jurisdiction_name": name,
        "jurisdiction_type": jtype,
        "state_code": sc,
    }


def test_geoid_extraction():
    assert _geoid_of("dekalb_1719161") == "1719161"
    assert _geoid_of("municipality_1719161") == "1719161"
    assert _geoid_of("susquehanna_42115") == "42115"
    assert _geoid_of("no-digits") is None


def test_foreign_type_form_reconciles_to_slug():
    # The catalog's municipality_<geoid> must map onto the slug id bronze uses.
    assert _to_canonical("municipality_1719161", _GEOID_INDEX, _LOOKUP) == "dekalb_1719161"
    # A slug id that lacks int_jurisdictions backing is still recovered by geoid.
    assert _to_canonical("carver_2502311665", _GEOID_INDEX, _LOOKUP) == "carver_2502311665"
    # No geoid → unresolvable.
    assert _to_canonical("statewide", _GEOID_INDEX, _LOOKUP) is None


def test_single_place_duplicate_forms_high_confidence():
    # DeKalb expressed three ways (foreign type form + two slug forms) is ONE place.
    juris = [
        _entry("municipality_1719161", "DeKalb city", "municipality", "IL"),
        _entry("dekalb_1719161", "DeKalb city", None, "IL"),
        _entry("dekalb_1719161", "DeKalb", None, "IL"),
    ]
    res = resolve_from_catalog(juris, _LOOKUP, _GEOID_INDEX)
    assert res is not None
    assert res.jurisdiction_id == "dekalb_1719161"
    assert res.confidence == "high"
    assert res.method == "catalog_single"
    # Name/state come from int_jurisdictions (authoritative), not the JSONB.
    assert res.jurisdiction_name == "DeKalb"
    assert res.state_code == "IL"


def test_county_plus_single_town_is_medium_picks_town():
    # A parent county plus exactly one local jurisdiction is the venue, not
    # ambiguity — pick the town, flag medium (not low).
    juris = [
        _entry("monmouth_34025", "Monmouth County", "county", "NJ"),
        _entry("howell_3402533300", "Howell township", "township", "NJ"),
    ]
    res = resolve_from_catalog(juris, _LOOKUP, _GEOID_INDEX)
    assert res is not None
    assert res.confidence == "medium"
    assert res.method == "catalog_county_town"
    assert res.jurisdiction_id == "howell_3402533300"


def test_genuine_multi_jurisdiction_low_confidence_specificity_pick():
    # A regional channel covering two distinct towns → low confidence; the tie
    # breaks to the most specific type, then the lowest geoid (Floresville).
    juris = [
        _entry("municipality_4826160", "Floresville city", "municipality", "TX"),
        _entry("municipality_4879612", "Wilson city", "municipality", "TX"),
        _entry("floresville_4826160", "Floresville", None, "TX"),
    ]
    res = resolve_from_catalog(juris, _LOOKUP, _GEOID_INDEX)
    assert res is not None
    assert res.confidence == "low"
    assert res.method == "catalog_multi"
    assert res.jurisdiction_id == "floresville_4826160"


def test_unresolvable_array_returns_none():
    assert resolve_from_catalog([_entry("statewide")], _LOOKUP, _GEOID_INDEX) is None
    assert resolve_from_catalog([], _LOOKUP, _GEOID_INDEX) is None

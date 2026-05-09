"""
Unit tests for wbsearchentities-aligned county reconciliation helpers.

Run:
  .venv/bin/pytest tests/test_wikidata_entity_search.py -q

Optional live API smoke (network + respects WIKIDATA_* env from .env):
  RUN_WIKIDATA_LIVE=1 .venv/bin/pytest tests/test_wikidata_entity_search.py -q -k live
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.datasources.wikidata import wikidata_entity_search as wes
from scripts.datasources.wikidata import wikidata_hybrid_sql


def test_county_search_strings_includes_state_phrases() -> None:
    s = wes.county_search_strings("Kent County", "Delaware")
    assert "Kent County" in s
    assert any("Delaware" in x for x in s)


def test_county_search_strings_strips_county_suffix_variant() -> None:
    s = wes.county_search_strings("Orleans Parish", "Louisiana")
    assert any("Orleans" in x and "Louisiana" in x for x in s)


def _claim_string(pid: str, text: str) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": pid,
            "datavalue": {"value": text, "type": "string"},
        },
        "type": "statement",
    }


def test_entity_claim_identifier_literals_p882_match() -> None:
    entity = {
        "claims": {
            "P882": [_claim_string("P882", "01001")],
        }
    }
    ok, seen = wes.entity_claim_identifier_literals(entity, {"01001", "1001", "01"})
    assert ok
    assert "01001" in seen or "1001" in seen


def test_county_bulk_by_state_sparql_contains_state_and_p131() -> None:
    q = wikidata_hybrid_sql.county_bulk_by_state_sparql("wd:Q47168", "Q1393", limit_rows=100)
    assert "wd:Q47168" in q
    assert "wd:Q1393" in q
    assert "wdt:P131" in q
    assert "P882" in q


def test_entity_claim_identifier_literals_no_match() -> None:
    entity = {
        "claims": {
            "P882": [_claim_string("P882", "99999")],
        }
    }
    ok, _ = wes.entity_claim_identifier_literals(entity, {"01001"})
    assert not ok


@pytest.mark.asyncio
async def test_live_wbsearchentities_kent_delaware_smoke() -> None:
    """Hits api.wikidata.org — run with RUN_WIKIDATA_LIVE=1 only."""
    if os.getenv("RUN_WIKIDATA_LIVE", "").strip().lower() not in ("1", "true", "yes"):
        pytest.skip("Set RUN_WIKIDATA_LIVE=1 to run live Wikidata API smoke test")

    from dotenv import load_dotenv

    load_dotenv()
    from scripts.datasources.wikidata.wikidata_integration import WikidataQuery

    wd = WikidataQuery()
    hits = await wd.wikibase_search_entities("Kent County, Delaware", limit=8)
    assert isinstance(hits, list)
    ids = [h["id"] for h in hits if h.get("id", "").startswith("Q")]
    assert ids, "expected at least one Q-id from wbsearchentities"

    ents = await wd.wikibase_get_entities(ids[:5], wikibase_props="labels|claims")
    # Kent County, Delaware is a known FIPS structure — at least one hit should carry P882 10001-style
    matched = False
    for qid, ent in ents.items():
        ok, _ = wes.entity_claim_identifier_literals(ent, {"10001", "01001"})
        if ok:
            matched = True
            break
    assert matched, "expected FIPS overlap for Kent County, DE among top search hits"

"""DEPRECATED orchestrator shim — Wikidata jurisdiction enrichment.

The full WDQS/SPARQL + Wikibase enrichment monolith that used to live here has
been DECOMPOSED and moved to archive/datasources/wikidata/load_jurisdictions_wikidata.py:

  * FETCH (live WDQS/SPARQL GET + wbgetentities GET, JSON cache) ->
        packages/ingestion/src/ingestion/wikidata/download.py
        (core_lib.http.BaseAsyncClient subclass; run `python -m ingestion.wikidata.download`).
  * SEED  (copy census bronze_jurisdictions_* into the *_wikidata base rows) ->
        dbt staging models stg_wikidata__jurisdiction_{counties,municipalities,school_districts}.
  * APPLY (UPDATE *_wikidata SET ... from cached enrichment, keyed on geoid) ->
        dbt staging stg_wikidata__enrichment + intermediate
        int_wikidata__jurisdictions_enriched (the UPDATE-on-geoid becomes a JOIN).

Do NOT run this module's old CLI — the happy path is FETCH (downloader) +
`dbt build`. This shim exists ONLY so the irreducible-scraper utilities that
still live in this directory keep importing the shared helpers:

  * hydrate_municipality_websites_from_wikidata.py / hydrate_county_websites_from_wikidata.py
    — live wbgetentities hydration of rows that have a QID but a NULL website
      (resume/checkpoint driven). These are SCRAPERS, not transformations.
  * discover_municipality_website_gaps.py — Postgres coverage/gap discovery.
  * geography_qid_cache.py / parquet_qid_lookup.py — literal->QID resolution
    (fuzzy / identifier matching) used to warm the geography cache.

FLAGGED as not-translatable-to-dbt (left as scraper/utility, by design):
  * fuzzy name matching + wbsearchentities entity-search county/municipality
    recovery (_county_resolve_via_entity_search),
  * checkpoint/resume (CheckpointManager),
  * county-gap discovery against Postgres (fetch_usps_county_wikidata_gaps),
  * the bespoke WDQS rolling-budget / cooldown / UA-rotation client.

These re-exports come from the archived module so the live scrapers above
continue to work unchanged.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path

# Import the archived monolith by file path (it is no longer importable via the
# scrapers.wikidata package, having moved under archive/).
# Walk up from this file to the repo root (the ancestor that contains
# archive/datasources/wikidata/) so the lookup survives the move of this shim
# from scripts/datasources/ into packages/scrapers/.
_REL = _Path("archive") / "datasources" / "wikidata" / "load_jurisdictions_wikidata.py"
_ARCHIVED = next(
    (anc / _REL for anc in _Path(__file__).resolve().parents if (anc / _REL).is_file()),
    _Path(__file__).resolve().parents[5] / _REL,  # fallback: packages/scrapers/src/scrapers/wikidata -> repo root
)

if not _ARCHIVED.is_file():
    raise ImportError(
        "Archived Wikidata loader not found at "
        f"{_ARCHIVED}. The enrichment happy path is now FETCH "
        "(python -m ingestion.wikidata.download) + dbt build "
        "(stg_wikidata__* / int_wikidata__jurisdictions_enriched)."
    )

_spec = _ilu.spec_from_file_location(
    "archive.datasources.wikidata.load_jurisdictions_wikidata", _ARCHIVED
)
_mod = _ilu.module_from_spec(_spec)
_sys.modules.setdefault(_spec.name, _mod)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

# Re-export the irreducible-scraper helpers the remaining utilities import.
DATABASE_URL = _mod.DATABASE_URL
PRIORITY_STATES = _mod.PRIORITY_STATES
STATE_MAP = _mod.STATE_MAP
CheckpointManager = _mod.CheckpointManager
JurisdictionsWikiDataLoader = _mod.JurisdictionsWikiDataLoader
fetch_usps_county_wikidata_gaps = _mod.fetch_usps_county_wikidata_gaps
_apply_wikidata_happy_path_env_defaults = _mod._apply_wikidata_happy_path_env_defaults
_wikidata_fips_gnis_parquet_path = _mod._wikidata_fips_gnis_parquet_path
_county_fips_literal_alternatives = _mod._county_fips_literal_alternatives
_municipality_wd_literal_sets = _mod._municipality_wd_literal_sets
_school_id_literal_alternatives = _mod._school_id_literal_alternatives
_batched_sorted_literals = _mod._batched_sorted_literals

__all__ = [
    "DATABASE_URL",
    "PRIORITY_STATES",
    "STATE_MAP",
    "CheckpointManager",
    "JurisdictionsWikiDataLoader",
    "fetch_usps_county_wikidata_gaps",
    "_apply_wikidata_happy_path_env_defaults",
    "_wikidata_fips_gnis_parquet_path",
    "_county_fips_literal_alternatives",
    "_municipality_wd_literal_sets",
    "_school_id_literal_alternatives",
    "_batched_sorted_literals",
]

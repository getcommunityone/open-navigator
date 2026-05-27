"""Wikidata jurisdiction enrichment FETCH layer.

The legacy monolith scripts/datasources/wikidata/load_jurisdictions_wikidata.py
was an enrichment job: it ran live WDQS/SPARQL + Wikibase ``wbgetentities``
queries and UPDATE-ed pre-seeded ``bronze.bronze_jurisdictions_*_wikidata``
tables (keyed on geoid).

That monolith has been decomposed into three layers:

  1. FETCH  — ``ingestion.wikidata.download`` (this package): a BaseAsyncClient
     subclass that runs the SPARQL/entity HTTP GETs and writes the enrichment
     results to ``data/cache/wikidata/`` as JSON, with cache-freshness reuse
     (same shape as ingestion.gsa.download).
  2. SEED + APPLY (DERIVE) — dbt models:
       * staging  ``stg_wikidata__jurisdiction_<type>`` seed the *_wikidata base
         rows from the census ``source('bronze', 'bronze_jurisdictions_*')``.
       * staging  ``stg_wikidata__enrichment`` reads the cached enrichment JSON
         (declared as a bronze source) produced by this FETCH layer.
       * intermediate ``int_wikidata__jurisdictions_enriched`` LEFT JOINs the
         seed to the enrichment on geoid (the UPDATE-on-geoid becomes a JOIN).
  3. Irreducible scraping / resume / fuzzy-match utilities stay in
     ``scripts/datasources/wikidata/`` (see that dir's README).
"""

from .download import (
    WikidataClient,
    download_state_enrichment,
    main,
)

__all__ = [
    "WikidataClient",
    "download_state_enrichment",
    "main",
]

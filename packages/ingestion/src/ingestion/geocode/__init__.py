"""Free, idempotent geocoding backfill for civic places.

Fills ``bronze.place_geocode_cache`` (an additive cache, never mutating
``public.event_place``) from two FREE, key-less geocoders:

* :mod:`ingestion.geocode.census_batch` — US Census Bureau batch geocoder for
  ``place_type='street_address'`` rows (up to 10k addresses per HTTP POST).
* OpenStreetMap Nominatim (reused from ``llm.gemini.enrich_analysis_places``)
  for every other place type, at the OSM-mandated 1 req/s.

A separate dbt model LEFT JOINs this cache into ``event_place``; this package
only produces and populates the cache table.
"""

from .census_batch import CensusBatchGeocoder, CensusGeocodeResult, parse_census_csv

__all__ = [
    "CensusBatchGeocoder",
    "CensusGeocodeResult",
    "parse_census_csv",
]

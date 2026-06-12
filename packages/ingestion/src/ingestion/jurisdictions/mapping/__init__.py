"""Jurisdiction mapping-quality analysis.

Modules:
- ``queries`` — shared SQL fragments + WHERE-clause builders (psycopg2 / asyncpg)
  for unmapped / missing-YouTube drill-downs.
- ``state_acs_quality`` — state-level ACS (population / income) tiers merged with
  per-state portal mapping rollups.
- ``state_youtube_category_rollup`` — per-state YouTube channel mapping by policy
  category for the dashboard export.
- ``youtube_channel_diagnostics`` — live YouTube channel + bronze video diagnostics
  SQL and gap-reason helpers used by the API drill-down routes.
- ``export_quality_json`` — CLI that writes the dashboard
  ``jurisdiction_mapping_quality.json`` (run: ``python -m
  ingestion.jurisdictions.mapping.export_quality_json``).
"""

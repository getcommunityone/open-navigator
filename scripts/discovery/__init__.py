"""
Jurisdiction Discovery Module

Identifies and tracks local government jurisdictions across the United States
for oral health policy monitoring.

Data Sources:
- Census Bureau Government Integrated Directory (GID)
- CISA .gov Domain Master List (cisagov/dotgov-data)
- NCES Common Core of Data (school districts)

Postgres path (recommended): ``python -m scripts.discovery.jurisdiction_discovery_pipeline``
writes to ``bronze.bronze_jurisdictions_*_scraped`` (see migration 009).
"""

"""Shared SQL for canonical URLs from ``intermediate.int_jurisdiction_websites``."""

from __future__ import annotations

INT_JURISDICTION_WEBSITES_TABLE = "intermediate.int_jurisdiction_websites"

# Same priority as scripts.discovery.jurisdiction_discovery_pipeline
WEBSITE_SOURCE_PRIORITY_ORDER_SQL = (
    "CASE WHEN jurisdiction_id LIKE 'county_%%' THEN "
    "CASE website_source WHEN 'override' THEN 0 WHEN 'naco' THEN 1 WHEN 'gsa' THEN 2 WHEN 'league' THEN 3 "
    "WHEN 'uscm' THEN 4 WHEN 'nces_directory' THEN 5 ELSE 6 END ELSE "
    "CASE website_source WHEN 'override' THEN 0 WHEN 'gsa' THEN 1 WHEN 'league' THEN 2 WHEN 'uscm' THEN 3 "
    "WHEN 'nces_directory' THEN 4 WHEN 'naco' THEN 5 ELSE 6 END END"
)

BRONZE_ACCESSIBILITY_TABLE = "bronze.bronze_jurisdiction_website_accessibility"

BRONZE_LIGHTHOUSE_TABLE = "bronze.bronze_jurisdiction_website_lighthouse"

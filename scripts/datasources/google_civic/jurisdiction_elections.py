"""
Deprecated: election ingest for ``scrape_priority_states`` now uses website HTML crawl.

See ``scripts.datasources.jurisdiction_pilot.website_elections``.
"""

from scripts.datasources.jurisdiction_pilot.website_elections import (  # noqa: F401
    JurisdictionElectionResult,
    ingest_jurisdiction_elections_from_website,
)

__all__ = [
    "JurisdictionElectionResult",
    "ingest_jurisdiction_elections_from_website",
]

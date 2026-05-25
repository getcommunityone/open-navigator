"""Built-in seeds resolve by GEOID across legacy and canonical jurisdiction_id keys."""

from scripts.discovery.jurisdiction_meeting_seed_urls import (
    _BUILTIN,
    merged_meeting_seed_urls,
)
from scripts.jurisdictions.jurisdiction_id import builtin_seed_urls_for_jurisdiction


def test_ben_hill_meeting_seed_legacy_and_canonical_ids():
    url = "https://www.benhillcounty-ga.gov/county-commissioner-meetings/"
    assert url in builtin_seed_urls_for_jurisdiction("county_13017", _BUILTIN)
    assert url in builtin_seed_urls_for_jurisdiction("ben_hill_13017", _BUILTIN)
    assert merged_meeting_seed_urls("ben_hill_13017", None) == [url]
    assert merged_meeting_seed_urls("county_13017", None) == [url]

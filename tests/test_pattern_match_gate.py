"""pattern_match acceptance and primary-selection guards."""

from scrapers.youtube.pattern_match_gate import (
    passes_pattern_match_gate,
    references_state,
)
from scripts.discovery.youtube_primary_channel import pick_primary_youtube_channel


def test_references_state_usps_and_name():
    assert references_state("Calhoun County, Texas government meetings", "TX")
    assert references_state("broadcasting public meetings in Alabama", "AL")
    assert not references_state("Calhoun County government meetings", "TX")


def test_pattern_match_calhoun_county_generic_handle_rejected():
    assert not passes_pattern_match_gate(
        channel_title="Calhoun County",
        channel_description="Share your videos with friends.",
        jurisdiction_name="Calhoun County",
        jurisdiction_state_code="TX",
        jurisdiction_homepage="https://www.co.calhoun.tx.us/",
        external_links=[],
        backlinks_to_jurisdiction=False,
    )


def test_pattern_match_accepted_with_backlink_state_meeting():
    assert passes_pattern_match_gate(
        channel_title="Calhoun County, Texas",
        channel_description=(
            "Official channel for Calhoun County, Texas commission meetings. "
            "Visit https://www.co.calhoun.tx.us/"
        ),
        jurisdiction_name="Calhoun County",
        jurisdiction_state_code="TX",
        jurisdiction_homepage="https://www.co.calhoun.tx.us/",
        external_links=["https://www.co.calhoun.tx.us/"],
        backlinks_to_jurisdiction=True,
    )


def test_pick_primary_skips_weak_pattern_match():
    url, method, conf = pick_primary_youtube_channel(
        [
            {
                "channel_url": "https://www.youtube.com/@CalhounCounty",
                "discovery_method": "pattern_match",
                "official_meeting_confidence": 0.2,
                "back_links_to_jurisdiction_website": False,
            },
            {
                "channel_url": "https://www.youtube.com/channel/UCgood",
                "discovery_method": "website_scrape",
                "official_meeting_confidence": 0.8,
                "back_links_to_jurisdiction_website": True,
            },
        ]
    )
    assert url == "https://www.youtube.com/channel/UCgood"
    assert method == "website_scrape"
    assert conf == 0.8

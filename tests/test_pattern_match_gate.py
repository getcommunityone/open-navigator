"""pattern_match acceptance and primary-selection guards."""

from scrapers.youtube.pattern_match_gate import (
    passes_pattern_match_gate,
    references_state,
)
from scrapers.discovery.youtube_primary_channel import pick_primary_youtube_channel


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


"""Case 8 -- Extended offline tests for scrapers.youtube.pattern_match_gate.

Supplements the three smoke tests already in tests/test_pattern_match_gate.py
with comprehensive coverage of every sub-gate, edge-cases, and adversarial inputs.
No network is touched; all logic is pure-Python.
"""

import pytest

from scrapers.youtube.pattern_match_gate import (
    has_meeting_signal,
    is_pattern_match_discovery,
    jurisdiction_name_plausible,
    passes_pattern_match_gate,
    references_state,
)


# ---------------------------------------------------------------------------
# references_state
# ---------------------------------------------------------------------------


class TestReferencesState:
    """The state-reference check against USPS code + full state name."""

    def test_usps_code_with_comma(self) -> None:
        assert references_state("Calhoun County, TX government meetings", "TX")

    def test_usps_code_standalone_word(self) -> None:
        assert references_state("public meetings in AL 2026", "AL")

    def test_full_state_name(self) -> None:
        assert references_state("broadcasting public meetings in Alabama", "AL")

    def test_no_state_reference(self) -> None:
        assert not references_state("Calhoun County government meetings", "TX")

    def test_wrong_state_not_matched(self) -> None:
        # Georgia county channel should not claim Texas
        assert not references_state("Calhoun County Georgia council", "TX")

    def test_empty_text_returns_false(self) -> None:
        assert not references_state("", "TX")

    def test_empty_state_code_returns_false(self) -> None:
        assert not references_state("Calhoun County, TX", "")

    def test_invalid_state_code_length(self) -> None:
        # Only two-char USPS codes are valid
        assert not references_state("Calhoun County, TEX", "TEX")

    def test_parenthesised_usps_code(self) -> None:
        assert references_state("Calhoun County (TX) official channel", "TX")


# ---------------------------------------------------------------------------
# has_meeting_signal
# ---------------------------------------------------------------------------


class TestHasMeetingSignal:
    """Government / meeting wording must appear in the combined title+desc blob."""

    def test_meeting_keyword_in_description(self) -> None:
        assert has_meeting_signal(
            "Calhoun County",
            "Official recordings of city council meetings.",
        )

    def test_gov_keyword_in_title(self) -> None:
        assert has_meeting_signal("Calhoun County Government", "")

    def test_junk_title_clears_title_contribution(self) -> None:
        # If title is a known junk word, it contributes nothing; the signal
        # must come from the description alone.
        assert has_meeting_signal(
            "Home",  # junk tab title from About-page scrape
            "Live broadcasts of every county commission meeting.",
        )

    def test_junk_title_no_description_is_false(self) -> None:
        assert not has_meeting_signal("videos", "")

    def test_no_signal_at_all(self) -> None:
        assert not has_meeting_signal(
            "Calhoun County",
            "Share your videos with friends, family, and the world.",
        )

    def test_empty_inputs_is_false(self) -> None:
        assert not has_meeting_signal("", "")


# ---------------------------------------------------------------------------
# jurisdiction_name_plausible
# ---------------------------------------------------------------------------


class TestJurisdictionNamePlausible:
    """At least one non-generic token from the jurisdiction name must appear."""

    def test_name_token_in_title(self) -> None:
        assert jurisdiction_name_plausible(
            "Calhoun County TX",
            "",
            "Calhoun County",
        )

    def test_name_token_in_description(self) -> None:
        assert jurisdiction_name_plausible(
            "Government Channel",
            "Official video feed for Calhoun County commission meetings.",
            "Calhoun County",
        )

    def test_no_name_token_anywhere(self) -> None:
        assert not jurisdiction_name_plausible(
            "County Council Videos",
            "Meetings from the local county.",
            "Calhoun County",  # "calhoun" missing in both fields
        )

    def test_no_meaningful_tokens_always_plausible(self) -> None:
        # If _jurisdiction_name_tokens returns empty (all stop words), True.
        assert jurisdiction_name_plausible("anything", "anything", "City")

    def test_junk_title_matched_against_description(self) -> None:
        assert jurisdiction_name_plausible(
            "About",  # junk tab -- cleared from blob
            "Calhoun County government channel",
            "Calhoun County",
        )


# ---------------------------------------------------------------------------
# passes_pattern_match_gate -- integration of all three sub-gates
# ---------------------------------------------------------------------------


class TestPassesPatternMatchGate:
    """Full gate: backlink AND state-reference AND meeting-signal AND name-plausible."""

    _HOMEPAGE = "https://www.co.calhoun.tx.us/"

    def _gate(self, **overrides) -> bool:
        defaults: dict = {
            "channel_title": "Calhoun County, Texas",
            "channel_description": (
                "Official recordings of Calhoun County, Texas commission meetings. "
                "Visit https://www.co.calhoun.tx.us/"
            ),
            "jurisdiction_name": "Calhoun County",
            "jurisdiction_state_code": "TX",
            "jurisdiction_homepage": self._HOMEPAGE,
            "external_links": [self._HOMEPAGE],
            "backlinks_to_jurisdiction": True,
        }
        defaults.update(overrides)
        return passes_pattern_match_gate(**defaults)

    def test_fully_qualifying_channel_passes(self) -> None:
        assert self._gate()

    def test_missing_homepage_always_fails(self) -> None:
        # No homepage = can't verify backlink; gate must reject immediately.
        assert not self._gate(jurisdiction_homepage="")

    def test_no_backlink_fails(self) -> None:
        assert not self._gate(backlinks_to_jurisdiction=False)

    def test_wrong_state_fails(self) -> None:
        # Channel mentions only Georgia (no TX code, no 'texas' in text).
        # Use a Georgia homepage so the homepage URL doesn't inject 'tx' into
        # the text used by references_state.
        assert not passes_pattern_match_gate(
            channel_title="Calhoun County, Georgia",
            channel_description="Commission meetings for Calhoun County, Georgia government.",
            jurisdiction_name="Calhoun County",
            jurisdiction_state_code="TX",
            jurisdiction_homepage="https://www.co.calhoun.ga.us/",
            external_links=["https://www.co.calhoun.ga.us/"],
            backlinks_to_jurisdiction=True,
        )

    def test_no_meeting_signal_fails(self) -> None:
        # Neither title nor description contains any meeting/government keyword.
        assert not self._gate(
            channel_title="Calhoun County, TX",
            channel_description=(
                "Calhoun County Texas photos and events calendar. "
                "https://www.co.calhoun.tx.us/"
            ),
        )

    def test_name_not_plausible_fails(self) -> None:
        # _jurisdiction_name_tokens('Zavala County') -> ['zavala'].
        # 'zavala' must not appear in the channel title, description, or the
        # homepage URL; the gate must therefore reject on name_plausible.
        assert not passes_pattern_match_gate(
            channel_title="Matagorda County, Texas government meetings",
            channel_description=(
                "Commission meetings for Matagorda County Texas government. "
                "https://www.co.matagorda.tx.us/"
            ),
            jurisdiction_name="Zavala County",
            jurisdiction_state_code="TX",
            jurisdiction_homepage="https://www.co.zavala.tx.us/",
            external_links=["https://www.co.matagorda.tx.us/"],
            backlinks_to_jurisdiction=True,
        )

    def test_backlinks_computed_from_external_links(self) -> None:
        """When backlinks_to_jurisdiction is None, the gate must compute it from
        external_links and description_text via back_links_to."""
        result = passes_pattern_match_gate(
            channel_title="Calhoun County, Texas",
            channel_description=(
                "Calhoun County Texas commission meetings. "
                "https://www.co.calhoun.tx.us/"
            ),
            jurisdiction_name="Calhoun County",
            jurisdiction_state_code="TX",
            jurisdiction_homepage=self._HOMEPAGE,
            external_links=[self._HOMEPAGE],
            backlinks_to_jurisdiction=None,  # force computation
        )
        assert result

    def test_backlinks_computed_no_links_fails(self) -> None:
        result = passes_pattern_match_gate(
            channel_title="Calhoun County, Texas",
            channel_description="Calhoun County Texas commission meetings.",
            jurisdiction_name="Calhoun County",
            jurisdiction_state_code="TX",
            jurisdiction_homepage=self._HOMEPAGE,
            external_links=[],  # no links in About
            backlinks_to_jurisdiction=None,
        )
        assert not result


# ---------------------------------------------------------------------------
# is_pattern_match_discovery
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "channel, expected",
    [
        ({"discovery_method": "pattern_match"}, True),
        ({"discovery_method": "pattern_match_handle"}, True),
        ({"youtube_channel_selection_method": "pattern_match"}, True),
        ({"discovery_method": "website_scrape"}, False),
        ({"discovery_method": None}, False),
        ({}, False),
    ],
)
def test_is_pattern_match_discovery(
    channel: dict, expected: bool
) -> None:
    assert is_pattern_match_discovery(channel) is expected

"""Unit tests for the bronze_event_youtube jurisdiction-tag repair (pure logic).

Covers the three decision points that keep the cleanup conservative and
collision-safe, none of which touch the database:

  * PART A civic detection — strict governance vocabulary (a real council title
    is civic; a celebrity-radio headline that merely says "fire"/"mayor" is not),
    plus the bare-date and channel-profile guards.
  * Title → place parsing — pulls a municipality out of a meeting title in both
    the "<Place> City Council" and "City of <Place>" shapes.
  * The state-collision guard — a state name the place regex greedily swallowed
    ("Omaha Nebraska") is split back off so it cannot mis-resolve to "Nebraska
    City", and a title-local state is recovered as a corroborant.
"""
from __future__ import annotations

from scrapers.youtube.clean_jurisdiction_tags import (
    ChannelProfile,
    _split_trailing_state,
    is_bare_date_title,
    is_civic_title,
    parse_title_place,
)


# --- PART A: civic-keyword detection --------------------------------------


def test_civic_title_accepts_governance_phrases():
    assert is_civic_title("Cookeville City Council Meeting May 01, 2014")
    assert is_civic_title("Pulaski County Fiscal Court Meeting 11-13-18")
    assert is_civic_title("Planning Commission Work Session")
    assert is_civic_title("City of Glendale - Redevelopment Agency")


def test_civic_title_rejects_entertainment_headlines():
    # Loose single words ("fire", "mayor", "water") must NOT count as civic.
    assert not is_civic_title(
        "Florida Man Sets Ex-GF's Apartment On Fire After Threatening Her"
    )
    assert not is_civic_title(
        "Mayor Ras Baraka Talks Effects From Trump Administration, ICE"
    )
    assert not is_civic_title("Samsung s23 ultra camera water resistant ip68")
    assert not is_civic_title("Kevin Hart Squashes Beef With Katt Williams")


def test_bare_date_title():
    assert is_bare_date_title("January 1, 2023")
    assert is_bare_date_title("11-13-18")
    assert is_bare_date_title("2023.05.01")
    assert not is_bare_date_title("Cookeville City Council Meeting")
    assert not is_bare_date_title("")


def test_channel_profile_non_civic_rule():
    # Pure junk: no civic keyword, no official type, not all dates → clear it.
    junk = ChannelProfile("c1", 99, any_civic=False, all_dates=False,
                          has_official_type=False)
    assert junk.is_non_civic
    # Any civic title anywhere protects the channel.
    civic = ChannelProfile("c2", 50, any_civic=True, all_dates=False,
                           has_official_type=False)
    assert not civic.is_non_civic
    # An authoritative channel_type protects a department whose titles are all
    # incident reports (e.g. Mesa Fire & Medical).
    official = ChannelProfile("c3", 95, any_civic=False, all_dates=False,
                              has_official_type=True)
    assert not official.is_non_civic
    # All-bare-date channels are protected (possible untitled meeting uploads).
    dated = ChannelProfile("c4", 13, any_civic=False, all_dates=True,
                           has_official_type=False)
    assert not dated.is_non_civic


# --- PART B: title parsing -------------------------------------------------


def test_parse_title_place_prefix_shape():
    assert parse_title_place("Cookeville City Council Meeting May 01, 2014") == (
        "Cookeville",
        None,
    )
    assert parse_title_place("2011-11-01 - Glendale City Council Meeting") == (
        "Glendale",
        None,
    )
    assert parse_title_place("21 09 09 Webster Village Board Meeting") == (
        "Webster",
        None,
    )


def test_parse_title_place_of_shape():
    assert parse_title_place("City of Mexico, MO")[0] == "Mexico"
    assert parse_title_place("City of Blue Springs-City Council Meeting")[0] == (
        "Blue Springs-City"
    )


def test_parse_title_place_none_when_no_place():
    assert parse_title_place("City Council 8-6-2018") == (None, None)
    assert parse_title_place("Salem Budget Committee") == (None, None)
    assert parse_title_place("") == (None, None)


# --- PART B: state-collision guard ----------------------------------------


def test_split_trailing_state_strips_state_name():
    # The bug this guards: "Omaha Nebraska" once resolved to "Nebraska City".
    assert _split_trailing_state("Omaha Nebraska") == ("Omaha", "NE")
    assert _split_trailing_state("Charleston West Virginia") == (
        "Charleston",
        "WV",
    )
    assert _split_trailing_state("Springfield IL") == ("Springfield", "IL")


def test_split_trailing_state_leaves_plain_names():
    assert _split_trailing_state("Springfield") == ("Springfield", None)
    assert _split_trailing_state("Grand Rapids") == ("Grand Rapids", None)


def test_parse_title_place_recovers_title_state():
    assert parse_title_place("Omaha Nebraska City Council meeting July 1") == (
        "Omaha",
        "NE",
    )

"""Tests for state YouTube category classifier."""

from scripts.discovery.state_youtube_category_classifier import (
    pick_best_channel_for_category,
    score_channel_for_category,
)


def test_public_health_department_scores() -> None:
    sc = score_channel_for_category(
        title="Alabama Department of Public Health",
        description="Official channel for ADPH",
        channel_type="state",
        state_name="Alabama",
        state_code="AL",
        category="public_health",
    )
    assert sc >= 0.45


def test_county_meeting_excluded_from_public_health() -> None:
    sc = score_channel_for_category(
        title="Jefferson County Commission Meetings",
        description="Public meetings streamed here",
        channel_type="county",
        state_name="Alabama",
        state_code="AL",
        category="public_health",
    )
    assert sc == 0.0


def test_overall_state_channel_scores() -> None:
    sc = score_channel_for_category(
        title="State of Georgia",
        description="Official Georgia government channel",
        channel_type="state",
        state_name="Georgia",
        state_code="GA",
        category="overall",
    )
    assert sc >= 0.45


def test_pick_best_channel_prefers_higher_score() -> None:
    channels = [
        {
            "channel_title": "Alabama DOT",
            "channel_description": "Department of Transportation",
            "channel_type": "state",
            "youtube_channel_url": "https://www.youtube.com/@ALDOT",
            "channel_id": "abc",
        },
        {
            "channel_title": "Random Alabama Videos",
            "channel_description": "Travel vlog",
            "channel_type": "unknown",
            "youtube_channel_url": "https://www.youtube.com/@travel",
            "channel_id": "def",
        },
    ]
    pick = pick_best_channel_for_category(
        channels,
        state_name="Alabama",
        state_code="AL",
        category="transportation",
    )
    assert pick is not None
    assert pick["channel_id"] == "abc"

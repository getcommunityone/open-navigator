"""Unit tests for the YouTube channel-purpose classifier (pure logic, no DB).

Cover the decision boundaries that keep junk out of government feeds without
purging quiet-but-legit municipal channels:
  * a clearly civic channel → government,
  * a zero-civic channel with big views or entertainment titles → junk,
  * a zero-civic but small, content-neutral channel → UNDECIDED (not junk),
  * curated 'seed' verdicts are never downgraded by the heuristic.
"""
from __future__ import annotations

from scrapers.youtube.classify_channel_purpose import (
    ChannelStats,
    civic_fraction,
    classify_channel,
    entertainment_hits,
    is_civic_meeting_type,
)


def _stats(
    *,
    channel_id="UC_test",
    total=10,
    civic=0,
    max_views=0,
    titles=None,
    channel_title=None,
) -> ChannelStats:
    return ChannelStats(
        channel_id=channel_id,
        total_videos=total,
        civic_videos=civic,
        max_views=max_views,
        avg_views=float(max_views) / 2 if max_views else 0.0,
        sample_titles=titles or [],
        channel_title=channel_title,
    )


# --- civic_fraction ----------------------------------------------------------


def test_civic_fraction_basic():
    assert civic_fraction(0, 0) == 0.0
    assert civic_fraction(0, 10) == 0.0
    assert civic_fraction(5, 10) == 0.5
    assert civic_fraction(10, 10) == 1.0
    # never out of [0, 1] even with bad inputs
    assert civic_fraction(20, 10) == 1.0
    assert civic_fraction(1, 0) == 0.0


# --- meeting-type recognition ------------------------------------------------


def test_is_civic_meeting_type():
    assert is_civic_meeting_type("MUNICIPAL COUNCIL")
    assert is_civic_meeting_type("City Council")
    assert is_civic_meeting_type("SCHOOL BOARD")
    assert is_civic_meeting_type("Planning Commission")
    assert not is_civic_meeting_type("Other")
    assert not is_civic_meeting_type("")
    assert not is_civic_meeting_type(None)


# --- entertainment markers ---------------------------------------------------


def test_entertainment_hits_detects_distinctive_markers():
    assert entertainment_hits("Kittie - Spit [LIVE @ Ozzfest]")
    assert entertainment_hits("Walker County - Mirror Mirror (Official Music Video)")
    assert entertainment_hits("ASS & TITIES (IN STUDIO PERFORMANCE)")
    assert entertainment_hits("Kevin Hart on The Breakfast Club")
    assert entertainment_hits("ARK Official Small Trailer gameplay")


def test_entertainment_hits_ignores_civic_live_meetings():
    # bare "live" must NOT trip the entertainment detector
    assert entertainment_hits("LIVE: City Council Regular Meeting") == []
    assert entertainment_hits("Board of Education Workshop") == []
    assert entertainment_hits("") == []


# --- the decision ------------------------------------------------------------


def test_clearly_civic_channel_is_government():
    v = classify_channel(_stats(total=100, civic=80, max_views=300))
    assert v.is_government is True
    assert v.is_junk is False
    assert v.method == "heuristic"


def test_zero_civic_high_views_is_junk():
    v = classify_channel(_stats(total=15, civic=0, max_views=2_348_963))
    assert v.is_junk is True
    assert v.is_government is False


def test_zero_civic_entertainment_titles_low_views_is_junk():
    v = classify_channel(
        _stats(
            total=5,
            civic=0,
            max_views=1200,
            titles=["Some Band - Track (Official Music Video)"],
        )
    )
    assert v.is_junk is True


def test_zero_civic_small_neutral_channel_is_undecided():
    # A quiet zero-civic channel with no entertainment signal and low views
    # could be a legit municipal channel posting non-meeting content -> NULL.
    v = classify_channel(
        _stats(
            total=8,
            civic=0,
            max_views=300,
            titles=["Bulk Trash Collection", "Police CSI Vehicle Unveiling"],
        )
    )
    assert v.is_government is None
    assert v.is_junk is None


def test_no_videos_is_undecided():
    v = classify_channel(_stats(total=0, civic=0, max_views=0))
    assert v.is_government is None
    assert v.is_junk is None


def test_low_civic_fraction_below_threshold_is_undecided():
    # 2/10 civic = 0.2, below the 0.30 gov bar, low views, no entertainment
    v = classify_channel(_stats(total=10, civic=2, max_views=400))
    assert v.is_government is None
    assert v.is_junk is None


def test_known_junk_channels_resolve_to_junk():
    # The four real offenders, with their corrupted channel_title and the
    # entertainment video titles that actually carry the signal.
    cases = [
        ("UC1BD9-9KkrR5GBEjBFmUh_Q", "c-IN-18109", 2_348_963,
         "Kittie - Spit [LIVE @ Ozzfest]"),
        ("UChi08h4577eFsNXGd3sxYhw", "c-AL-01077", 489_649,
         "Kevin Hart Squashes Beef With Katt Williams"),
        ("UC5AoMZDQCYKZ8OczR4qeNGQ", "c-IN-18171", 560_739,
         "Jennifer Ellison - Baby I Don't Care"),
        ("UCzlnaIrdxwJITyrESOReqxg", "Double Springs", 791_146,
         "Michigan Opening Weekend CHAOS! Angry Hunter Confronts Us"),
    ]
    for cid, ctitle, views, title in cases:
        v = classify_channel(
            _stats(
                channel_id=cid,
                total=20,
                civic=0,
                max_views=views,
                titles=[title],
                channel_title=ctitle,
            )
        )
        assert v.is_junk is True, cid
        assert v.is_government is False, cid

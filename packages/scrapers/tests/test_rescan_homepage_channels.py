"""scrapers.youtube.rescan_homepage_channels: merging found links and choosing the primary."""

from __future__ import annotations

from scrapers.youtube import rescan_homepage_channels as r

NOW = "2026-11-16T00:00:00+00:00"


def test_merge_adds_new_links_and_relabels_known_ones():
    payload = {
        "youtube_channels": [
            {
                "channel_url": "https://www.youtube.com/@ElkinsCityHall",
                "discovery_method": "pattern_match",
                "confidence": 0.7,
            }
        ],
        "social_media": {"youtube": [], "vimeo": []},
        "other": 1,
    }
    out, added = r.merge_channels(
        payload,
        [
            "https://www.youtube.com/@elkinscityhall/",
            "https://www.youtube.com/channel/UC-j6MHOHpxlWYpNPTEt15-Q",
        ],
        now=NOW,
    )
    assert added == 1
    assert out["other"] == 1
    known, new = out["youtube_channels"]
    assert known["discovery_method"] == "website_scrape" and known["confidence"] == 0.9
    assert (
        new["channel_id"] == "UC-j6MHOHpxlWYpNPTEt15-Q" and new["discovered_at"] == NOW
    )
    assert len(out["social_media"]["youtube"]) == 2
    assert out["social_media"]["vimeo"] == []
    # The input is not mutated.
    assert payload["youtube_channels"][0]["discovery_method"] == "pattern_match"


def test_merge_with_nothing_found_keeps_payload():
    out, added = r.merge_channels(None, [], now=NOW)
    assert (
        added == 0
        and out["youtube_channels"] == []
        and out["social_media"]["youtube"] == []
    )


def test_primary_replaces_only_guesses_or_blanks():
    found = ["https://www.youtube.com/@real"]
    assert r.choose_primary(None, None, found) == found[0]
    assert (
        r.choose_primary("https://www.youtube.com/@guess", "pattern_match", found)
        == found[0]
    )
    assert (
        r.choose_primary("https://www.youtube.com/@api", "youtube_api", found) is None
    )
    assert (
        r.choose_primary("https://www.youtube.com/@guess", "pattern_match", []) is None
    )


def test_channel_id_only_from_channel_urls():
    assert r._channel_id("https://www.youtube.com/channel/UCabc/videos") == "UCabc"
    assert r._channel_id("https://www.youtube.com/@handle") is None


def test_select_sql():
    sql, params = r.select_sql(["al"], include_rescanned=False)
    assert (
        params == [["AL"]] and "homepage_rescan_at" in sql and sql.endswith("LIMIT %s")
    )
    sql, params = r.select_sql([], include_rescanned=True)
    assert params == [] and "homepage_rescan_at" not in sql

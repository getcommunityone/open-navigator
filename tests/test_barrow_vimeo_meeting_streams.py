"""Barrow County GA — CivicPlus Vimeo board meeting video hub."""

from scripts.discovery.jurisdiction_meeting_seed_urls import merged_meeting_seed_urls
from scripts.discovery.meetings_platform_heuristics import extract_other_video_stream_refs
from scripts.discovery.promote_bronze_meetings_to_c1_event import derive_date


BARROW_VIDEO_PAGE = "https://www.barrowga.org/390/Watch-a-Board-Meeting-Video"
BARROW_FIXTURE = """
<html><body>
<a href="https://vimeo.com/1154407944?fl=ip&amp;fe=ec">
  Barrow County Board of Commissioners Voting Session - January 13, 2026
</a>
</body></html>
"""


def test_barrow_meeting_seed_url():
    urls = merged_meeting_seed_urls("barrow_13013", None)
    assert BARROW_VIDEO_PAGE in urls


def test_vimeo_stream_refs_include_meeting_anchor_text():
    refs = extract_other_video_stream_refs(BARROW_FIXTURE, BARROW_VIDEO_PAGE)
    assert len(refs) == 1
    assert refs[0]["platform"] == "vimeo"
    assert "January 13, 2026" in refs[0]["anchor_text"]
    assert derive_date(refs[0]["anchor_text"]) == "2026-01-13"

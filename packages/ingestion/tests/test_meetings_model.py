"""CORE-3.1 (#242): one meeting model across platforms.

Agenda, recording and transcript resolve to the same shape whichever platform a council
broadcasts on, and an unsupported platform fails loudly instead of looking empty. The raw
records below are test fixtures shaped like each source (a LocalView row, a Legistar Web
API event); they never leave the tests.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from ingestion.meetings import (
    ArtifactKind,
    LegistarAdapter,
    Meeting,
    MeetingArtifact,
    UnsupportedPlatformError,
    YouTubeLocalViewAdapter,
    adapter_for,
    coverage_report,
    supported_platforms,
)

LOCALVIEW_ROW = {
    "vid_id": "abc123XYZ",
    "vid_title": "City Council Regular Meeting",
    "meeting_date": "2026-10-06",
    "place_name": "Springfield",
    "state_name": "Illinois",
    "place_govt": "City Council",
    "caption_text": "raw captions",
    "caption_text_clean": "Call to order. Roll call.",
}

LEGISTAR_EVENT = {
    "EventId": 4512,
    "EventBodyName": "City Council",
    "EventDate": "2026-10-06T00:00:00",
    "EventTime": "6:00 PM",
    "EventAgendaFile": "https://example.legistar.com/View.ashx?M=A&ID=4512",
    "EventMinutesFile": None,
    "EventVideoPath": "https://example.granicus.com/player/clip/99",
    "EventInSiteURL": "https://example.legistar.com/MeetingDetail.aspx?ID=4512",
}


def legistar() -> LegistarAdapter:
    return LegistarAdapter(jurisdiction_name="Springfield", state_code="IL", state="Illinois")


# -- the shape ------------------------------------------------------------------


def test_artifact_needs_a_url_or_text():
    with pytest.raises(ValueError):
        MeetingArtifact(kind=ArtifactKind.AGENDA, platform_code="legistar")


def test_meeting_key_is_stable_per_platform_and_id():
    a = Meeting(platform_code="youtube", platform_meeting_id="v1", jurisdiction_name="X")
    b = Meeting(platform_code="youtube", platform_meeting_id="v1", jurisdiction_name="Y")
    c = Meeting(platform_code="legistar", platform_meeting_id="v1", jurisdiction_name="X")
    assert a.meeting_key == b.meeting_key
    assert a.meeting_key != c.meeting_key
    assert len(a.meeting_key) == 16


def test_same_record_keys_for_every_platform():
    youtube = YouTubeLocalViewAdapter().normalize(LOCALVIEW_ROW).to_record()
    legistar_record = legistar().normalize(LEGISTAR_EVENT).to_record()
    assert list(youtube) == list(legistar_record)
    for key in ("agenda_url", "recording_url", "transcript_url", "minutes_url", "has_transcript_text"):
        assert key in youtube


# -- YouTube via LocalView ------------------------------------------------------


def test_localview_row_gives_recording_and_transcript():
    meeting = YouTubeLocalViewAdapter().normalize(LOCALVIEW_ROW)
    assert meeting.platform_code == "youtube"
    assert meeting.platform_meeting_id == "abc123XYZ"
    assert meeting.recording.url == "https://www.youtube.com/watch?v=abc123XYZ"
    assert meeting.transcript.text == "Call to order. Roll call."
    assert meeting.agenda is None  # LocalView carries no agenda: absent, never invented
    assert meeting.meeting_date == date(2026, 10, 6)
    assert (meeting.state_code, meeting.state) == ("IL", "Illinois")
    record = meeting.to_record()
    assert record["has_transcript_text"] is True
    assert record["agenda_url"] is None


def test_localview_missing_values_stay_missing():
    row = {**LOCALVIEW_ROW, "caption_text": math.nan, "caption_text_clean": math.nan,
           "vid_title": math.nan, "meeting_date": None, "state_name": "Atlantis"}
    meeting = YouTubeLocalViewAdapter().normalize(row)
    assert meeting.transcript is None
    assert meeting.title is None
    assert meeting.meeting_date is None
    assert meeting.state_code is None  # an unknown state is not guessed from its first letters


def test_localview_row_without_video_id_is_rejected():
    with pytest.raises(ValueError, match="vid_id"):
        YouTubeLocalViewAdapter().normalize({**LOCALVIEW_ROW, "vid_id": None})


# -- Legistar ---------------------------------------------------------------------


def test_legistar_event_gives_agenda_and_recording():
    meeting = legistar().normalize(LEGISTAR_EVENT)
    assert meeting.platform_code == "legistar"
    assert meeting.platform_meeting_id == "4512"
    assert meeting.agenda.url == LEGISTAR_EVENT["EventAgendaFile"]
    assert meeting.recording.url == LEGISTAR_EVENT["EventVideoPath"]
    assert meeting.minutes is None
    assert meeting.transcript is None
    assert meeting.body_name == "City Council"
    assert meeting.meeting_date == date(2026, 10, 6)
    assert meeting.source_url == LEGISTAR_EVENT["EventInSiteURL"]


def test_legistar_event_without_id_is_rejected():
    with pytest.raises(ValueError, match="EventId"):
        legistar().normalize({**LEGISTAR_EVENT, "EventId": None})


# -- loud failure -------------------------------------------------------------------


def test_supported_platforms_lists_the_adapters():
    assert {"youtube", "legistar"} <= set(supported_platforms())


def test_adapter_for_known_platform_ignores_case_and_spaces():
    assert adapter_for(" YouTube ", jurisdiction_name="Springfield") is YouTubeLocalViewAdapter


@pytest.mark.parametrize("platform", ["granicus", "", None])
def test_unsupported_platform_fails_loudly(platform):
    with pytest.raises(UnsupportedPlatformError) as err:
        adapter_for(platform, jurisdiction_name="Spokane")
    message = str(err.value)
    assert "Spokane" in message
    assert "youtube" in message  # names what is supported
    assert err.value.jurisdiction_name == "Spokane"


def test_coverage_report_counts_supported_and_lists_unsupported():
    report = coverage_report(
        [("Springfield", "youtube"), ("Shelbyville", "YouTube"), ("Spokane", "granicus"),
         ("Marshall", None), ("Capital City", "legistar")]
    )
    assert report.supported == {"youtube": 2, "legistar": 1}
    assert report.unsupported == {"granicus": ["Spokane"], "unknown": ["Marshall"]}
    assert report.unsupported_count == 2

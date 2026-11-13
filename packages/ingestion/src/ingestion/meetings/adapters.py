"""Reference meeting adapters (CORE-3.1, #242).

- ``youtube``: a LocalView row, which carries the YouTube recording and its captions.
- ``legistar``: a Legistar Web API event, which carries the agenda, minutes and video links.

Both return the same ``Meeting`` shape. Each sets only the artifacts its source really has.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ingestion.meetings.model import ArtifactKind, Meeting, MeetingArtifact, clean_value, parse_meeting_date
from ingestion.meetings.registry import MeetingAdapter, register_adapter

# Exact names only: an unlisted state gets no code rather than a guess from its first letters.
STATE_CODES: dict[str, str] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Puerto Rico": "PR", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


@register_adapter
class YouTubeLocalViewAdapter(MeetingAdapter):
    """A LocalView row: the meeting's YouTube recording, and its captions as the transcript."""

    platform_code = "youtube"

    def normalize(self, raw: Mapping[str, Any]) -> Meeting:
        video_id = clean_value(raw.get("vid_id"))
        if video_id is None:
            raise ValueError("LocalView row has no vid_id, so it can't identify a meeting.")
        video_id = str(video_id)
        recording_url = f"https://www.youtube.com/watch?v={video_id}"
        artifacts = [
            MeetingArtifact(ArtifactKind.RECORDING, self.platform_code, url=recording_url, label="YouTube video")
        ]
        captions = clean_value(raw.get("caption_text_clean")) or clean_value(raw.get("caption_text"))
        if captions is not None:
            artifacts.append(
                MeetingArtifact(ArtifactKind.TRANSCRIPT, self.platform_code, text=str(captions), label="YouTube captions")
            )
        state = clean_value(raw.get("state_name"))
        return Meeting(
            platform_code=self.platform_code,
            platform_meeting_id=video_id,
            jurisdiction_name=str(clean_value(raw.get("place_name")) or ""),
            title=clean_value(raw.get("vid_title")),
            meeting_date=parse_meeting_date(raw.get("meeting_date")),
            state_code=STATE_CODES.get(state) if state else None,
            state=state,
            body_name=clean_value(raw.get("place_govt")),
            source_url=recording_url,
            artifacts=tuple(artifacts),
        )


@register_adapter
class LegistarAdapter(MeetingAdapter):
    """A Legistar Web API event (``/v1/{client}/events``) for one configured jurisdiction."""

    platform_code = "legistar"

    def __init__(self, *, jurisdiction_name: str, state_code: str | None = None, state: str | None = None) -> None:
        self.jurisdiction_name = jurisdiction_name
        self.state_code = state_code
        self.state = state

    def normalize(self, raw: Mapping[str, Any]) -> Meeting:
        event_id = clean_value(raw.get("EventId"))
        if event_id is None:
            raise ValueError("Legistar event has no EventId, so it can't identify a meeting.")
        artifacts = []
        for kind, key, label in (
            (ArtifactKind.AGENDA, "EventAgendaFile", "Agenda"),
            (ArtifactKind.MINUTES, "EventMinutesFile", "Minutes"),
            (ArtifactKind.RECORDING, "EventVideoPath", "Video"),
        ):
            url = clean_value(raw.get(key))
            if url is not None:
                artifacts.append(MeetingArtifact(kind, self.platform_code, url=str(url), label=label))
        body_name = clean_value(raw.get("EventBodyName"))
        return Meeting(
            platform_code=self.platform_code,
            platform_meeting_id=str(event_id),
            jurisdiction_name=self.jurisdiction_name,
            title=body_name,
            meeting_date=parse_meeting_date(raw.get("EventDate")),
            state_code=self.state_code,
            state=self.state,
            body_name=body_name,
            source_url=clean_value(raw.get("EventInSiteURL")),
            artifacts=tuple(artifacts),
        )

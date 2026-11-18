"""What the meeting-platform readers return (#536).

One :class:`PlatformMeeting` per meeting a portal lists, with only what the platform
really serves: a field the platform doesn't give stays ``None`` (never guessed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

# transcription_status values (bronze_platform_meeting.transcription_status).
CAPTIONS = "captions"            # the platform serves caption text; it is in bronze_platform_meeting_caption
QUEUED_WHISPER = "queued_whisper"  # a video URL and no captions: waiting for Colab Whisper (#489)
VIDEO_URL_UNKNOWN = "video_url_unknown"  # the platform says there is a video but gives no URL
NO_VIDEO = "no_video"


@dataclass
class CaptionCue:
    start: float
    duration: Optional[float]
    text: str

    def as_json(self) -> dict[str, Any]:
        return {"start": self.start, "duration": self.duration, "text": self.text}


@dataclass
class MeetingCaption:
    """Caption / closed-caption text a platform serves for a meeting's video."""

    caption_source: str  # e.g. 'granicus_vtt'
    caption_url: Optional[str]
    caption_format: str  # 'vtt' | 'srt' | 'text'
    raw_text: str
    cues: list[CaptionCue] = field(default_factory=list)
    language: Optional[str] = "en"


@dataclass
class PlatformMeeting:
    platform: str  # 'legistar' | 'granicus'
    meeting_uid: str  # unique within the platform: '<portal>:<native id>'
    portal: str  # Legistar client slug or Granicus host
    jurisdiction_id: Optional[str] = None
    state_code: Optional[str] = None
    body_name: Optional[str] = None
    title: Optional[str] = None
    meeting_date: Optional[date] = None
    meeting_time: Optional[str] = None
    location: Optional[str] = None
    agenda_url: Optional[str] = None
    minutes_url: Optional[str] = None
    video_url: Optional[str] = None
    video_url_source: Optional[str] = None  # where video_url came from (see the readers)
    video_clip_id: Optional[str] = None
    detail_url: Optional[str] = None
    agenda_text: Optional[str] = None  # agenda item text the platform serves (not PDF extraction)
    minutes_text: Optional[str] = None  # minutes notes / actions the platform serves
    source_modified_at: Optional[datetime] = None
    raw: dict[str, Any] = field(default_factory=dict)
    caption: Optional[MeetingCaption] = None
    has_video: bool = False

    @property
    def transcription_status(self) -> str:
        if self.caption is not None and self.caption.raw_text.strip():
            return CAPTIONS
        if self.video_url:
            return QUEUED_WHISPER
        if self.has_video or self.video_clip_id:
            return VIDEO_URL_UNKNOWN
        return NO_VIDEO


@dataclass
class PortalResult:
    """One portal read (or probe): its status and the meetings it gave."""

    platform: str
    portal: str
    portal_url: str
    jurisdiction_id: Optional[str]
    state_code: Optional[str] = None
    found_via: str = "survey"  # 'survey' (#460/#464) | 'url_pattern'
    data_center: bool = False
    status: str = "ok"  # ok | empty | robots_disallowed | blocked | not_configured | error
    detail: Optional[str] = None
    meetings: list[PlatformMeeting] = field(default_factory=list)

    @property
    def newest_meeting_date(self) -> Optional[date]:
        """Newest meeting already held (scheduled meetings ahead of today are left out)."""
        today = date.today()
        dates = [m.meeting_date for m in self.meetings if m.meeting_date and m.meeting_date <= today]
        return max(dates) if dates else None

"""One meeting shape for every broadcast platform (CORE-3.1, #242).

A council's meetings arrive from YouTube, Legistar, Granicus and others, each with its own
field names. Adapters turn each platform's record into a ``Meeting`` whose agenda, recording,
transcript and minutes sit in fixed slots, so nothing downstream has to know which vendor a
council uses. A missing artifact is ``None``: it is never filled in.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class ArtifactKind(str, Enum):
    """What a meeting artifact is, whatever the platform calls it."""

    AGENDA = "agenda"
    RECORDING = "recording"
    TRANSCRIPT = "transcript"
    MINUTES = "minutes"


def clean_value(value: Any) -> Any:
    """Return ``None`` for missing values (None, NaN, blank text); otherwise the value, stripped if text."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def parse_meeting_date(value: Any) -> date | None:
    """Read a meeting date from a date, datetime or ISO-style string; ``None`` if absent or unreadable."""
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):  # a pandas Timestamp, without importing pandas
        return value.to_pydatetime().date()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


@dataclass(frozen=True)
class MeetingArtifact:
    """One document or media item of a meeting: where it lives, or its text when the source carries it."""

    kind: ArtifactKind
    platform_code: str
    url: str | None = None
    text: str | None = None
    label: str | None = None
    media_type: str | None = None

    def __post_init__(self) -> None:
        if not (self.url or self.text):
            raise ValueError(f"A {self.kind.value} artifact needs a url or text; an empty one is not an artifact.")


@dataclass(frozen=True)
class Meeting:
    """One meeting, in the same shape for every platform. Grain: one meeting per platform record."""

    platform_code: str
    platform_meeting_id: str
    jurisdiction_name: str
    title: str | None = None
    meeting_date: date | None = None
    state_code: str | None = None
    state: str | None = None
    body_name: str | None = None
    source_url: str | None = None
    artifacts: tuple[MeetingArtifact, ...] = field(default_factory=tuple)

    @property
    def meeting_key(self) -> str:
        """A stable key: the same platform record always gets the same key."""
        digest = hashlib.sha256(f"{self.platform_code}:{self.platform_meeting_id}".encode()).hexdigest()
        return digest[:16]

    def first(self, kind: ArtifactKind) -> MeetingArtifact | None:
        return next((a for a in self.artifacts if a.kind is kind), None)

    @property
    def agenda(self) -> MeetingArtifact | None:
        return self.first(ArtifactKind.AGENDA)

    @property
    def recording(self) -> MeetingArtifact | None:
        return self.first(ArtifactKind.RECORDING)

    @property
    def transcript(self) -> MeetingArtifact | None:
        return self.first(ArtifactKind.TRANSCRIPT)

    @property
    def minutes(self) -> MeetingArtifact | None:
        return self.first(ArtifactKind.MINUTES)

    def to_record(self) -> dict[str, Any]:
        """Flatten to one row with the same keys for every platform; a missing artifact is ``None``."""

        def url(artifact: MeetingArtifact | None) -> str | None:
            return artifact.url if artifact else None

        return {
            "meeting_key": self.meeting_key,
            "platform_code": self.platform_code,
            "platform_meeting_id": self.platform_meeting_id,
            "jurisdiction_name": self.jurisdiction_name,
            "state_code": self.state_code,
            "state": self.state,
            "body_name": self.body_name,
            "title": self.title,
            "meeting_date": self.meeting_date,
            "source_url": self.source_url,
            "agenda_url": url(self.agenda),
            "recording_url": url(self.recording),
            "transcript_url": url(self.transcript),
            "minutes_url": url(self.minutes),
            "has_transcript_text": bool(self.transcript and self.transcript.text),
        }

"""One meeting model across broadcast platforms (CORE-3.1, #242).

    from ingestion.meetings import adapter_for, coverage_report

    adapter_cls = adapter_for(platform_code, jurisdiction_name=name)  # raises UnsupportedPlatformError
    meeting = adapter_cls(...).normalize(raw_record)                    # the same Meeting shape everywhere
"""

from ingestion.meetings.adapters import STATE_CODES, LegistarAdapter, YouTubeLocalViewAdapter
from ingestion.meetings.model import ArtifactKind, Meeting, MeetingArtifact, clean_value, parse_meeting_date
from ingestion.meetings.registry import (
    UNKNOWN_PLATFORM,
    CoverageReport,
    MeetingAdapter,
    UnsupportedPlatformError,
    adapter_for,
    coverage_report,
    register_adapter,
    supported_platforms,
)

__all__ = [
    "STATE_CODES",
    "UNKNOWN_PLATFORM",
    "ArtifactKind",
    "CoverageReport",
    "LegistarAdapter",
    "Meeting",
    "MeetingAdapter",
    "MeetingArtifact",
    "UnsupportedPlatformError",
    "YouTubeLocalViewAdapter",
    "adapter_for",
    "clean_value",
    "coverage_report",
    "parse_meeting_date",
    "register_adapter",
    "supported_platforms",
]
